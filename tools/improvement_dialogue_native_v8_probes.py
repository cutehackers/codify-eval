"""Counterexamples for actual reply receipt and same-session write barrier."""
import copy
import hashlib
import json
import shlex
from pathlib import Path

from prepare import ROOT
from improvement_dialogue_native_v8 import READ, SCRIPT, reply_barrier


def encode(events):
    return b''.join(json.dumps(e).encode() + b'\n' for e in events)


def fixture():
    def e(timestamp, kind, payload):
        return {'timestamp': '2026-10-11T00:00:' + timestamp + 'Z', 'type': kind, 'payload': payload}
    initial = [e('01', 'session_meta', {'id': 'child', 'agent_path': '/root/probe', 'parent_thread_id': 'parent'}),
               e('02', 'turn_context', {'model': 'gpt-6.1-sol', 'effort': 'medium', 'turn_id': 'one'}),
               e('03', 'event_msg', {'type': 'agent_message', 'recipient': '/root/probe', 'author': '/root', 'message': 'initial'}),
               e('04', 'event_msg', {'type': 'task_complete', 'turn_id': 'one'})]
    raw = encode(initial)
    code = 'text(await tools.exec_command(' + json.dumps({'cmd': shlex.join(['python3', str(ROOT / 'tools' / SCRIPT), '--run', 'probe', '--cmd', READ]), 'max_output_tokens': 2000}) + '));'
    record = {'run_id': 'probe', 'container_id': 'reply-container', 'phase': 'reply_read', 'command': READ, 'time': '2026-10-11T00:00:09.010000+00:00', 'elapsed_seconds': 0.1, 'exit_code': 0, 'output': 'Use the selected public policy.'}
    later = [e('06', 'turn_context', {'model': 'gpt-6.1-sol', 'effort': 'medium', 'turn_id': 'two'}),
             e('07', 'event_msg', {'type': 'agent_message', 'recipient': '/root/probe', 'author': '/root', 'message': 'followup', 'internal_chat_message_metadata_passthrough': {'turn_id': 'two'}}),
             e('09', 'response_item', {'type': 'custom_tool_call', 'name': 'exec', 'call_id': 'read', 'input': code}),
             e('10', 'response_item', {'type': 'custom_tool_call_output', 'call_id': 'read', 'output': json.dumps({'exit_code': 0, 'output': json.dumps(record), 'wall_time_seconds': 0.1})})]
    parent = [e('00', 'session_meta', {'id': 'parent'}),
              e('05', 'response_item', {'type': 'function_call', 'name': 'followup_task', 'call_id': 'dispatch', 'arguments': json.dumps({'target': '/root/probe', 'message': 'followup'})}),
              e('08', 'response_item', {'type': 'function_call_output', 'call_id': 'dispatch', 'output': ''})]
    metadata = {'run_id': 'probe', 'agent_path': '/root/probe', 'actor_native_id': 'child'}
    staged = {'first_native_bytes': len(raw), 'first_native_sha256': hashlib.sha256(raw).hexdigest(), 'staged_at': 0,
              'followup': 'followup', 'reply_utf8': record['output'], 'reply_container_id': record['container_id']}
    return initial + later, parent, metadata, staged, [record]


