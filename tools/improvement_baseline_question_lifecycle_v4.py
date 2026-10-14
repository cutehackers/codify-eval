"""Strict baseline root one/two-turn decoder with full native origin checks.

A supplied turn_contract is data, not authenticated approval. The adapter must
independently authenticate its first seal, same-UUID delivery, reply-read proof,
source pins and original clock before using this decoder's result. This module
allocates nothing and grants no runtime, cleanup, cost or comparison authority.
Workers stay one turn. A terminal one-turn root can retain a late non-triggering
packet only from a worker that genuinely completed before that root completion.
Integration ordering and authenticated no-followup remain external audit gates.
Workers stay one turn. Root phase first_seal may retain a non-triggering worker
final after turn one completes; terminal two-turn decoding retains that same
between-turn delivery without treating it as a root turn or permitting tools.
"""
import json
import math
import re

import improvement_q01_dialogue_core_v1 as core
import improvement_baseline_membership_v1 as membership

parse,require,instant,final_text=core.parse,core.require,core.instant,core.final_text


def turn_id(payload):
    values=[]
    if 'turn_id' in payload:values.append(payload['turn_id'])
    if 'internal_chat_message_metadata_passthrough' in payload:
        metadata=payload['internal_chat_message_metadata_passthrough']
        require(isinstance(metadata,dict),'Native turn metadata must be an object')
        if 'turn_id' in metadata:values.append(metadata['turn_id'])
    require(all(isinstance(v,str) and bool(v) for v in values),'Native turn identity must be a nonempty string')
    require(len(set(values))<=1,'Conflicting native turn identity fields')
    return values[0] if values else None


def decoded_turn_contract(raw, binding, expected_turns, turn_contract):
    """Validate the exact supplied contract, without proving its approval origin."""
    require(type(binding) is dict and set(binding) == {
        'agent_path', 'actor_native_id', 'parent_native_id'} and
        all(type(value) is str and bool(value) for value in binding.values()),
        'Exact native binding required')
    require(binding['actor_native_id'] != binding['parent_native_id'],
            'Actor and parent native UUIDs must be distinct')
    path = binding['agent_path']
    require(re.fullmatch(r'/root/[A-Za-z0-9_]+(?:/worker[12])?', path) is not None,
            'Exact root or immediate worker path required')
    require(type(expected_turns) is int and expected_turns in (1, 2),
            'Typed expected turn count required')
    keys = {'schema_version', 'binding', 'job', 'expected_turns', 'turn_ids',
            'native_sha256', 'worker_cap', 'phase'}
    require(type(turn_contract) is dict and set(turn_contract) == keys and
            type(turn_contract['schema_version']) is int and
            turn_contract['schema_version'] == 1, 'Exact supplied turn contract required')
    require(type(turn_contract['binding']) is dict and
            core.decode(json.dumps(turn_contract['binding'])) == binding and
            turn_contract['expected_turns'] == expected_turns and
            type(turn_contract['expected_turns']) is int,
            'Supplied turn binding or typed count changed')
    ids = turn_contract['turn_ids']
    require(type(ids) is list and len(ids) == expected_turns and
            all(type(value) is str and bool(value) for value in ids) and
            len(set(ids)) == len(ids), 'Exact distinct approved turn IDs required')
    require(turn_contract['native_sha256'] == core.digest(raw),
            'Supplied exact native source pin changed')
    job = path.rsplit('/', 1)[-1] if path.count('/') == 3 else 'root'
    require(turn_contract['job'] == job and
            type(turn_contract['worker_cap']) is int and
            turn_contract['worker_cap'] in (0, 2), 'Exact role and cumulative cap required')
    require(turn_contract['phase'] in ('first_seal', 'terminal') and
            (turn_contract['phase'] != 'first_seal' or job == 'root' and expected_turns == 1),
            'First seal is only a one-turn root prefix')
    require(job == 'root' or expected_turns == 1 and
            turn_contract['worker_cap'] == 0 and turn_contract['phase'] == 'terminal',
            'Workers cannot resume or delegate')
    return turn_contract


