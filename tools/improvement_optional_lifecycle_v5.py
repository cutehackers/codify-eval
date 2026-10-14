"""Optional-only full-original lifecycle with validated automatic worker finals.

No source records are filtered or rewritten. Parent/child native origin binding,
current source fences and caller authority remain external qualification gates.
Adjacent native delivery timestamps may cross one millisecond serialization tick.
This helper grants no cleanup, comparison or whole-cost authority.
"""
import json
import math
import re

import improvement_q01_dialogue_core_v1 as core
import improvement_optional_membership_v2 as membership

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
        _,turns=lifecycle(child_raw,child_binding,1)
        join=membership.native.binding(raw,membership.first_request_prefix(child_raw,binding['agent_path']),binding['agent_path'],path)
        require(join['spawn_call_id']==by_path[path][0],'Original child allocation request join changed')
        require(instant(by_path[path][1]['timestamp'])<=instant(child_events[0]['timestamp']), 'Child source precedes allocation')
        proofs[path]={'native_sha256':core.digest(child_raw),'native_session_id':header['id'],'spawn_call_id':join['spawn_call_id'],
            'completed_at':turns[0]['completed_at'],'wrapper':f"Message Type: FINAL_ANSWER\nTask name: {binding['agent_path']}\nSender: {path}\nPayload:\n"+turns[0]['final_text']}
    return proofs


def lifecycle(raw, binding, expected_turns, child_sources=None):
    require(expected_turns == 1, "Optional controls permit one approved turn")
    deliveries=child_proofs(raw,binding,{} if child_sources is None else child_sources)
    observed_deliveries=[]
    require(type(expected_turns) is int and expected_turns in (1, 2), 'Unsupported turn count')
    events = parse(raw)
    headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
    require(len(headers) == 1 and events[0].get('type') == 'session_meta', 'Ambiguous session header')
    header = headers[0]
    require(header.get('id') == binding['actor_native_id']
            and header.get('agent_path') == binding['agent_path']
            and header.get('parent_thread_id') == binding['parent_native_id'], 'Actor session identity changed')
    parent_path=binding['agent_path'].rsplit('/',1)[0]
    initial=[i for i,e in enumerate(events) if e['payload'].get('type')=='agent_message' and e['payload'].get('author')==parent_path]
    require(len(initial)==1,'One original parent request required')
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
                require(p.get('author') == binding['agent_path'].rsplit('/', 1)[0]
                        and p.get('recipient') == binding['agent_path'], 'Incoming routing changed')
            elif p.get('type') == 'message' and p.get('role') == 'assistant' and (
                    p.get('channel') == 'final' or p.get('phase') == 'final_answer'):
                name = 'final'
        if name:
            groups[name].append((index, event))
    require(all(len(rows) == expected_turns for rows in groups.values()), 'Incomplete or additional turn lifecycle')
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
    for row in observed_deliveries:
        require(any(t['incoming_index']<row['event_index']<t['final_index'] and
                    t['turn_id']==row['turn_id'] and instant(row['timestamp'])<=instant(t['completed_at'])
                    for t in turns), 'Worker final outside original active parent turn')
    if observed_deliveries:turns[0]['worker_deliveries']=observed_deliveries
    return events, turns

