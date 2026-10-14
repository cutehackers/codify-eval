"""Pure optional native allocation joins, never a broker or cleanup authority.

Inputs must be authenticated by the future coordinator: replayed registry state,
pre-dispatch intents, real provision ledger and atomic original native prefixes.
Every reserved slot remains consumed. Missing allocation evidence stays unknown.
Full bootstrap/route/turn/delivery/current-inventory/fence audits are separate.
"""
import json
import re
import math
import copy

import improvement_q01_dialogue_core_v1 as core
import improvement_optional_inventory_v3 as inventory
import improvement_optional_registry_v2 as registry
import improvement_software_native_binding_v2 as native

require = core.require
INTENT_FIELDS = {'job', 'agent_path', 'at', 'public_request_sha256',
                 'configuration_sha256', 'reservation_worker_sha256'}
WORKER_FIELDS = ('slot', 'goal', 'scope', 'mode', 'snapshot', 'snapshot_sha256')


def digest(value):
    return registry.sha(value)


def worker_digest(row):
    return digest({k: row[k] for k in WORKER_FIELDS})


def source(raw, expected_path, parent_id=None):
    events = core.parse(raw)
    inventory.finite(events)
    headers = [e for e in events if e.get('type') == 'session_meta']
    require(len(headers) == 1 and events[0] == headers[0], 'Ambiguous native header')
    header = headers[0]['payload']
    require(isinstance(header.get('id'), str) and bool(header['id']), 'Native UUID required')
    require(header.get('agent_path') == expected_path if expected_path != '/root'
            else header.get('agent_path') in (None, '/root'), 'Native path conflict')
    if parent_id is None:
        require(not header.get('parent_thread_id'), 'Original coordinator required')
    else:
        nested = header.get('source', {}).get('subagent', {}).get('thread_spawn', {})
        require(header.get('parent_thread_id') == parent_id and nested.get('parent_thread_id') == parent_id
                and nested.get('agent_path') == expected_path, 'Native parent/source conflict')
    contexts = [e['payload'] for e in events if e.get('type') == 'turn_context']
    if expected_path != '/root':
        require(bool(contexts), 'Actual member context required')
    for context in contexts:
        require(context.get('model') == 'gpt-6.1-sol' and context.get('effort') == 'medium',
                'Actual model or reasoning changed')
        settings = context.get('collaboration_mode', {}).get('settings')
        if settings is not None:
            require(settings.get('model') == 'gpt-6.1-sol' and settings.get('reasoning_effort') == 'medium',
                    'Conflicting collaboration settings')
    return events, header


def operations(events):
    """All actual collaboration spawn calls, including unknown/unreceipted ones."""
    calls, outputs = {}, {}
    for index, event in enumerate(events):
        p = event['payload']; kind = p.get('type'); cid = p.get('call_id')
        if kind in ('function_call', 'custom_tool_call'):
            require(event.get('type') == 'response_item' and isinstance(cid, str) and cid
                    and cid not in calls, 'Invalid or duplicate native call')
            calls[cid] = (index, event)
        elif kind in ('function_call_output', 'custom_tool_call_output'):
            require(event.get('type') == 'response_item' and isinstance(cid, str) and cid
                    and cid in calls and cid not in outputs and calls[cid][0] < index,
                    'Orphan, duplicate or backward receipt')
            require(core.instant(calls[cid][1]['timestamp']) <= core.instant(event['timestamp']),
                    'Receipt clock reversed')
            outputs[cid] = (index, event)
    result = []
    for cid, (_, event) in calls.items():
        p = event['payload']
        if core.route(p, 'collaboration', 'spawn_agent'):
            require(p['type'] == 'function_call', 'Wrong spawn call type')
            args = inventory.decoded(p['arguments'])
            require(isinstance(args, dict), 'Malformed spawn arguments')
            result.append((cid, event, args, outputs.get(cid)))
    return result


def first_request_prefix(raw, parent_path):
    """Legacy binding sees only initial incoming request; full source is retained.

    This is derived, never caller-selectable. Later approved turns need a separate
    full lifecycle/delivery audit; no record is erased from the resulting proof.
    """
    prefix = bytearray()
    for line in raw.splitlines(keepends=True):
        prefix.extend(line); event = inventory.decoded(line)
        p = event['payload']
        if p.get('type') == 'agent_message' and p.get('author') == parent_path:
            require(event.get('type') == 'response_item', 'Wrong incoming native event kind')
            return bytes(prefix)
    raise ValueError('Initial actual parent request missing')