def child_proofs(raw,binding,child_sources):
    require(isinstance(child_sources,dict) and len(child_sources)<=2,'Bounded original worker sources required')
    events=parse(raw);ops=membership.operations(events);by_path={}
    for cid,event,args,receipt in ops:
        require(set(args)=={'task_name','message','fork_turns','model','reasoning_effort'} and
                args['task_name'] in ('worker1','worker2') and args['fork_turns']=='none' and
                args['model']=='gpt-6.1-sol' and args['reasoning_effort']=='medium', 'Unapproved worker allocation')
        path=binding['agent_path']+'/'+args['task_name']
        require(path not in by_path and receipt is not None and
                core.decode(receipt[1]['payload']['output'])=={'task_name':path},'Worker allocation unproven or repeated')
        by_path[path]=(cid,event)
    require(set(by_path)==set(child_sources),'Original worker sources do not cover every actual allocation')
    proofs={};ids={binding['actor_native_id']}
    for path,child_raw in child_sources.items():
        require(re.fullmatch(re.escape(binding['agent_path'])+r'/worker[12]',path) is not None and
                isinstance(child_raw,bytes) and child_raw.endswith(b'\n'), 'Complete original child source required')
        child_events,header=membership.source(child_raw,path,binding['actor_native_id'])
        require(header['id'] not in ids and not membership.operations(child_events),'Duplicate UUID or nested worker allocation')
        ids.add(header['id']);child_binding={'agent_path':path,'actor_native_id':header['id'],'parent_native_id':binding['actor_native_id']}
        child_ids=[e['payload'].get('turn_id') for e in child_events if e['type']=='turn_context']
        child_contract={'schema_version':1,'binding':child_binding,'job':path.rsplit('/',1)[-1],
            'expected_turns':1,'turn_ids':child_ids,'native_sha256':core.digest(child_raw),
            'worker_cap':0,'phase':'terminal'}
        _,turns=lifecycle(child_raw,child_binding,1,turn_contract=child_contract)
        join=membership.native.binding(raw,membership.first_request_prefix(child_raw,binding['agent_path']),binding['agent_path'],path)
        require(join['spawn_call_id']==by_path[path][0],'Original child allocation request join changed')
        require(instant(by_path[path][1]['timestamp'])<=instant(child_events[0]['timestamp']), 'Child source precedes allocation')
        proofs[path]={'native_sha256':core.digest(child_raw),'native_session_id':header['id'],'spawn_call_id':join['spawn_call_id'],
            'completed_at':turns[0]['completed_at'],'wrapper':f"Message Type: FINAL_ANSWER\nTask name: {binding['agent_path']}\nSender: {path}\nPayload:\n"+turns[0]['final_text']}
    return proofs


