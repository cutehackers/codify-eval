"""Discover observed native product descendants. Runtime drain authority remains separate.

This pure validator cannot attest complete allocation from supplied sources or rows.
It preserves known missing children, every failed attempt and unavailable usage.
"""
import hashlib
import json
from datetime import datetime

from improvement_usage_v4 import snapshot

SPAWN_NAMES = {'spawn_agent', 'collaboration.spawn_agent'}
MODEL = {'model': 'gpt-6.1-sol', 'effort': 'medium'}
QUOTA = 'collab spawn failed: agent thread limit reached'


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def discover(sources, root_id, expected_ids=None):
    """sources is an independently collected prefix map, NOT inventory authority."""
    nodes, paths, issues, attempts = {}, {}, [], []
    def issue(reason, identity=None, severity='fail'):
        issues.append({'reason': reason, 'native_session_id': identity, 'severity': severity})
    for source, raw in sources.items():
        complete = raw.endswith(b'\n')
        observed = raw if complete else raw[:raw.rfind(b'\n')+1]
        if not complete:
            issue('Incomplete native source prefix', source, 'incomplete')
        if not observed:
            issue('No complete native records available', source, 'incomplete')
            continue
        events = [json.loads(line) for line in observed.splitlines()]
        headers = [e for e in events if e.get('type') == 'session_meta']
        if len(headers) != 1 or headers[0] != events[0]:
            issue('Missing, duplicate or displaced session header', source)
            continue
        event, header = headers[0], headers[0]['payload']
        identity, path = header.get('id'), header.get('agent_path')
        if not isinstance(identity, str) or not identity or not isinstance(path, str) or not path:
            issue('Missing native UUID or canonical path', source)
            continue
        if identity in nodes:
            issue('Duplicate native UUID', identity)
            continue
        if path in paths:
            issue('Ambiguous canonical path for distinct native UUIDs', identity)
        nested = header.get('source', {}).get('subagent', {}).get('thread_spawn', {})
        parent = header.get('parent_thread_id')
        if nested and (nested.get('parent_thread_id') != parent or nested.get('agent_path') != path):
            issue('Conflicting top-level and nested parent/path', identity)
        nodes[identity] = {'id': identity, 'path': path, 'parent': parent, 'events': events,
                           'created': event['timestamp'], 'source': source, 'raw': observed, 'full_raw': raw, 'source_complete': complete}
        paths[path] = identity
    if root_id not in nodes:
        issue('Product root source unavailable', root_id, 'incomplete')
    selected = {root_id} if root_id in nodes else set()
    while True:
        expanded = selected | {i for i, n in nodes.items() if n['parent'] in selected}
        if expanded == selected:
            break
        selected = expanded
    for identity in selected:
        trail, cursor = set(), identity
        while cursor in selected:
            if cursor in trail:
                issue('Cycle in product UUID ancestry', identity)
                break
            trail.add(cursor)
            cursor = nodes[cursor]['parent']
    joined = set()
    sessions = []
    for identity in sorted(selected):
        node = nodes[identity]
        try:
            observed = snapshot(node['raw'], node['path'], node['source'])
            observed['role'] = 'product'
            sessions.append(observed)
        except ValueError as error:
            issue(str(error), identity)
            counts = [e['payload'].get('info', {}).get('total_token_usage') for e in node['events'] if e.get('type') == 'event_msg' and e.get('payload', {}).get('type') == 'token_count']
            observed = {'agent_path': node['path'], 'native_session_id': identity, 'role': 'product',
                        'parent_thread_id': node['parent'], 'native_source': node['source'],
                        'source_bytes': len(node['raw']), 'source_sha256': hashlib.sha256(node['raw']).hexdigest(),
                        'usage': counts[-1] if counts else None, 'native_completion_observed': False,
                        'qualification_error': str(error)}
            sessions.append(observed)
        observed['full_source_complete'] = node['source_complete']
        if not node['source_complete']:
            observed['native_completion_observed'] = False
        calls, outputs = {}, {}
        for index, event in enumerate(node['events']):
            payload = event.get('payload', {})
            kind, call_id = payload.get('type'), payload.get('call_id')
            if kind in {'function_call', 'custom_tool_call'}:
                if not isinstance(call_id, str) or not call_id or call_id in calls:
                    issue('Missing or duplicate native call ID', identity)
                    continue
                calls[call_id] = (index, event)
            elif kind in {'function_call_output', 'custom_tool_call_output'}:
                if call_id not in calls or call_id in outputs:
                    issue('Unmatched, duplicate or backward native receipt', identity)
                    continue
                if instant(event['timestamp']) < instant(calls[call_id][1]['timestamp']):
                    issue('Native receipt precedes invocation', identity)
                outputs[call_id] = (index, event)
        for call_id, (index, event) in calls.items():
            payload = event['payload']
            name = payload.get('name', '')
            if name not in SPAWN_NAMES:
                if 'spawn' in name or 'create_thread' in name or 'fork_thread' in name:
                    issue('Unqualified allocation route', identity)
                continue
            namespace = payload.get('namespace')
            if namespace not in {None, 'collaboration'} or payload['type'] != 'function_call':
                issue('Unqualified allocation namespace/type', identity)
            args = payload.get('arguments', {})
            args = json.loads(args) if isinstance(args, str) else args
            requested = args.get('task_name')
            requested_path = node['path'] + '/' + requested if isinstance(requested, str) and requested else None
            row = {'parent_native_id': identity, 'call_id': call_id, 'call_index': index,
                   'requested_path': requested_path, 'child_native_id': None,
                   'outcome': 'pending', 'fresh_context_requested': args.get('fork_turns') == 'none'}
            attempts.append(row)
            if not requested_path or '/' in requested or requested in {'.', '..'}:
                issue('Invalid requested child name', identity)
            if args.get('fork_turns') != 'none' or args.get('model') != MODEL['model'] or args.get('reasoning_effort') != MODEL['effort']:
                issue('Unqualified requested context/model', identity)
            receipt = outputs.get(call_id)
            if receipt is None:
                issue('Allocation receipt unavailable', identity, 'incomplete')
                continue
            row['receipt_index'] = receipt[0]
            text = receipt[1]['payload'].get('output')
            if text == QUOTA:
                row['outcome'] = 'rejection_schema_observed_no_child_authority_unavailable'
                issue('Quota rejection lacks authoritative no-child disposition', identity, 'incomplete')
                continue
            try:
                result = json.loads(text)
            except (TypeError, ValueError):
                row['outcome'] = 'unknown'
                issue('Unknown allocation result', identity, 'incomplete')
                continue
            if not isinstance(result, dict) or set(result) != {'task_name'} or result['task_name'] != requested_path:
                row['outcome'] = 'invalid'
                issue('Allocation receipt schema/path mismatch', identity)
                continue
            children = [i for i in selected if nodes[i]['parent'] == identity and nodes[i]['path'] == requested_path]
            if len(children) != 1:
                row['outcome'] = 'known_missing'
                issue('Successful allocation child source unavailable or ambiguous', identity, 'incomplete')
                continue
            child = children[0]
            if child in joined:
                issue('Child joined to multiple allocation calls', child)
            joined.add(child)
            if not instant(event['timestamp']) <= instant(nodes[child]['created']) <= instant(receipt[1]['timestamp']):
                issue('Child creation outside allocation call/receipt', child)
            row.update(outcome='success', child_native_id=child)
    for identity in selected - {root_id} - joined:
        issue('Orphan descendant without successful allocation receipt', identity)
    if expected_ids is not None and (len(expected_ids) != len(set(expected_ids)) or set(expected_ids) != selected):
        issue('Caller membership differs from independently discovered graph')
    totals = {}
    missing_usage = []
    unavailable_metrics = {}
    for session in sessions:
        usage = session.get('usage')
        required_counters = {'input_tokens', 'cached_input_tokens', 'output_tokens', 'total_tokens'}
        if not isinstance(usage, dict):
            usage = {}
        unavailable = sorted(required_counters - set(usage) | {k for k, v in usage.items() if type(v) is not int or v < 0})
        if unavailable:
            issue('Unavailable or invalid native token metrics', session['native_session_id'], 'incomplete')
            missing_usage.append(session['native_session_id'])
            unavailable_metrics[session['native_session_id']] = unavailable
        for key, value in usage.items():
            if type(value) is int and value >= 0:
                totals[key] = totals.get(key, 0) + value
    return {'verdict': 'fail' if any(i['severity'] == 'fail' for i in issues) else 'incomplete',
            'issues': issues, 'attempts': attempts, 'sessions': sessions,
            'discovered_native_ids': sorted(selected), 'graph_consistent_observed_prefix': not issues,
            'observed_cost_totals': totals, 'usage_unavailable_native_ids': missing_usage, 'unavailable_metrics_by_native_id': unavailable_metrics,
            'all_observed_sessions_normally_terminal': bool(sessions) and all(s['native_completion_observed'] for s in sessions),
            'source_pins': {str(p): {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} for p, raw in sources.items()},
            'allocation_registry_completeness_attested': False, 'complete_final_cost': False,
            'fresh_context_qualified': False, 'inventory_and_drain_authority_qualified': False,
            'scope': 'Observed supplied native graph only; runtime allocation gate/drain/flush and exhaustive inventory remain required'}
