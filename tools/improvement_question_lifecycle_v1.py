"""Full-original approved one/two-turn lifecycle for new question controls.

No records are removed or rewritten. Native origin, approved reply, live source
fences and coordinator authority remain separate gates. Prior core file unchanged.
"""
import improvement_q01_dialogue_core_v1 as base
parse,require,final_text=base.parse,base.require,base.final_text

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

def lifecycle(raw, binding, expected_turns):
    require(type(expected_turns) is int and expected_turns in (1, 2), 'Unsupported turn count')
    events = parse(raw)
    headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
    require(len(headers) == 1 and events[0].get('type') == 'session_meta', 'Ambiguous session header')
    header = headers[0]
    require(header.get('id') == binding['actor_native_id']
            and header.get('agent_path') == binding['agent_path']
            and header.get('parent_thread_id') == binding['parent_native_id'], 'Actor session identity changed')
    parent=binding['agent_path'].rsplit('/',1)[0]
    initial=[i for i,e in enumerate(events) if e['payload'].get('type')=='agent_message' and e['payload'].get('author')==parent]
    require(bool(initial),'Original parent request required')
    require(all(i<initial[0] for i,e in enumerate(events) if e['payload'].get('type')=='user_message' or
                (e['payload'].get('type')=='message' and e['payload'].get('role')=='user')),
            'Unapproved user input after original parent delivery')
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
    return events, turns