def intent(value, job, config, root_path, worker=None):
    require(isinstance(value, dict) and set(value) == INTENT_FIELDS, 'Exact dispatch intent required')
    path = root_path if job == 'root' else root_path + '/' + job
    require(value['job'] == job and value['agent_path'] == path, 'Dispatch role/path conflict')
    require(value['configuration_sha256'] == digest(config), 'Dispatch configuration drift')
    require(isinstance(value['public_request_sha256'], str) and
            re.fullmatch('[0-9a-f]{64}', value['public_request_sha256']), 'Public request hash required')
    at = core.instant(value['at']).timestamp()
    require(config['started_at'] <= at < config['deadline'], 'Intent outside original clock')
    require(value['reservation_worker_sha256'] == (worker_digest(worker) if worker else None),
            'Dispatch reservation/goal/scope/snapshot drift')
    return path, at


def spawn_contract(event, args, expected_path, parent_path, intent_at, config):
    require(set(args) == {'task_name', 'message', 'fork_turns', 'model', 'reasoning_effort'},
            'Unexpected native spawn arguments')
    require(args.get('task_name') == expected_path.removeprefix(parent_path + '/')
            and '/' not in args['task_name'] and args['fork_turns'] == 'none'
            and args['model'] == 'gpt-6.1-sol' and args['reasoning_effort'] == 'medium'
            and isinstance(args['message'], str) and args['message'].startswith('gAAAAA'),
            'Unqualified native spawn path/model/context/request')
    at = core.instant(event['timestamp']).timestamp()
    require(intent_at <= at < config['deadline'], 'Native allocation before intent or after original deadline')


def validate_reservations(config, supplied, raw):
    """Replay original immutable registry bytes without filesystem access."""
    require(isinstance(raw, bytes) and (not raw or raw.endswith(b'\n')), 'Complete original registry events required')
    registry.validate_tree(config['initial_tree'])
    editable = config.get('editable_paths')
    require(isinstance(editable, list) and len(editable) == 3 and all(isinstance(p, str) for p in editable)
            and len(set(editable)) == 3 and all(p in config['initial_tree'] and config['initial_tree'][p]['kind'] == 'file' for p in editable),
            'Invalid frozen editable paths')
    require(isinstance(supplied, dict) and type(supplied.get('event_count')) is int, 'Invalid replayed event count')
    events = [inventory.decoded(line) for line in raw.splitlines()]
    state = {'configuration': config, 'configuration_sha256': digest(config), 'workers': {},
             'active_leases': {}, 'event_count': 0, 'head_sha256': digest(config)}
    previous = config['started_at']; reservations = {}
    for number, event in enumerate(events):
        require(isinstance(event, dict) and type(event.get('number')) is int and event['number'] == number
                and event.get('previous_sha256') == state['head_sha256']
                and event.get('configuration_sha256') == state['configuration_sha256'], 'Registry event chain changed')
        at = event.get('at')
        require(type(at) in (int, float) and math.isfinite(at) and at >= previous, 'Registry clock changed')
        previous = at; op = event.get('operation')
        common = {'number', 'previous_sha256', 'configuration_sha256', 'at', 'operation'}
        if op == 'reserve':
            require(set(event) == common | {'worker'}, 'Unknown reserve fields')
            row = event['worker']; slot = f'worker{len(state["workers"])+1}'
            require(isinstance(row, dict) and set(row) == set(WORKER_FIELDS) and row['slot'] == slot
                    and len(state['workers']) < 2 and config['started_at'] <= at < config['deadline'],
                    'Reservation cap, slot or original clock changed')
            registry.validate_tree(row['snapshot'])
            scope = row['scope']
            require(row['snapshot_sha256'] == digest(row['snapshot']) and row['mode'] in ('write', 'review')
                    and isinstance(row['goal'], str) and row['goal'].strip()
                    and isinstance(scope, list) and all(isinstance(p, str) for p in scope)
                    and scope == sorted(set(scope)) and set(scope) <= set(config['editable_paths'])
                    and (bool(scope) if row['mode'] == 'write' else not scope)
                    and not set(scope) & set(state['active_leases']), 'Invalid reserved worker/scope')
            registry.check_root_changes(state, row['snapshot'])
            state['workers'][slot] = dict(copy.deepcopy(row), status='reserved', errors=[])
            state['active_leases'].update({p:slot for p in scope})
            reservations[slot] = {'at': at, 'event_sha256': digest(event)}
        elif op == 'allocation_error':
            require(set(event) == common | {'slot', 'error'} and event['slot'] in state['workers'],
                    'Unknown allocation error')
            error = event['error']
            require(isinstance(error, dict) and set(error) == {'type', 'message'}
                    and all(isinstance(v, str) and v for v in error.values()), 'Invalid preserved error')
            state['workers'][event['slot']]['errors'].append(copy.deepcopy(error))
            state['workers'][event['slot']]['status'] = 'allocation_unknown_pending_reconciliation'
        else:
            raise ValueError('Unknown registry event')
        state['event_count'] += 1; state['head_sha256'] = digest(event)
    require(state == supplied, 'Supplied registry state is not original event replay')
    return reservations


