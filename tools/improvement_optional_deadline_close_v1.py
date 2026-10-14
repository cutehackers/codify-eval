"""Prospective same-family deadline preservation, with external native control.

The original coordinator commits before interrupting every actual member with
native tools. This helper never dispatches or interrupts actors. Caller source
freeze, observer qualification and genuine native control remain required.
"""
import json
from pathlib import Path
import time

from collect import find_session
import improvement_optional_comparison_inputs_v2 as inputs
import improvement_optional_deadline_members_v1 as aggregate
import improvement_optional_native_close_v4 as original
import improvement_optional_native_dispatch_v4 as dispatch

CONTROL = 'native-optional-deadline-control-v1'
CONTROL_ACTOR = '/root/native_optional_deadline_control_v1'


def identity(folder):
    folder = Path(folder).resolve()
    original.require(folder.parent == inputs.ROOT / 'runtime', 'Exact owned runtime parent required')
    if folder.name == CONTROL:
        return {'case_id': 'O01', 'condition': 'A', 'actor_path': CONTROL_ACTOR}
    rows = [row for row in inputs.sequence() if row['run_id'] == folder.name]
    original.require(len(rows) == 1, 'Registered original namespace required')
    return rows[0]


def capture_family(folder, coordinator_source, destination):
    row = identity(folder)
    snapshot = aggregate.membership.reservation_prefix(folder / 'registry')
    config = snapshot['state']['configuration']
    original.require(config['case_id'] == row['case_id'] and config['condition'] == row['condition'],
                     'Original case/condition changed')
    dispatch_raw = original.broker.original(folder / 'native-dispatch/configuration.json')
    dispatch_config = original.audit.inventory.decoded(dispatch_raw)
    original.require(dispatch_config['root_path'] == row['actor_path']
                     and dispatch_config['run_id'] == config['run_id']
                     and dispatch_config['configuration_sha256'] == aggregate.membership.registry.sha(config)
                     and dispatch_config['runtime_configuration_sha256'] == dispatch.runtime_identity(folder, config),
                     'Original runtime/dispatch association required')
    original.preserve_raw(destination, 'dispatch-configuration.json', dispatch_raw)
    rows, sources, locators = {}, {}, {}
    for job in ['root', *snapshot['state']['workers']]:
        path = folder / 'native-dispatch/intents' / (job + '.json')
        if path.exists():
            value = original.audit.inventory.decoded(original.broker.original(path))
            rows[job] = value
            locator = find_session(value['intent']['agent_path'])
            raw = original.capture(locator, 256 * 1024 * 1024)
            original.preserve_raw(destination, job + '.jsonl', raw)
            sources[value['intent']['agent_path']] = raw
            locators[value['intent']['agent_path']] = str(locator)
    parent = original.capture(coordinator_source, 256 * 1024 * 1024)
    original.preserve_raw(destination, 'coordinator.jsonl', parent)
    original.require(parent.endswith(b'\n'), 'Complete original coordinator prefix required')
    parent_id = aggregate.original.core.parse(parent)[0]['payload']['id']
    original.require(parent_id == dispatch_config['coordinator_id']
                     and rows['root']['intent']['agent_path'] == row['actor_path'], 'Exact actor/controller required')
    provision = {'run_id': config['run_id'], 'configuration_sha256': aggregate.membership.registry.sha(config),
                 'jobs': {job: value['provision'] for job, value in rows.items()}}
    proof = aggregate.membership.reconcile_membership(
        config, snapshot['state'], rows['root']['intent'],
        {job: value['intent'] for job, value in rows.items() if job != 'root'},
        parent, sources[row['actor_path']], {path: raw for path, raw in sources.items() if path != row['actor_path']},
        provision, folder / 'registry')
    original.atomic_json(destination / 'allocation-proof.json', proof, exclusive=True)
    original.atomic_json(destination / 'locators.json', locators, exclusive=True)
    return config, snapshot, proof, parent, sources, locators


def commit(folder, coordinator_source):
    folder = Path(folder).resolve(); identity(folder)
    output = folder / 'deadline-close-v1'
    output.mkdir()  # Same original attempt; no overwritten commitment.
    original.atomic_json(output / 'intent.json', {'started_at': time.time(),
                         'first_error': {'type': 'SharedTrajectoryDeadline', 'message': 'Original 1200-second deadline reached'},
                         'software_pass': None, 'comparison_admitted': False}, exclusive=True)
    try:
        config, _, proof, parent, sources, _ = capture_family(folder, coordinator_source, output)
        value = aggregate.commit(config, proof, parent, sources, time.time())
        original.atomic_json(output / 'commitment.json', value, exclusive=True)
        return value
    except BaseException as error:
        original.atomic_json(output / 'commit-error.json', {'type': type(error).__name__, 'message': str(error)}, exclusive=True)
        raise


def close(folder, coordinator_source):
    folder = Path(folder).resolve(); row = identity(folder)
    output = folder / 'deadline-close-v1'
    committed = original.audit.inventory.decoded(original.broker.original(output / 'commitment.json'))
    current = output / 'current'; current.mkdir()
    record = {'software_pass': None, 'owned_cleanup_verified': False, 'status': 'awaiting_terminal_authority',
              'usage': None, 'comparison_admitted': False, 'superiority_proven': False}
    try:
        config, snapshot, proof, parent, sources, locators = capture_family(folder, coordinator_source, current)
        committed_parent = original.broker.original(output / 'coordinator.jsonl')
        committed_sources = {path: original.broker.original(output / ('root.jsonl' if path == row['actor_path']
                             else path.rsplit('/', 1)[-1] + '.jsonl')) for path in committed['member_prefixes']}
        authority = aggregate.verify(config, proof, committed, committed_parent, committed_sources, parent, sources)
        original.atomic_json(current / 'terminal-authority.json', authority, exclusive=True)
        record['usage'] = original.audit.cost.usage_members(proof, sources, locators)
        def fence():
            original.require(all(original.capture(locators[path], 256 * 1024 * 1024) == raw
                                 for path, raw in sources.items()), 'Member appended after interruption authority')
            original.require(aggregate.membership.reservation_prefix(folder / 'registry') == snapshot,
                             'Registry changed after interruption authority')
            original.require(original.capture(coordinator_source, 256 * 1024 * 1024) == parent,
                             'Coordinator changed during synchronous closure')
            original.require(original.broker.original(folder / 'native-dispatch/configuration.json')
                             == original.broker.original(current / 'dispatch-configuration.json'),
                             'Original dispatch changed after interruption authority')
        fence()
        original.runtime.failure(folder, TimeoutError('Original 1200-second deadline reached'))
        cleaned = original.runtime.cleanup(folder)
        fence()
        record['owned_cleanup_verified'] = bool(cleaned['jobs']) and all(
            job['status'] == 'removed' for job in cleaned['jobs'].values())
        original.require(record['owned_cleanup_verified'], 'Owned deadline preservation/removal incomplete')
        record['status'] = 'preserved_interrupted_failure'
        record['original_started_at'] = config['started_at']
        record['original_deadline'] = config['deadline']
    except BaseException as error:
        record['closure_error'] = {'type': type(error).__name__, 'message': str(error)}
        if 'authority' in locals(): record['status'] = 'closure_incomplete'
    record['finished_at'] = time.time()
    if 'config' in locals(): record['whole_observed_seconds'] = record['finished_at'] - config['started_at']
    original.atomic_json(current / 'outcome.json', record, exclusive=True)
    return record