def lifecycle(raw, binding, expected_turns, child_sources=None, *, turn_contract):
    contract=decoded_turn_contract(raw,binding,expected_turns,turn_contract)
    require(child_sources is None or type(child_sources) is dict, 'Typed child source map required')
    require(len({} if child_sources is None else child_sources)<=contract['worker_cap'],
            'Original cumulative worker cap exceeded')
    deliveries=child_proofs(raw,binding,{} if child_sources is None else child_sources)
    observed_deliveries=[]
    parent_metadata_indexes=set()
    require(type(expected_turns) is int and expected_turns in (1, 2), 'Unsupported turn count')
    events, _ = membership.source(raw, binding['agent_path'], binding['parent_native_id'])
    headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
    require(len(headers) == 1 and events[0].get('type') == 'session_meta', 'Ambiguous session header')
    header = headers[0]
    require(header.get('id') == binding['actor_native_id']
            and header.get('agent_path') == binding['agent_path']
            and header.get('parent_thread_id') == binding['parent_native_id'], 'Actor session identity changed')
    parent_path=binding['agent_path'].rsplit('/',1)[0]
    initial=[i for i,e in enumerate(events) if e['payload'].get('type')=='agent_message' and e['payload'].get('author')==parent_path]
    require(len(initial)==expected_turns,'Exact original and approved parent requests required')
    require(all(i<initial[0] for i,e in enumerate(events) if e['payload'].get('type')=='user_message' or
            (e['payload'].get('type')=='message' and e['payload'].get('role')=='user')),
            'Unapproved user request after original parent delivery')
    groups = {name: [] for name in ('start', 'context', 'incoming', 'final', 'complete')}
    for index, event in enumerate(events):
        p = event['payload']
        name = None
        if event.get('type') == 'turn_context':
            name = 'context'
            require(p.get('model') == 'gpt-6.1-sol' and p.get('effort') == 'medium', 'Model or reasoning changed')
            settings = p.get('collaboration_mode', {}).get('settings')
            if settings is not None:
                require(settings.get('model') == 'gpt-6.1-sol' and settings.get('reasoning_effort') == 'medium',
                        'Conflicting collaboration model settings')
        elif event.get('type') == 'event_msg' and p.get('type') in ('task_started', 'task_complete'):
            name = 'start' if p['type'] == 'task_started' else 'complete'
        elif event.get('type') == 'response_item':
            if p.get('type') == 'agent_message':
                if p.get('author') in deliveries:
                    proof=deliveries[p['author']]
                    require(p.get('recipient')==binding['agent_path'] and index>0, 'Worker final recipient changed')
                    metadata=events[index-1]
                    require(metadata['type']=='inter_agent_communication_metadata' and
                            set(metadata['payload'])=={'trigger_turn'} and metadata['payload']['trigger_turn'] is False and
                            0 <= (instant(event['timestamp']) - instant(metadata['timestamp'])).total_seconds() <= .001,
                            'Worker final started an unapproved turn')
                    message_meta=p.get('internal_chat_message_metadata_passthrough',{})
                    require(isinstance(message_meta,dict) and isinstance(message_meta.get('turn_id'),str) and
                            bool(message_meta['turn_id']), 'Authoritative worker delivery turn identity required')
                    created=message_meta.get('create_time')
                    require(isinstance(p.get('id'),str) and bool(p['id']) and type(created) in (int,float) and
                            math.isfinite(created) and abs(created-instant(event['timestamp']).timestamp())<.001,
                            'Worker delivery identity or clock metadata invalid')
                    require(p.get('content')==[{'type':'input_text','text':proof['wrapper']}], 'Worker final payload changed')
                    require(p['author'] not in [row['agent_path'] for row in observed_deliveries], 'Worker final replayed')
                    require(instant(proof['completed_at'])<=instant(event['timestamp']), 'Worker delivery before genuine completion')
                    observed_deliveries.append({'agent_path':p['author'],'event_index':index,
                        'turn_id':turn_id(p),'timestamp':event['timestamp'],'native_sha256':proof['native_sha256'],
                        'native_session_id':proof['native_session_id'],'spawn_call_id':proof['spawn_call_id']})
                    continue
                name = 'incoming'
                if index>0 and events[index-1]['type']=='inter_agent_communication_metadata':
                    metadata=events[index-1]
                    require(set(metadata['payload'])=={'trigger_turn'} and metadata['payload']['trigger_turn'] is True
                            and 0 <= (instant(event['timestamp'])-instant(metadata['timestamp'])).total_seconds() <= .001,
                            'Original parent request requires adjacent triggering metadata')
                    parent_metadata_indexes.add(index-1)
                require(p.get('author') == binding['agent_path'].rsplit('/', 1)[0]
                        and p.get('recipient') == binding['agent_path'], 'Incoming routing changed')
            elif p.get('type') == 'message' and p.get('role') == 'assistant' and (
                    p.get('channel') == 'final' or p.get('phase') == 'final_answer'):
                name = 'final'
        if name:
            groups[name].append((index, event))
    require(all(len(rows) == expected_turns for rows in groups.values()), 'Incomplete or additional turn lifecycle')
    require([turn_id(e['payload']) for _,e in groups['context']] == contract['turn_ids'],
            'Observed turn IDs differ from supplied exact contract')
    ids, turns = set(), []
    last_end = -1
    for n in range(expected_turns):
        rows = [groups[name][n] for name in ('start', 'context', 'incoming', 'final', 'complete')]
        indexes = [i for i, _ in rows]
        require(last_end < indexes[0] and indexes == sorted(set(indexes)), 'Turn lifecycle ordering mismatch')
        ids_here = [turn_id(e['payload']) for _, e in rows]
        identity = ids_here[0]
        require(isinstance(identity, str) and bool(identity) and len(set(ids_here)) == 1 and identity not in ids,
                'Turn identity mismatch or reuse')
        ids.add(identity)
        text = final_text(rows[3][1]['payload'])
        require(rows[4][1]['payload'].get('last_agent_message') == text, 'Completion final text mismatch')
        completion = rows[4][1]['payload']
        require(completion.get('error') is None and completion.get('status') in (None, 'completed', 'success')
                and all(completion.get(key) is None or completion.get(key) is False
                        for key in ('interrupted', 'cancelled')),
                'Errored or interrupted native completion cannot establish normal lifecycle')
        turns.append({'turn_id': identity, 'start_index': indexes[0], 'incoming_index': indexes[2],
                      'final_index': indexes[3], 'complete_index': indexes[4], 'final_text': text,
                      'completed_at': rows[4][1]['timestamp']})
        last_end = indexes[4]
    for index, event in enumerate(events):
        if event.get('type') == 'response_item' and event['payload'].get('type') in (
                'function_call', 'custom_tool_call', 'function_call_output', 'custom_tool_call_output'):
            require(any(t['incoming_index'] < index < t['final_index'] for t in turns),
                    'Tool event outside an active received turn')
    require({row['agent_path'] for row in observed_deliveries}==set(deliveries), 'Missing genuine worker final delivery')
    metadata_indexes={row['event_index']-1 for row in observed_deliveries}|parent_metadata_indexes
    require({i for i,e in enumerate(events) if e['type']=='inter_agent_communication_metadata'}
            == metadata_indexes, 'Unbound native communication metadata')
    for row in observed_deliveries:
        active=[t for t in turns if t['incoming_index']<row['event_index']<t['final_index'] and
                t['turn_id']==row['turn_id'] and instant(row['timestamp'])<=instant(t['completed_at'])]
        if active:
            owner=active[0]
            row['delivery_phase']='active_turn'
        else:
            first=turns[0]
            next_start=turns[1]['start_index'] if expected_turns==2 else len(events)
            paused=(first['complete_index']<row['event_index']<next_start and
                    (expected_turns==2 or contract['phase']=='first_seal' or
                     contract['phase']=='terminal' and
                     instant(deliveries[row['agent_path']]['completed_at'])<=instant(first['completed_at'])) and
                    row['turn_id']==first['turn_id'] and
                    instant(first['completed_at'])<=instant(row['timestamp']))
            require(paused, 'Worker final outside active turn or first completed pause')
            owner=first
            row['delivery_phase']='late_completed_worker' if expected_turns==1 and contract['phase']=='terminal' else 'between_turns'
        owner.setdefault('worker_deliveries',[]).append(row)
    return events, turns