def reconcile_membership(config, registry_state, root_intent, worker_intents,
                         coordinator_raw, product_root_raw, member_raw_by_path, provision_ledger, registry_events_raw):
    require(isinstance(config, dict) and config.get('model') == 'gpt-6.1-sol'
            and config.get('effort') == 'medium' and type(config.get('worker_cap')) is int and config['worker_cap'] == 2
            and type(config.get('retries')) is int and config['retries'] == 0 and type(config.get('started_at')) in (int, float)
            and math.isfinite(config['started_at']) and config['started_at'] > 0
            and type(config.get('deadline')) in (int, float) and math.isfinite(config['deadline'])
            and config['deadline'] == config['started_at'] + 1200 and config['deadline']-config['started_at'] == 1200, 'Invalid frozen configuration')
    require(registry_state.get('configuration') == config and
            registry_state.get('configuration_sha256') == digest(config), 'Replayed registry configuration mismatch')
    reservations = validate_reservations(config, registry_state, registry_events_raw)
    workers = registry_state['workers']
    require(isinstance(workers, dict) and list(workers) == [f'worker{i+1}' for i in range(len(workers))]
            and len(workers) <= 2, 'Cumulative worker slots changed')
    require(isinstance(worker_intents, dict) and set(worker_intents) <= set(workers), 'Unreserved dispatch intent')
    require(isinstance(root_intent, dict) and isinstance(root_intent.get('agent_path'), str)
            and re.fullmatch('/root/[A-Za-z0-9_]+', root_intent['agent_path']), 'Immediate product root required')
    root_path, root_at = intent(root_intent, 'root', config, root_intent['agent_path'])
    expected_paths = {root_path + '/' + slot for slot in workers}
    require(isinstance(member_raw_by_path, dict) and set(member_raw_by_path) <= expected_paths,
            'Unregistered worker source cannot be excluded')
    require(isinstance(provision_ledger, dict) and set(provision_ledger) == {'run_id', 'configuration_sha256', 'jobs'}
            and provision_ledger['run_id'] == config['run_id']
            and provision_ledger['configuration_sha256'] == digest(config), 'Provision ledger origin drift')
    jobs = provision_ledger['jobs']
    require(isinstance(jobs, dict) and 'root' in jobs and set(jobs) <= {'root'} | set(workers),
            'Unknown or missing provision job')
    def prepared(job, value):
        row = jobs.get(job)
        require(isinstance(row, dict) and set(row) == {'job', 'agent_path', 'intent_sha256', 'public_request_sha256', 'status'}
                and row['job'] == job and row['agent_path'] == value['agent_path']
                and row['intent_sha256'] == digest(value)
                and row['public_request_sha256'] == value['public_request_sha256']
                and row['status'] == 'prepared', 'Unprepared or mismatched dispatch provision')
    prepared('root', root_intent)
    parents, parent = source(coordinator_raw, '/root')
    roots, root = source(product_root_raw, root_path, parent['id'])
    parent_ops = operations(parents)
    root_ops = [op for op in parent_ops if op[2].get('task_name') == root_path.removeprefix('/root/')]
    require(len(root_ops) == 1, 'Missing or duplicate product root allocation')
    spawn_contract(root_ops[0][1], root_ops[0][2], root_path, '/root', root_at, config)
    root_receipt = root_ops[0][3]
    require(root_receipt is not None and root_receipt[1]['payload'].get('type') == 'function_call_output'
            and inventory.decoded(root_receipt[1]['payload']['output']) == {'task_name':root_path},
            'Exact typed root allocation success required')
    root_join = native.binding(coordinator_raw, first_request_prefix(product_root_raw, '/root'), '/root', root_path)
    require(root_join['spawn_call_id'] == root_ops[0][0], 'Root allocation join changed')
    members = [{'job': 'root', 'agent_path': root_path, 'native_session_id': root['id'],
                'raw_sha256': core.digest(product_root_raw), 'raw_bytes': len(product_root_raw), 'binding': root_join}]
    attempts = []; pending = []; ids = {parent['id'], root['id']}
    spawns = operations(roots)
    require(len(spawns) <= 2, 'Third or replacement worker allocation')
    by_path = {}
    for op in spawns:
        task = op[2].get('task_name')
        require(isinstance(task, str) and task in workers and task in worker_intents,
                'Unregistered or unreserved actual worker spawn')
        require(task not in by_path, 'Replacement worker allocation')
        by_path[task] = op
    observed_unbound_sources = []
    for slot, row in workers.items():
        record = {'job': slot, 'registry_status': row['status'], 'registry_errors': row['errors'],
                  'reservation_worker_sha256': worker_digest(row), 'allocation_status': 'unknown'}
        value = worker_intents.get(slot); op = by_path.get(slot); path = root_path + '/' + slot
        if value is not None:
            _, at = intent(value, slot, config, root_path, row)
            require(reservations[slot]['at'] <= at, 'Worker intent before original reservation')
            record['reservation_event'] = reservations[slot]
            record['dispatch_intent_sha256'] = digest(value)
        raw = member_raw_by_path.get(path)
        if raw is not None:
            child_events, child = source(raw, path, root['id'])
            require(child['id'] not in ids, 'Native UUID reused across members')
            ids.add(child['id'])
            require(not operations(child_events), 'Nested worker allocation forbidden')
            record['observed_source'] = {'agent_path': path, 'native_session_id': child['id'],
                                         'raw_sha256': core.digest(raw), 'raw_bytes': len(raw)}
        if op is None:
            record['allocation_status'] = 'reserved_dispatch_unproven'
            pending.append(slot)
        else:
            prepared(slot, value)
            cid, event, args, receipt = op
            spawn_contract(event, args, path, root_path, at, config)
            record['spawn_call_id'] = cid
            success = False
            if receipt is not None and receipt[1]['payload'].get('type') == 'function_call_output':
                try:
                    success = inventory.decoded(receipt[1]['payload']['output']) == {'task_name': path}
                except (ValueError, TypeError):
                    success = False
            if not success:
                record['allocation_status'] = 'dispatch_outcome_unknown'
                pending.append(slot)
            elif raw is None:
                record['allocation_status'] = 'allocated_native_source_missing'
                pending.append(slot)
            else:
                joined = native.binding(product_root_raw, first_request_prefix(raw, root_path), root_path, path)
                require(joined['spawn_call_id'] == cid, 'Worker allocation join changed')
                members.append({'job': slot, 'agent_path': path, 'native_session_id': child['id'],
                                'raw_sha256': core.digest(raw), 'raw_bytes': len(raw), 'binding': joined})
                record['allocation_status'] = 'actual_allocation_joined'
        if raw is not None and record['allocation_status'] != 'actual_allocation_joined':
            observed_unbound_sources.append(record['observed_source'])
        attempts.append(record)
    return {'configuration_sha256': digest(config), 'registry_head_sha256': registry_state['head_sha256'],
            'registry_events_prefix': {'bytes':len(registry_events_raw),'sha256':core.digest(registry_events_raw)},
            'coordinator_native_id': parent['id'], 'root_path': root_path, 'members': members,
            'attempts': attempts, 'pending_allocation_slots': pending,
            'observed_unbound_sources': observed_unbound_sources,
            'provided_allocation_joins_complete': not pending,
            'coordinator_prefix': {'bytes': len(coordinator_raw), 'sha256': core.digest(coordinator_raw)},
            'historical_membership_authoritative': False, 'bootstrap_routes_qualified': False,
            'all_member_completions_proven': False, 'exclusive_delivery_enforced': False,
            'whole_cost_qualified': False, 'native_qualified': False,
            'cleanup_authorized': False, 'comparison': False, 'superiority': False}
