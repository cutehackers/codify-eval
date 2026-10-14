"""Closed observed routes for one synthetic product root and two workers.

Literal wrappers only. Accepted native prefixes are not a universal host sandbox,
global inventory attestation, or hidden-context freshness proof.
"""
import hashlib
import json
import re
import shlex
from pathlib import Path

from improvement_software_native_binding_v2 import binding, instant, parse
from improvement_usage_v4 import snapshot
from transport import OPTIONS, STRING, poll_options, result_objects

SCRIPT = 'improvement_software_broker_v7.py'
MODEL = {'model': 'gpt-6.1-sol', 'effort': 'medium'}


def wrapper(code, root, registration, job):
    match = re.fullmatch(r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*('
                        + STRING + ')' + OPTIONS + r'\s*\}\s*\)\s*\)\s*;?', code.strip(), re.S)
    if not match:
        raise ValueError('Literal broker wrapper required')
    command = json.loads(match.group(1))
    parts = shlex.split(command)
    expected = ['python3', str(Path(root) / 'tools' / SCRIPT), '--run', registration['run_name'],
                '--job', job, '--cap']
    if (len(parts) != 12 or parts[:7] != expected or parts[8] != '--op'
            or parts[10] != '--data' or not re.fullmatch('[0-9a-f]{48}', parts[7])
            or hashlib.sha256(parts[7].encode()).hexdigest() != registration['capability_hashes'][job]):
        raise ValueError('Wrong broker route/job/capability')
    allowed = {'exec'} if job != 'root' else {'exec', 'seal', 'view', 'decide', 'integrate', 'verify'}
    if parts[9] not in allowed:
        raise ValueError('Operation forbidden for role')
    base = ' '.join(parts[:11]) + ' '
    canonical = base + shlex.quote(parts[11])
    # Two exact POSIX literal encodings, never a general shell expression.
    backslash_literal = base + "'" + parts[11].replace("'", "'\\''") + "'"
    if command not in {canonical, backslash_literal}:
        raise ValueError('Canonical single-quoted payload required; shell expansions forbidden')
    data = json.loads(parts[11])
    if not isinstance(data, dict):
        raise ValueError('Broker payload must be an object')
    return {'job': job, 'op': parts[9], 'data': data}


def audit(raw, registration, job, root, terminal=True):
    events, header = parse(raw)
    row = registration['actors'][job]
    if header.get('agent_path') != row['path']:
        raise ValueError('Actor path mismatch')
    contexts = [e for e in events if e.get('type') == 'turn_context']
    if len(contexts) != 1 or {k: contexts[0]['payload'].get(k) for k in MODEL} != MODEL:
        raise ValueError('Exactly one fixed-model actor turn required')
    if instant(events[0]) > instant(contexts[0]):
        raise ValueError('Context predates native actor creation')
    observed = snapshot(raw, row['path'], row['source'])
    if terminal and not observed['native_completion_observed']:
        raise ValueError('Actor has not completed its original turn')
    ends = [(i,e) for i,e in enumerate(events) if e.get('type') == 'event_msg' and e.get('payload',{}).get('type') == 'task_complete']
    calls, outputs, owned, sessions = {}, {}, {}, set()
    bootstrap_count, requests, spawns = 0, [], []
    for index, event in enumerate(events):
        p = event.get('payload', {})
        kind, identity = p.get('type'), p.get('call_id')
        if kind in {'function_call', 'custom_tool_call'}:
            if instant(event) < instant(contexts[0]) or terminal and (len(ends) != 1 or index >= ends[0][0] or instant(event) > instant(ends[0][1])):
                raise ValueError('Native invocation outside its actual turn interval')
            if not isinstance(identity, str) or not identity or identity in calls:
                raise ValueError('Missing/duplicate native call identity')
            name = p.get('name')
            route = {'index': index, 'event': event, 'mode': None}
            if name in {'exec', 'functions.exec'} and p.get('namespace') in {None, 'functions'}:
                code = p.get('input', p.get('arguments'))
                if not isinstance(code, str):
                    raise ValueError('Unknown native execution schema')
                if code.strip() == row['bootstrap_code']:
                    bootstrap_count += 1
                    if calls or bootstrap_count != 1:
                        raise ValueError('Bootstrap must be first and unique')
                    route['mode'] = 'bootstrap'
                else:
                    poll = poll_options(code)
                    if poll is not None:
                        sid = poll['session_id']
                        if sid not in owned or instant(event) < owned[sid]['time']:
                            raise ValueError('Unowned/backward poll')
                        route.update(mode='poll', session=sid)
                    else:
                        request = wrapper(code, root, registration, job)
                        requests.append(request)
                        route.update(mode='broker', request=request)
            elif job == 'root' and p.get('type') == 'function_call' and p.get('namespace') in {None, 'collaboration'}:
                args = p.get('arguments')
                args = json.loads(args) if isinstance(args, str) else args
                if name in {'spawn_agent', 'collaboration.spawn_agent'}:
                    expected_names = {registration['actors'][j]['path'].rsplit('/', 1)[1] for j in ('label', 'quantity')}
                    if (not isinstance(args, dict) or set(args) != {'task_name', 'fork_turns', 'model', 'reasoning_effort', 'message'}
                            or args['task_name'] not in expected_names or args['task_name'] in spawns
                            or args['fork_turns'] != 'none' or args['model'] != MODEL['model']
                            or args['reasoning_effort'] != MODEL['effort']):
                        raise ValueError('Unqualified worker dispatch')
                    spawns.append(args['task_name'])
                    route.update(mode='spawn', child=row['path'] + '/' + args['task_name'])
                elif name in {'list_agents', 'collaboration.list_agents'} and args == {'path_prefix': row['path']}:
                    route['mode'] = 'status'
                elif (name in {'wait_agent', 'collaboration.wait_agent'} and isinstance(args, dict)
                      and set(args) == {'timeout_ms'} and type(args['timeout_ms']) is int
                      and 10000 <= args['timeout_ms'] <= 60000):
                    route['mode'] = 'wait'
                else:
                    raise ValueError('Unsupported root native route')
            else:
                raise ValueError('Unsupported native tool route')
            calls[identity] = route
        elif kind in {'function_call_output', 'custom_tool_call_output'}:
            if terminal and (len(ends) != 1 or index >= ends[0][0] or instant(event) > instant(ends[0][1])):
                raise ValueError('Native receipt outside its actual turn interval')
            if identity not in calls or identity in outputs or instant(event) < instant(calls[identity]['event']):
                raise ValueError('Unmatched/duplicate/backward native receipt')
            outputs[identity] = event
            route = calls[identity]
            if route['mode'] == 'spawn':
                if json.loads(p.get('output', '')) != {'task_name': route['child']}:
                    raise ValueError('Worker allocation lacks exact success receipt')
            if route['mode'] in {'bootstrap', 'broker', 'poll'}:
                values = list(result_objects(p))
                if len(values) != 1 or not isinstance(values[0].get('output'), str):
                    raise ValueError('Unknown execution result')
                value = values[0]
                if route['mode'] == 'bootstrap' and (value.get('exit_code') != 0
                        or hashlib.sha256(value['output'].encode()).hexdigest() != row['request_sha256']):
                    raise ValueError('Bootstrap did not return the exact pinned request successfully')
                if route['mode'] == 'poll':
                    sid = route['session']
                    if ('session_id' in value and value['session_id'] is not None and type(value['session_id']) is not int
                            or 'exit_code' in value and type(value['exit_code']) is not int
                            or value.get('session_id') not in {None, sid}
                            or not (type(value.get('exit_code')) is int or value.get('session_id') == sid)):
                        raise ValueError('Poll returned wrong session')
                    owned[sid]['time'] = instant(event)
                    if type(value.get('exit_code')) is int:
                        del owned[sid]
                elif type(value.get('session_id')) is int and 'exit_code' not in value:
                    sid = value['session_id']
                    if sid <= 0 or sid in sessions or route['mode'] == 'bootstrap':
                        raise ValueError('Invalid/reused asynchronous session')
                    sessions.add(sid); owned[sid] = {'time': instant(event)}
                elif type(value.get('exit_code')) is not int:
                    raise ValueError('Missing terminal execution status')
    if bootstrap_count != 1 or set(calls) != set(outputs) or owned:
        raise ValueError('Incomplete bootstrap/native calls/poll sessions')
    if terminal and job == 'root' and len(spawns) != 2:
        raise ValueError('Exactly two actual worker allocations required')
    return {'status': 'closed_observed_native_routes', 'native_calls': len(calls),
            'broker_requests': requests, 'actual_worker_spawns': spawns, 'usage': observed,
            'native_global_completeness_attested': False}


def runtime_completed(parent_raw, actor_paths, after, required=None):
    """Use an actual native list_agents call/receipt, never caller-supplied rows."""
    events, _ = parse(parent_raw)
    calls, matches = {}, []
    seen_calls, seen_outputs, call_events = set(), set(), {}
    prefix = actor_paths['root']
    required = set(actor_paths.values()) if required is None else set(required)
    if not required or not required <= set(actor_paths.values()):
        raise ValueError('Invalid required runtime statuses')
    for event in events:
        p = event.get('payload', {})
        identity = p.get('call_id')
        if p.get('type') in {'function_call', 'custom_tool_call'}:
            if not isinstance(identity, str) or not identity or identity in seen_calls:
                raise ValueError('Missing/duplicate native status-source call identity')
            seen_calls.add(identity); call_events[identity] = event
        elif p.get('type') in {'function_call_output', 'custom_tool_call_output'}:
            if identity not in seen_calls or identity in seen_outputs or instant(event) < instant(call_events[identity]):
                raise ValueError('Unmatched/duplicate/backward native status-source output')
            seen_outputs.add(identity)
        if p.get('type') == 'function_call' and p.get('name') in {'list_agents', 'collaboration.list_agents'}:
            args = p.get('arguments', {})
            args = json.loads(args) if isinstance(args, str) else args
            if args == {'path_prefix': prefix} and p.get('namespace') in {None, 'collaboration'}:
                calls[p['call_id']] = event
        elif p.get('type') == 'function_call_output' and p.get('call_id') in calls:
            call = calls[p['call_id']]
            if instant(event) < instant(call) or instant(call).timestamp() < after:
                continue
            value = json.loads(p.get('output', ''))
            rows = value.get('agents', [])
            if len(rows) != len(actor_paths) or {r.get('agent_name') for r in rows} != set(actor_paths.values()):
                continue
            if all(isinstance(r.get('agent_status'), dict) and set(r['agent_status']) == {'completed'} for r in rows if r['agent_name'] in required):
                matches.append({'call_id': p['call_id'], 'receipt_timestamp': event['timestamp']})
    if set(calls) - seen_outputs:
        raise ValueError('Pending status observation has no forward receipt')
    if not matches:
        raise ValueError('No actual completed runtime statuses after native terminal turns')
    return matches[-1]
