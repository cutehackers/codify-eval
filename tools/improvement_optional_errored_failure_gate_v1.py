"""Pure mixed native terminal gate for server-overloaded failed attempts only.

Every original source remains unchanged. API errors do not imply software
failure, normal completion, comparison admission or complete billed cost.
"""
import math

import improvement_optional_completed_failure_gate_v1 as previous
import improvement_optional_errored_inventory_v1 as inventory
import improvement_optional_lifecycle_v5 as lifecycle

original = previous.original
core = original.inventory.core
require = original.require


def terminal(raw, binding):
    events = core.parse(raw)
    completes = [e for e in events if e.get('type') == 'event_msg'
                 and e['payload'].get('type') == 'task_complete']
    require(len(completes) == 1, 'One genuine native terminal required')
    complete = completes[0]
    error = complete['payload'].get('error')
    if error is None:
        _, turns = lifecycle.lifecycle(raw, binding, 1, {})
        return {'status': 'completed', 'api_text': turns[0]['final_text'],
                'completed_at': turns[0]['completed_at'], 'turn': turns[0]}
    require(isinstance(error, dict) and set(error) == {'message', 'codex_error_info'}
            and error['codex_error_info'] == 'server_overloaded'
            and isinstance(error['message'], str) and bool(error['message'])
            and complete['payload'].get('last_agent_message') is None,
            'Exact original capacity error terminal required')
    headers = [e for e in events if e.get('type') == 'session_meta']
    require(len(headers) == 1 and events[0] == headers[0]
            and headers[0]['payload']['id'] == binding['actor_native_id']
            and headers[0]['payload']['agent_path'] == binding['agent_path']
            and headers[0]['payload']['parent_thread_id'] == binding['parent_native_id'],
            'Original error actor identity changed')
    starts = [i for i,e in enumerate(events) if e.get('type') == 'event_msg'
              and e['payload'].get('type') == 'task_started']
    contexts = [i for i,e in enumerate(events) if e.get('type') == 'turn_context']
    incoming = [i for i,e in enumerate(events) if e['payload'].get('type') == 'agent_message'
                and e['payload'].get('author') == binding['agent_path'].rsplit('/',1)[0]]
    finals = [e for e in events if e['payload'].get('type') == 'message'
              and e['payload'].get('role') == 'assistant'
              and (e['payload'].get('channel') == 'final' or e['payload'].get('phase') == 'final_answer')]
    require(len(starts) == len(contexts) == len(incoming) == 1 and not finals
            and starts[0] < contexts[0] < incoming[0] < len(events)-1
            and events[-1] == complete, 'One original failed turn ending in native error required')
    turn_events = [events[i] for i in (starts[0],contexts[0],incoming[0])] + [complete]
    ids = [lifecycle.turn_id(e['payload']) for e in turn_events]
    require(isinstance(ids[0],str) and bool(ids[0]) and len(set(ids)) == 1,
            'Error turn identity changed')
    context = events[contexts[0]]['payload']
    require(context.get('model') == 'gpt-6.1-sol' and context.get('effort') == 'medium',
            'Error actor model/reasoning changed')
    settings = context.get('collaboration_mode',{}).get('settings')
    require(settings is None or (settings.get('model') == 'gpt-6.1-sol'
            and settings.get('reasoning_effort') == 'medium'), 'Conflicting error actor settings')
    require(all(i < incoming[0] for i,e in enumerate(events)
                if e['payload'].get('type') == 'user_message' or
                (e['payload'].get('type') == 'message' and e['payload'].get('role') == 'user')),
            'New user input in failed actor')
    require(events[incoming[0]]['payload'].get('recipient') == binding['agent_path'],
            'Failed actor request recipient changed')
    parent_path = binding['agent_path'].rsplit('/',1)[0]
    root_actor = parent_path == '/root'
    for i,e in enumerate(events):
        p = e['payload']
        if p.get('type') == 'agent_message' and p.get('author') != parent_path:
            require(root_actor and isinstance(p.get('author'),str)
                    and p['author'] in {binding['agent_path']+'/worker1',binding['agent_path']+'/worker2'},
                    'Unapproved message into errored worker or root')
        if e.get('type') == 'inter_agent_communication_metadata':
            require(i+1 < len(events) and events[i+1]['payload'].get('type') == 'agent_message',
                    'Stray failed actor delivery metadata')
    calls, outputs = {}, {}
    for i,e in enumerate(events):
        p = e['payload']
        if p.get('type') in ('function_call','custom_tool_call','function_call_output','custom_tool_call_output'):
            require(incoming[0] < i < len(events)-1 and e.get('type') == 'response_item',
                    'Failed actor tool outside original received turn')
            table = outputs if p['type'].endswith('_output') else calls
            cid = p.get('call_id')
            require(isinstance(cid,str) and bool(cid) and cid not in table, 'Duplicate error tool identity')
            table[cid] = i
    require(set(calls) == set(outputs) and all(calls[k] < outputs[k] for k in calls),
            'Pending failed actor tool prevents cleanup')
    require(core.instant(complete['timestamp']) >= core.instant(events[starts[0]]['timestamp']),
            'Error terminal precedes original start')
    return {'status':'errored', 'api_text':error['message'], 'error':error,
            'completed_at':complete['timestamp'],
            'turn':{'turn_id':ids[0],'incoming_index':incoming[0],
                    'complete_index':len(events)-1,'final_text':None}}


