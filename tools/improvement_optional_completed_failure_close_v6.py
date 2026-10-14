"""Prospective preservation/cleanup of normally completed optional failures.

No actor dispatch, interruption, grading or comparison admission. Genuine
interrupted or unresolved members remain pending with owned resources retained.
Original coordinator must stop all further member deliveries before calling.
Complete coordinator tool-return appends are reverified against the same binding.
"""
import hashlib
from pathlib import Path
import time

from collect import find_session
import improvement_optional_comparison_inputs_v6 as inputs
import improvement_optional_completed_failure_gate_v1 as gate
import improvement_optional_native_close_v4 as original
import improvement_optional_native_dispatch_v4 as native_dispatch


def coordinator_fence(config, snapshot, rows, provision, registry_folder,
                      locators, inventory_call_id, commitment, captured_parent,
                      current_parent, sources):
    """Reverify an append without changing the original allocation/delivery binding."""
    original.require(commitment.get('parent_sha256') == hashlib.sha256(captured_parent).hexdigest()
                     and commitment.get('parent_bytes') == len(captured_parent),
                     'Original coordinator commitment changed')
    original.require(current_parent.startswith(captured_parent),
                     'Original coordinator prefix replaced or truncated')
    core = gate.original.inventory.core
    events = core.parse(current_parent)
    prefix_events = core.parse(captured_parent)
    # No postcommit actor mutation is legal, even if a caller forges an earlier
    # timestamp or targets an alias. Ordinary tool-return events remain legal.
    for event in events[len(prefix_events):]:
        payload = event['payload']
        if payload.get('type') in ('function_call', 'custom_tool_call'):
            original.require(not any(core.route(payload, 'collaboration', name)
                                     for name in ('spawn_agent', 'followup_task',
                                                  'send_message', 'interrupt_agent')),
                             'Coordinator actor activity after terminal authority')
    refreshed = {**commitment, 'parent_sha256': hashlib.sha256(current_parent).hexdigest(),
                 'parent_bytes': len(current_parent)}
    root_path = commitment['root_path']
    return gate.verify(config, snapshot['state'], rows['root']['intent'],
                       {job: dispatch['intent'] for job, dispatch in rows.items() if job != 'root'},
                       current_parent, sources[root_path],
                       {path: raw for path, raw in sources.items() if path != root_path},
                       provision, registry_folder, locators, inventory_call_id, refreshed)


