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
        if not raw.endswith(b'\n'):
            issue('Incomplete native source prefix', source, 'incomplete')
            continue
        events = [json.loads(line) for line in raw.splitlines()]
        headers = [e for e in events if e.get('type') == 'session_meta']
        if len(headers) != 1 or headers[0] != events[0]:
            issue('Missing, duplicate or displaced session header', source)
            continue
        event, header = headers[0], headers[0]['payload']
        identity, path = header.get('id'), header.get('agent_path')
        if not isinstance(identity, str) or not identity or not isinstance(path, str) or not path:
            issue('Missing native UUID or canonical path', source)
            continue
        if identity in nodes or path in paths:
            issue('Duplicate native UUID or canonical path', identity)
            continue
        nested = header.get('source', {}).get('subagent', {}).get('thread_spawn', {})
        parent = header.get('parent_thread_id')
        if nested and (nested.get('parent_thread_id') != parent or nested.get('agent_path') != path):
            issue('Conflicting top-level and nested parent/path', identity)
        nodes[identity] = {'id': identity, 'path': path, 'parent': parent, 'events': events,
                           'created': event['timestamp'], 'source': source, 'raw': raw}
        paths[path] = identity
    if root_id not in nodes:
        issue('Product root source unavailable', root_id, 'incomplete')
    selected = {root_id} if root_id in nodes else set()
    while True:
        expanded = selected | {i for i, n in nodes.items() if n['parent'] in selected}
        if expanded == selected:
            break
        selected = expanded
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
    for session in sessions:
        usage = session.get('usage')
        if usage is None:
            missing_usage.append(session['native_session_id'])
            continue
        for key, value in usage.items():
            if type(value) is not int or value < 0:
                issue('Invalid native token counter', session['native_session_id'])
                continue
            totals[key] = totals.get(key, 0) + value
    return {'verdict': 'fail' if any(i['severity'] == 'fail' for i in issues) else 'incomplete',
            'issues': issues, 'attempts': attempts, 'sessions': sessions,
            'discovered_native_ids': sorted(selected), 'graph_consistent_observed_prefix': not issues,
            'observed_cost_totals': totals, 'usage_unavailable_native_ids': missing_usage,
            'all_observed_sessions_normally_terminal': bool(sessions) and all(s['native_completion_observed'] for s in sessions),
            'source_pins': {str(p): {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} for p, raw in sources.items()},
            'allocation_registry_completeness_attested': False, 'complete_final_cost': False,
            'fresh_context_qualified': False, 'inventory_and_drain_authority_qualified': False,
            'scope': 'Observed supplied native graph only; runtime allocation gate/drain/flush and exhaustive inventory remain required'}
