"""Version two observed native parent/child join; not inventory or runtime authority."""
import hashlib
import json
from datetime import datetime

from dialogue_schema import normalize

MODEL = {'model': 'gpt-6.1-sol', 'effort': 'medium'}

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def parse(raw):
    if not raw or not raw.endswith(b'\n'):
        raise ValueError('Incomplete native prefix; observe the same source again')
    events = [json.loads(line) for line in raw.splitlines()]
    headers = [e for e in events if e.get('type') == 'session_meta']
    if len(headers) != 1 or events[0] != headers[0]:
        raise ValueError('Missing/duplicate/displaced native header')
    return events, headers[0]['payload']

def instant(event):
    return datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))

def binding(parent_raw, child_raw, parent_path, child_path):
    """Paths are coordinator-selected locators; UUID/call/token joins prove origin.

    A coordinator root has no agent_path in its native header. Its externally
    established '/root' path may be supplied only by trusted coordinator code.
    This function cannot establish that coordinator identity or path authority.
    """
    parents, parent = parse(parent_raw)
    children, child = parse(child_raw)
    if not isinstance(parent_path, str) or not parent_path.startswith('/'):
        raise ValueError('Invalid trusted parent path')
    if parent.get('agent_path') not in {None, parent_path}:
        raise ValueError('Parent header/path conflict')
    if (not isinstance(child_path, str) or child_path.rsplit('/', 1)[0] != parent_path
            or not child_path.rsplit('/', 1)[1] or child_path.endswith('/.')
            or child_path.endswith('/..')):
        raise ValueError('Expected one immediate child path')
    nested = child.get('source', {}).get('subagent', {}).get('thread_spawn', {})
    if (not parent.get('id') or not child.get('id') or parent['id'] == child['id']
            or child.get('parent_thread_id') != parent['id']
            or child.get('agent_path') != child_path
            or nested.get('parent_thread_id') != parent['id']
            or nested.get('agent_path') != child_path):
        raise ValueError('Native UUID/parent/path conflict')
    contexts = [(i, e) for i, e in enumerate(children) if e.get('type') == 'turn_context']
    if (not contexts or any({k: e['payload'].get(k) for k in MODEL} != MODEL
                            for _, e in contexts)):
        raise ValueError('Missing/unqualified actual child model contexts')
    calls, outputs = {}, {}
    for index, event in enumerate(parents):
        payload = event.get('payload', {})
        kind = payload.get('type')
        if kind not in {'function_call', 'custom_tool_call', 'function_call_output', 'custom_tool_call_output'}:
            continue
        call_id = payload.get('call_id')
        if not isinstance(call_id, str) or not call_id:
            raise ValueError('Missing native call identity')
        if kind in {'function_call', 'custom_tool_call'}:
            if call_id in calls:
                raise ValueError('Duplicate native call identity')
            calls[call_id] = (index, event)
        else:
            if call_id not in calls or call_id in outputs or instant(event) < instant(calls[call_id][1]):
                raise ValueError('Unmatched/duplicate/backward native output')
            outputs[call_id] = (index, event)
    matches = []
    for call_id, (index, event) in calls.items():
        payload = event['payload']
        if payload.get('name') not in {'spawn_agent', 'collaboration.spawn_agent'}:
            continue
        args = payload.get('arguments', {})
        args = json.loads(args) if isinstance(args, str) else args
        if not isinstance(args, dict):
            raise ValueError('Unknown spawn argument schema')
        task = args.get('task_name')
        if parent_path + '/' + str(task) != child_path:
            continue
        if (payload['type'] != 'function_call'
                or payload.get('namespace') not in {None, 'collaboration'}
                or not isinstance(task, str) or '/' in task or task in {'.', '..'}
                or args.get('fork_turns') != 'none'
                or args.get('model') != MODEL['model']
                or args.get('reasoning_effort') != MODEL['effort']
                or not isinstance(args.get('message'), str) or not args['message'].startswith('gAAAAA')):
            raise ValueError('Unqualified spawn route/context/model/input')
        if call_id not in outputs:
            raise ValueError('Observed spawn has no success receipt yet')
        receipt_index, receipt = outputs[call_id]
        result = json.loads(receipt['payload'].get('output', ''))
        if result != {'task_name': child_path}:
            raise ValueError('Spawn success receipt/path mismatch')
        if not instant(event) <= instant(children[0]) <= instant(receipt):
            raise ValueError('Child creation outside actual spawn call/receipt')
        matches.append((call_id, event, receipt, args))
    if len(matches) != 1:
        raise ValueError('Missing/ambiguous parent allocation join')
    call_id, call, receipt, args = matches[0]
    normalized, conversions = normalize(children)
    incoming = [(i, e) for i, e in enumerate(normalized)
                if e.get('payload', {}).get('type') == 'agent_message'
                and e['payload'].get('author') == parent_path]
    if len(incoming) != 1:
        raise ValueError('Missing/extra parent dispatch request')
    index, request = incoming[0]
    payload = request['payload']
    first_context_index, first_context = contexts[0]
    turn_id = first_context['payload'].get('turn_id')
    if not isinstance(turn_id, str) or not turn_id:
        raise ValueError('Missing initial child turn identity')
    encrypted = [m for m in conversions if m['event_index'] == index and m['source_field'] == 'content.encrypted_content']
    if len(encrypted) != 1:
        raise ValueError('Initial dispatch is not the observed encrypted content representation')
    if (payload.get('recipient') != child_path or payload.get('message') != args['message']
            or index <= first_context_index
            or payload.get('internal_chat_message_metadata_passthrough', {}).get('turn_id')
               != first_context['payload'].get('turn_id')
            or not instant(children[0]) <= instant(first_context) <= instant(request)
            or instant(request) < instant(call)):
        raise ValueError('Dispatch token/routing/turn/chronology mismatch')
    first_tool = next((i for i, e in enumerate(children)
                      if e.get('payload', {}).get('type') in {'function_call', 'custom_tool_call'}), None)
    if first_tool is not None and (first_tool <= index or instant(children[first_tool]) < instant(request)):
        raise ValueError('Child tool call preceded the initial request')
    return {'status': 'observed_parent_child_binding', 'parent_native_id': parent['id'],
        'child_native_id': child['id'], 'parent_path': parent_path, 'child_path': child_path,
        'spawn_call_id': call_id, 'request_token_sha256': digest(args['message'].encode()),
        'parent_prefix': {'bytes': len(parent_raw), 'sha256': digest(parent_raw)},
        'child_prefix': {'bytes': len(child_raw), 'sha256': digest(child_raw)},
        'actual_child_models': [e['payload'].get('model') for _, e in contexts],
        'fresh_context_requested': True, 'hidden_context_freshness_qualified': False,
        'coordinator_identity_authority_qualified': False, 'runtime_qualified': False,
        'complete_final_cost': False, 'superiority_proven': False,
        'normalization': conversions}