def main():
    outcomes = []
    def check(name, change, expected):
        actor, parent, metadata, staged, records = copy.deepcopy(fixture())
        change(actor, parent, metadata, staged, records)
        try:
            reply_barrier(encode(actor), encode(parent), metadata, staged, records, str(ROOT))
            passed = True
        except (ValueError, KeyError, TypeError):
            passed = False
        assert passed == expected, name
        outcomes.append({'name': name, 'pass': True, 'barrier_opened': passed})
    check('complete same-session read opens barrier', lambda *a: None, True)
    check('missing native output stays closed', lambda a, *rest: a.pop(), False)
    check('truncated stdout stays closed', lambda a, *rest: a[-1]['payload'].update(output=json.dumps({'exit_code': 0, 'output': '{', 'wall_time_seconds': 0.1})), False)
    check('host-only fake receipt stays closed', lambda a, p, m, s, r: a[-1]['payload'].update(call_id='unrelated'), False)
    check('wrong phase container stays closed', lambda a, p, m, s, r: s.update(reply_container_id='other'), False)
    check('wrong assigned run stays closed', lambda a, p, m, s, r: m.update(run_id='other'), False)
    check('changed first native prefix stays closed', lambda a, p, m, s, r: a[1]['payload'].update(effort='high'), False)
    check('unqualified second model stays closed', lambda a, p, m, s, r: a[4]['payload'].update(model='gpt-6-sol'), False)
    check('wrong parent source stays closed', lambda a, p, *rest: p[0]['payload'].update(id='other'), False)
    check('missing successful dispatch stays closed', lambda a, p, *rest: p.pop(), False)
    check('dispatch before staging stays closed', lambda a, p, m, s, r: s.update(staged_at=9999999999), False)
    check('wrong incoming turn stays closed', lambda a, *rest: a[5]['payload']['internal_chat_message_metadata_passthrough'].update(turn_id='one'), False)
    check('extra unscoped tool stays closed', lambda a, *rest: a.append({'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'web.run', 'call_id': 'bypass', 'arguments': '{}'}}), False)
    check('partial reply bytes stay closed', lambda a, p, m, s, r: s.update(reply_utf8='different'), False)
    def old_broker_marker(actor, *rest):
        command = "python3 " + str(ROOT / 'tools/agent_io.py') + " --run probe --cmd 'echo improvement_dialogue_io_v5.py'"
        code = 'text(await tools.exec_command(' + json.dumps({'cmd': command}) + '));'
        actor.append({'timestamp': '2026-10-11T00:00:11Z', 'type': 'response_item', 'payload': {'type': 'custom_tool_call', 'name': 'exec', 'call_id': 'wrong-broker', 'input': code}})
    check('inner marker cannot select old host broker', old_broker_marker, False)
    check('duplicate actual read call identity stays closed', lambda a, *rest: a.append(copy.deepcopy(a[6])), False)
    check('duplicate native output stays closed', lambda a, *rest: a.append(copy.deepcopy(a[7])), False)
    check('stale native read output stays closed', lambda a, *rest: a[-1].update(timestamp='2026-10-11T00:00:01Z'), False)
    check('wrong parent tool namespace stays closed', lambda a, p, *rest: p[1]['payload'].update(name='other.followup_task'), False)
    def content_message(actor, parent, metadata, staged, records):
        message = actor[5]['payload'];message.pop('message')
        message['content'] = [{'type':'input_text','text':'incoming task'}, {'type':'encrypted_content','encrypted_content':'gAAAAAqualified-native-token'}]
        parent[1]['payload']['arguments']=json.dumps({'target':'/root/probe','message':'gAAAAAqualified-native-token'})
    check('actual encrypted content shape routes without decryption', content_message, True)
    def conflict(actor, parent, metadata, staged, records):
        content_message(actor,parent,metadata,staged,records)
        actor[5]['payload']['message']='conflicting token'
    check('conflicting legacy/content shape stays closed', conflict, False)
    def ambiguous(actor, parent, metadata, staged, records):
        content_message(actor,parent,metadata,staged,records)
        actor[5]['payload']['content'].append({'type':'encrypted_content','encrypted_content':'gAAAAAsecond-token'})
    check('ambiguous encrypted blocks stay closed', ambiguous, False)
    check('known namespaced followup alias succeeds', lambda a, p, *rest: p[1]['payload'].update(name='collaboration.followup_task'), True)
    def duplicate_parent(actor, parent, *rest):
        q=copy.deepcopy(parent[1]);q['payload']['name']='unrelated';parent.insert(2,q)
    check('unrelated duplicate parent call stays closed', duplicate_parent, False)
    check('parent output before call stays closed', lambda a,p,*rest:p.insert(1,p.pop()), False)
    def impossible_duration(actor,parent,metadata,staged,records):
        records[0]['elapsed_seconds']=100
        actor[-1]['payload']['output']=json.dumps({'exit_code':0,'output':json.dumps(records[0]),'wall_time_seconds':0.1})
    check('completion beyond native receipt stays closed', impossible_duration, False)
    def owned_poll(actor, parent, metadata, staged, records):
        terminal=actor.pop()
        actor.append({'timestamp':'2026-10-11T00:00:09.100000Z','type':'response_item','payload':{'type':'custom_tool_call_output','call_id':'read','output':json.dumps({'session_id':77,'output':''})}})
        actor.append({'timestamp':'2026-10-11T00:00:09.200000Z','type':'response_item','payload':{'type':'custom_tool_call','name':'exec','call_id':'poll','input':'text(await tools.write_stdin({session_id:77,chars:""}));'}})
        terminal['payload']['call_id']='poll';actor.append(terminal)
    check('owned poll complete read succeeds', owned_poll, True)
    def reowned_poll(actor,parent,metadata,staged,records):
        owned_poll(actor,parent,metadata,staged,records)
        other=copy.deepcopy(actor[6]);other['timestamp']='2026-10-11T00:00:09.150000Z'
        other['payload']['call_id']='other'
        other['payload']['input']=other['payload']['input'].replace(READ,'echo other')
        result=copy.deepcopy(actor[7]);result['timestamp']='2026-10-11T00:00:09.160000Z';result['payload']['call_id']='other'
        actor[8:8]=[other,result]
    check('conflicting session reownership stays closed', reowned_poll, False)
    def negative_session(actor,parent,metadata,staged,records):
        owned_poll(actor,parent,metadata,staged,records)
        actor[7]['payload']['output']=json.dumps({'session_id':-77,'output':''})
        actor[8]['payload']['input']=actor[8]['payload']['input'].replace('77','-77')
    check('negative session identity stays closed', negative_session, False)
    def premature_poll(actor,parent,metadata,staged,records):
        owned_poll(actor,parent,metadata,staged,records)
        actor[8]['timestamp']='2026-10-11T00:00:08Z'
    check('poll before session receipt stays closed', premature_poll, False)
    def premature_poll_output(actor,parent,metadata,staged,records):
        owned_poll(actor,parent,metadata,staged,records)
        actor[9]['timestamp']='2026-10-11T00:00:09.150000Z'
    check('poll output before poll invocation stays closed', premature_poll_output, False)
    result = {'status': 'pass', 'scope': 'Pure native protocol counterexamples including actual content schema only; no Docker/native actor qualification or semantic coverage claim', 'count': len(outcomes), 'probes': outcomes}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