def close(row, coordinator_source, inventory_call_id, first_error):
    inputs.row_valid(row)
    original.require(isinstance(first_error, dict) and set(first_error) == {'type', 'message'}
                     and all(isinstance(value, str) and value for value in first_error.values()),
                     'Preserve the original failure, not a replacement diagnosis')
    folder = inputs.ROOT / 'runtime' / row['run_id']
    output = folder / 'completed-failure-close-v6'
    output.mkdir()  # An unsuccessful original close remains immutable.
    record = {'row': row, 'first_error': first_error, 'status': 'awaiting_terminal_authority',
              'software_pass': None, 'owned_cleanup_verified': False, 'usage': None,
              'interrupted_branch_qualified': False, 'comparison_admitted': False,
              'superiority_proven': False, 'started_at': time.time()}
    original.atomic_json(output / 'intent.json', record, exclusive=True)
    try:
        state = original.runtime.load(folder)
        snapshot = gate.original.membership.reservation_prefix(folder / 'registry')
        config = snapshot['state']['configuration']
        dispatch_config_raw = original.broker.original(folder / 'native-dispatch/configuration.json')
        dispatch_config = gate.original.inventory.decoded(dispatch_config_raw)
        original.require(dispatch_config['root_path'] == row['actor_path']
                         and dispatch_config['run_id'] == config['run_id']
                         and dispatch_config['configuration_sha256'] == original.runtime.registry.sha(config)
                         and dispatch_config['runtime_configuration_sha256'] == native_dispatch.runtime_identity(folder, config),
                         'Original dispatch must bind this exact comparison row')
        original.preserve_raw(output, 'dispatch-configuration.json', dispatch_config_raw)
        original.require(config['run_id'] == state['run_id']
                         and config['started_at'] == state['started_at']
                         and config['deadline'] == state['deadline']
                         and config['case_id'] == row['case_id']
                         and config['condition'] == row['condition'], 'Exact original allocation required')
        record['original_started_at'] = state['started_at']
        record['original_deadline'] = state['deadline']
        rows = {}
        dispatch_raws = {}
        intent_names = sorted(path.name for path in (folder / 'native-dispatch/intents').iterdir())
        for job in ['root', *snapshot['state']['workers']]:
            path = folder / 'native-dispatch/intents' / (job + '.json')
            if path.exists():
                dispatch_raws[job] = original.broker.original(path)
                rows[job] = gate.original.inventory.decoded(dispatch_raws[job])
        original.atomic_json(output / 'dispatch-inputs.json', {'snapshot': snapshot['state'], 'rows': rows}, exclusive=True)
        sources, locators = {}, {}
        for job, dispatch in rows.items():
            actor_path = dispatch['intent']['agent_path']
            locator = find_session(actor_path)
            raw = original.capture(locator, 256 * 1024 * 1024)
            original.preserve_raw(output, job + '.jsonl', raw)
            sources[actor_path] = raw
            locators[actor_path] = str(locator)
        parent = original.capture(coordinator_source, 256 * 1024 * 1024)
        original.preserve_raw(output, 'coordinator.jsonl', parent)
        original.require(parent.endswith(b'\n'), 'Complete original coordinator prefix required')
        root_path = rows['root']['intent']['agent_path']
        parent_id = gate.original.inventory.core.parse(parent)[0]['payload']['id']
        original.require(root_path == row['actor_path'] == dispatch_config['root_path']
                         and parent_id == dispatch_config['coordinator_id'],
                         'Original actor/controller association changed')
        commitment = {'parent_id': parent_id, 'root_path': root_path,
                      'member_paths': sorted(sources), 'inventory_call_id': inventory_call_id,
                      'parent_sha256': hashlib.sha256(parent).hexdigest(), 'parent_bytes': len(parent),
                      'no_more_delivery': True}
        original.atomic_json(output / 'coordinator-authority.json', commitment, exclusive=True)
        provision = {'run_id': config['run_id'], 'configuration_sha256': original.runtime.registry.sha(config),
                     'jobs': {job: dispatch['provision'] for job, dispatch in rows.items()}}
        proof = gate.verify(config, snapshot['state'], rows['root']['intent'],
                            {job: dispatch['intent'] for job, dispatch in rows.items() if job != 'root'},
                            parent, sources[root_path], {path: raw for path, raw in sources.items() if path != root_path},
                            provision, folder / 'registry', locators, inventory_call_id, commitment)
        record['usage'] = proof['usage']
        original.atomic_json(output / 'terminal-proof.json', proof, exclusive=True)
        def member_dispatch_fence():
            original.require(all(original.capture(locators[path], 256 * 1024 * 1024) == raw
                                 for path, raw in sources.items()), 'Original member appended after authority')
            current = gate.original.membership.reservation_prefix(folder / 'registry')
            original.require(current == snapshot, 'Original registry changed after authority')
            original.require(original.broker.original(folder / 'native-dispatch/configuration.json')
                             == dispatch_config_raw, 'Original dispatch configuration changed after authority')
            original.require(sorted(path.name for path in (folder / 'native-dispatch/intents').iterdir())
                             == intent_names and all(original.broker.original(
                                 folder / 'native-dispatch/intents' / (job + '.json')) == raw
                                 for job, raw in dispatch_raws.items()),
                             'Original dispatch intents changed after authority')
        def fence():
            member_dispatch_fence()
            current_parent = original.capture(coordinator_source, 256 * 1024 * 1024)
            current_proof = coordinator_fence(config, snapshot, rows, provision, folder / 'registry',
                                              locators, inventory_call_id, commitment, parent,
                                              current_parent, sources)
            member_dispatch_fence()
            number = len(list(output.glob('fence-*-proof.json'))) + 1
            original.preserve_raw(output, f'fence-{number}-coordinator.jsonl', current_parent)
            original.atomic_json(output / f'fence-{number}-proof.json', current_proof, exclusive=True)
        fence()
        original.runtime.failure(folder, ValueError(first_error['message']))
        cleaned = original.runtime.cleanup(folder)
        fence()
        record['owned_cleanup_verified'] = bool(cleaned['jobs']) and all(
            job['status'] == 'removed' for job in cleaned['jobs'].values())
        original.require(record['owned_cleanup_verified'], 'Owned preservation/removal incomplete')
        original.atomic_json(folder / 'native-observer/stop.json', {
            'reason': 'coordinator_stop', 'root_path': root_path, 'parent_id': parent_id}, exclusive=True)
        record['status'] = 'preserved_completed_failure'
    except BaseException as error:
        record['closure_error'] = {'type': type(error).__name__, 'message': str(error)}
        if 'proof' in locals():
            record['status'] = 'closure_incomplete'
    record['finished_at'] = time.time()
    if 'original_started_at' in record:
        record['whole_observed_seconds'] = record['finished_at'] - record['original_started_at']
    original.atomic_json(output / 'outcome.json', record, exclusive=True)
    return record