def deliveries(root_raw, root_path, terminals):
    root = terminals[root_path]
    require(root['status'] == 'errored', 'This adapter requires genuinely errored root')
    events = core.parse(root_raw)
    observed = set()
    for i,e in enumerate(events):
        p = e['payload']
        if p.get('type') != 'agent_message' or p.get('author') == '/root':
            continue
        path = p.get('author')
        require(path in terminals and path != root_path and path not in observed,
                'Unregistered or repeated child delivery')
        child = terminals[path]
        body = child['api_text'] if child['status'] == 'completed' else (
            'Agent errored: ' + child['api_text'] + '\n\n'
            "This agent's turn failed. If you still need this agent, use the available collaboration tools to give it another task.")
        wrapper = f'Message Type: FINAL_ANSWER\nTask name: {root_path}\nSender: {path}\nPayload:\n' + body
        require(p.get('recipient') == root_path and p.get('content') == [{'type':'input_text','text':wrapper}],
                'Child terminal delivery changed')
        require(i > 0 and events[i-1]['type'] == 'inter_agent_communication_metadata'
                and events[i-1]['payload'] == {'trigger_turn':False}
                and 0 <= (core.instant(e['timestamp'])-core.instant(events[i-1]['timestamp'])).total_seconds() <= .001,
                'Child delivery started unapproved turn')
        metadata = p.get('internal_chat_message_metadata_passthrough',{})
        created = metadata.get('create_time')
        require(lifecycle.turn_id(p) == root['turn']['turn_id']
                and isinstance(p.get('id'),str) and bool(p['id'])
                and type(created) in (int,float) and math.isfinite(created)
                and abs(created-core.instant(e['timestamp']).timestamp()) < .001
                and root['turn']['incoming_index'] < i < root['turn']['complete_index']
                and core.instant(child['completed_at']) <= core.instant(e['timestamp']),
                'Child delivery identity or chronology changed')
        observed.add(path)
    require(observed == set(terminals)-{root_path}, 'All actual child terminal deliveries required')


def verify(config,state,root_intent,worker_intents,coordinator_raw,root_raw,
           worker_raw_by_path,provision,registry_folder,locators,inventory_call_id,commitment):
    proof = original.membership.reconcile_membership(config,state,root_intent,worker_intents,
        coordinator_raw,root_raw,worker_raw_by_path,provision,registry_folder)
    require(proof['provided_allocation_joins_complete'] and not proof['pending_allocation_slots']
            and not proof['observed_unbound_sources'], 'Every original allocation join required')
    sources = {proof['root_path']:root_raw,**worker_raw_by_path}
    members = {m['agent_path']:m for m in proof['members']}
    require(set(sources) == set(members) == set(locators), 'Exact all-member original sources required')
    terminals = {p:terminal(sources[p],original.lifecycle_binding(m)) for p,m in members.items()}
    deliveries(root_raw,proof['root_path'],terminals)
    completions = {p:t['completed_at'] for p,t in terminals.items()}
    current = inventory.completed_inventory(coordinator_raw,proof['coordinator_native_id'],
        completions,inventory_call_id,commitment,terminal_records=terminals)
    usage = original.cost.usage_members(proof,sources,locators)
    return {'membership':proof,'current_inventory':current,'completions':completions,
            'terminals':terminals,'usage':usage,'original_no_more_delivery_commitment':commitment,
            'errored_terminal_failure_gate_pass':True,'software_pass':None,
            'cleanup_authorized':False,'interrupted_branch_qualified':False,
            'comparison_admitted':False,'superiority_proven':False}
