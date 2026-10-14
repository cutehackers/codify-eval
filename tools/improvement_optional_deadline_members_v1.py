"""Pure aggregate interruption checks; caller authenticates allocation proofs.

No native control, cleanup or admission authority. An actual prospective control
must qualify the observed interruption format and owned cleanup before use.
Every supplied member requires the same original-deadline interrupt and latest
inventory; this deliberately does not infer absence from a missing source.
"""
import math
import re

import improvement_deadline_authority_v3 as original
import improvement_optional_membership_v3 as membership

require = original.core.require


def members(proof, sources):
    require(proof.get('provided_allocation_joins_complete') is True
            and proof.get('pending_allocation_slots') == []
            and proof.get('observed_unbound_sources') == [], 'Complete original allocation joins required')
    root = proof.get('root_path')
    require(isinstance(root, str) and re.fullmatch('/root/[A-Za-z0-9_]+', root), 'Exact product root required')
    rows = proof.get('members')
    require(isinstance(rows, list) and 1 <= len(rows) <= 3, 'Bounded actual member set required')
    by_path = {row['agent_path']: row for row in rows}
    require(len(by_path) == len(rows) and root in by_path and set(by_path) == set(sources),
            'Exact all-member source set required')
    require(len({row['native_session_id'] for row in rows}) == len(rows), 'Member UUID reused')
    for path, row in by_path.items():
        require(path == root or path in {root + '/worker1', root + '/worker2'}, 'Unregistered descendant')
        raw = sources[path]
        require(isinstance(raw, bytes) and raw.endswith(b'\n')
                and len(raw) == row['raw_bytes'] and original.core.digest(raw) == row['raw_sha256'],
                'Complete original allocation prefix required')
        parent = proof['coordinator_native_id'] if path == root else by_path[root]['native_session_id']
        _, header = membership.original.source(raw, path, parent)
        require(header['id'] == row['native_session_id'], 'Allocation UUID/source changed')
    return by_path


def commit(config, proof, parent_raw, sources, now):
    require(type(now) in (int, float) and math.isfinite(now)
            and type(config['started_at']) in (int, float) and math.isfinite(config['started_at'])
            and type(config['deadline']) in (int, float) and math.isfinite(config['deadline'])
            and config['deadline'] == config['started_at'] + 1200 and now >= config['deadline'],
            'Commit only at the original deadline')
    require(config['model'] == 'gpt-6.1-sol' and config['effort'] == 'medium'
            and proof['configuration_sha256'] == membership.registry.sha(config), 'Original configuration required')
    rows = members(proof, sources)
    require(parent_raw.endswith(b'\n'), 'Complete coordinator prefix required')
    _, parent = membership.original.source(parent_raw, '/root')
    require(parent['id'] == proof['coordinator_native_id'], 'Original controller required')
    return {'run_id': config['run_id'], 'configuration_sha256': proof['configuration_sha256'],
            'original_deadline': config['deadline'], 'committed_at': now, 'no_more_delivery': True,
            'parent_id': parent['id'], 'root_path': proof['root_path'],
            'parent_prefix_bytes': len(parent_raw), 'parent_prefix_sha256': original.core.digest(parent_raw),
            'member_prefixes': {path: {'native_session_id': row['native_session_id'],
                                     'bytes': len(sources[path]), 'sha256': original.core.digest(sources[path])}
                                for path, row in rows.items()}}


def verify(config, fresh_proof, committed, committed_parent, committed_sources, parent_raw, sources):
    expected = commit(config, fresh_proof, parent_raw, sources, committed['committed_at'])
    require(committed.get('no_more_delivery') is True
            and committed['run_id'] == expected['run_id']
            and committed['configuration_sha256'] == expected['configuration_sha256']
            and committed['original_deadline'] == expected['original_deadline']
            and committed['parent_id'] == expected['parent_id']
            and committed['root_path'] == expected['root_path']
            and set(committed['member_prefixes']) == set(expected['member_prefixes']) == set(committed_sources),
            'Committed original family changed')
    require(len(committed_parent) == committed['parent_prefix_bytes']
            and original.core.digest(committed_parent) == committed['parent_prefix_sha256']
            and parent_raw.startswith(committed_parent), 'Coordinator commitment prefix changed')
    for path, pin in committed['member_prefixes'].items():
        require(pin['native_session_id'] == expected['member_prefixes'][path]['native_session_id']
                and len(committed_sources[path]) == pin['bytes']
                and original.core.digest(committed_sources[path]) == pin['sha256']
                and sources[path].startswith(committed_sources[path]), 'Member commitment prefix changed')
    aliases = {alias for path in sources for alias in (path, path.rsplit('/', 1)[-1], path.removeprefix('/root/'))}
    for path, before, current in [('/root', committed_parent, parent_raw)] + [
            (path, committed_sources[path], sources[path]) for path in sources]:
        suffix_events = original.core.parse(current[len(before):]) if len(current) > len(before) else []
        for event in suffix_events:
            payload = event['payload']
            if payload.get('type') != 'function_call':
                continue
            if original.core.route(payload, 'collaboration', 'spawn_agent'):
                raise ValueError('Allocation after whole-family commitment')
            if any(original.core.route(payload, 'collaboration', name) for name in ('send_message', 'followup_task')):
                args = original.core.decode(payload['arguments'])
                target = args.get('target')
                require(isinstance(target, str) and target.startswith('/'), 'Ambiguous postcommit delivery')
                require(target not in aliases and not target.startswith(committed['root_path'] + '/'),
                        'Delivery after whole-family commitment')
    authority = {path: original.authority(parent_raw, {'parent_thread_id': committed['parent_id'],
                                                      'agent_path': path}, config['deadline'])
                 for path in sources}
    require(len({row['terminal_poll_call_id'] for row in authority.values()}) == 1,
            'Same latest whole-family inventory required')
    events = original.core.parse(parent_raw)
    inventory_id = next(iter(authority.values()))['terminal_poll_call_id']
    receipts = [event for event in events if event['payload'].get('type') == 'function_call_output'
                and event['payload'].get('call_id') == inventory_id]
    require(len(receipts) == 1, 'Unique current inventory receipt required')
    inventory = original.core.decode(receipts[0]['payload']['output'])
    descendants = {row['agent_name'] for row in inventory['agents']
                   if row['agent_name'] == committed['root_path']
                   or row['agent_name'].startswith(committed['root_path'] + '/')}
    require(descendants <= set(sources), 'Unbound current descendant prevents cleanup')
    interrupt_ids = {row['interrupt_call_id'] for row in authority.values()}
    suffix = original.core.parse(parent_raw[len(committed_parent):])
    actual_interrupts = {event['payload'].get('call_id') for event in suffix
                         if event['payload'].get('type') == 'function_call'
                         and original.core.route(event['payload'], 'collaboration', 'interrupt_agent')
                         and original.core.instant(event['timestamp']).timestamp() >= committed['committed_at']}
    require(interrupt_ids <= actual_interrupts, 'Every bound interruption must follow commitment')
    return {'member_authority': authority, 'whole_family_interruption_checks_pass': True,
            'cleanup_authorized': False, 'actual_native_control_qualified': False,
            'comparison_admitted': False, 'superiority_proven': False}
