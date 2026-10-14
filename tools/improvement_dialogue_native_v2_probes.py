"""Counterexamples for actual reply receipt and same-session write barrier."""
import copy
import hashlib
import json
import shlex
from pathlib import Path

from prepare import ROOT
from improvement_dialogue_native_v2 import READ, SCRIPT, reply_barrier


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
    record = {'run_id': 'probe', 'container_id': 'reply-container', 'phase': 'reply_read', 'command': READ, 'time': '2026-10-11T00:00:09.010000+00:00', 'exit_code': 0, 'output': 'Use the selected public policy.'}
    later = [e('06', 'turn_context', {'model': 'gpt-6.1-sol', 'effort': 'medium', 'turn_id': 'two'}),
             e('07', 'event_msg', {'type': 'agent_message', 'recipient': '/root/probe', 'author': '/root', 'message': 'followup', 'internal_chat_message_metadata_passthrough': {'turn_id': 'two'}}),
             e('09', 'response_item', {'type': 'custom_tool_call', 'name': 'exec', 'call_id': 'read', 'input': code}),
             e('10', 'response_item', {'type': 'custom_tool_call_output', 'call_id': 'read', 'output': json.dumps({'exit_code': 0, 'output': json.dumps(record), 'wall_time_seconds': 0.1})})]
    parent = [e('00', 'session_meta', {'id': 'parent'}),
              e('05', 'response_item', {'type': 'function_call', 'name': 'collaboration.followup_task', 'call_id': 'dispatch', 'arguments': json.dumps({'target': '/root/probe', 'message': 'followup'})}),
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
        command = "python3 " + str(ROOT / 'tools/agent_io.py') + " --run probe --cmd 'echo improvement_dialogue_io_v2.py'"
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
    result = {'status': 'pass', 'scope': 'Pure native protocol counterexamples including actual content schema only; no Docker/native actor qualification or semantic coverage claim', 'count': len(outcomes), 'probes': outcomes}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
