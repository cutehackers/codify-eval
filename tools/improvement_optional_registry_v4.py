"""Prospective optional-member intents and leases, not native qualification.

The future broker must reconcile actual spawn/native/container records against
these intents. This ledger alone cannot prove actor absence, terminality, scope
enforcement, cost completeness or safe cleanup. No actor/container is launched.
"""
import contextlib
import fcntl
import hashlib
import json
import math
from pathlib import Path
import re
import time

import improvement_optional_inventory_v3 as strict

from improvement_software_artifacts_v3 import atomic_json, encoded, path_name


def sha(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def require(test, message):
    if not test:
        raise ValueError(message)


def validate_tree(value):
    require(isinstance(value, dict) and '.' in value, 'Typed repository tree required')
    for name, entity in value.items():
        if name != '.':
            path_name(name)
        require(isinstance(entity, dict), 'Typed entity required')
        kind = entity.get('kind')
        require(kind in ('file', 'directory'), 'Nonregular entity denied')
        require(type(entity.get('mode')) is int and 0 <= entity['mode'] <= 0o7777,
                'Invalid permission mode')
        require(set(entity) == ({'kind', 'mode', 'sha256'} if kind == 'file'
                                else {'kind', 'mode'}), 'Unexpected entity fields')
        if kind == 'file':
            require(isinstance(entity['sha256'], str) and
                    re.fullmatch('[0-9a-f]{64}', entity['sha256']) is not None,
                    'Invalid content digest')
        require(name != '.' or kind == 'directory', 'Root must be directory')
        if name != '.':
            parent = Path(name).parent.as_posix()
            require(parent in value and value[parent].get('kind') == 'directory',
                    'Missing typed parent directory')


@contextlib.contextmanager
def locked(folder):
    with (Path(folder) / 'lock').open('a+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def create(folder, run_id, case_id, condition, started_at, initial_tree, editable_paths):
    """Must be called before root provisioning. Original time never resets."""
    require(isinstance(run_id, str) and re.fullmatch('[A-Za-z0-9_-]+', run_id), 'Invalid run id')
    require(case_id in ('O01', 'O02') and condition in ('A', 'C0', 'C16'), 'Invalid allocation')
    require(type(started_at) in (int, float) and math.isfinite(started_at)
            and 0 < started_at <= time.time(), 'Invalid original start')
    validate_tree(initial_tree)
    require(isinstance(editable_paths, list) and len(editable_paths) == 3
            and len(set(editable_paths)) == 3, 'Exactly three public editable files required')
    for name in editable_paths:
        path_name(name)
        require(name in initial_tree and initial_tree[name]['kind'] == 'file', 'Unknown editable file')
    folder = Path(folder)
    folder.mkdir()  # Exclusive namespace: failed attempts are never overwritten.
    (folder / 'events').mkdir()
    config = dict(run_id=run_id, case_id=case_id, condition=condition,
                  model='gpt-6.1-sol', effort='medium', started_at=started_at,
                  deadline=started_at + 1200, worker_cap=2, retries=0,
                  initial_tree=initial_tree, editable_paths=sorted(editable_paths),
                  native_qualified=False, comparison_eligible=False, superiority_proven=False)
    atomic_json(folder / 'configuration.json', config, exclusive=True)
    return read(folder)


def read(folder, _pending=None):
    """Replay immutable, chained events. Reservations survive ambiguous failures."""
    folder = Path(folder)
    config = strict.decoded((folder / 'configuration.json').read_bytes())
    require(config['model'] == 'gpt-6.1-sol' and config['effort'] == 'medium'
            and config['deadline'] == config['started_at'] + 1200
            and type(config['worker_cap']) is int and config['worker_cap'] == 2
            and type(config['retries']) is int and config['retries'] == 0,
            'Registry contract changed')
    validate_tree(config['initial_tree'])
    state = dict(configuration=config, configuration_sha256=sha(config),
                 workers={}, active_leases={}, event_count=0, head_sha256=sha(config))
    events = []
    for number, path in enumerate(sorted((folder / 'events').iterdir())):
        require(path.name == f'{number:04d}.json' and path.is_file() and not path.is_symlink(),
                'Ledger sequence/entity mismatch')
        events.append(strict.decoded(path.read_bytes()))
    if _pending is not None:
        events.append(_pending)
    previous_at = config['started_at']
    for number, event in enumerate(events):
        require(type(event['number']) is int and event['number'] == number and event['previous_sha256'] == state['head_sha256'],
                'Ledger chain mismatch')
        require(event['configuration_sha256'] == state['configuration_sha256'], 'Configuration drift')
        require(type(event['at']) in (int, float) and math.isfinite(event['at'])
                and event['at'] >= previous_at, 'Invalid/backward event clock')
        previous_at = event['at']
        operation = event['operation']
        require('integration_release' not in state, 'No allocations, replacement or second release after final integration')
        if operation == 'reserve':
            row = event['worker']
            slot = f'worker{len(state["workers"]) + 1}'
            require(len(state['workers']) < 2 and row['slot'] == slot, 'Cumulative worker cap exceeded')
            require(config['started_at'] <= event['at'] < config['deadline'], 'Reservation outside original clock')
            validate_tree(row['snapshot'])
            require(row['snapshot_sha256'] == sha(row['snapshot']), 'Snapshot drift')
            require(row['mode'] in ('write', 'review') and isinstance(row['goal'], str)
                    and row['goal'].strip(), 'Invalid worker goal/mode')
            scope = row['scope']
            require(isinstance(scope, list) and scope == sorted(set(scope))
                    and set(scope) <= set(config['editable_paths']), 'Invalid worker scope')
            require(bool(scope) if row['mode'] == 'write' else not scope, 'Review workers cannot lease writes')
            require(not set(scope) & set(state['active_leases']), 'Overlapping worker leases')
            protected = set(config['initial_tree']) - set(config['editable_paths'])
            require(set(row['snapshot']) == set(config['initial_tree'])
                    and all(row['snapshot'][p] == config['initial_tree'][p] for p in protected),
                    'Protected tree drift')
            require(all(row['snapshot'][p]['kind'] == 'file' and
                        row['snapshot'][p]['mode'] == config['initial_tree'][p]['mode']
                        for p in config['editable_paths']), 'Editable entity kind/mode drift')
            check_root_changes(state, row['snapshot'])
            state['workers'][slot] = dict(row, status='reserved', errors=[])
            state['active_leases'].update({name: slot for name in scope})
        elif operation == 'allocation_error':
            row = state['workers'].get(event['slot'])
            require(row is not None, 'Unknown failed allocation')
            require(isinstance(event['error'], dict) and
                    set(event['error']) == {'type', 'message'} and
                    all(isinstance(v, str) and v for v in event['error'].values()), 'Invalid error')
            row['errors'].append(event['error'])
            row['status'] = 'allocation_unknown_pending_reconciliation'
            # Neither absence nor stopped-native proof follows from an exception.
            # Keep the slot consumed and lease held for the qualified broker.
        elif operation == 'integration_release':
            require(config['started_at'] <= event['at'] < config['deadline'], 'Release outside original clock')
            expected_fields={'number','previous_sha256','configuration_sha256','at','operation','transaction','original_intent','commitment'}
            require(set(event)==expected_fields, 'Exact release event required')
            value=verified_install(folder,state,event['transaction'],event['original_intent'],event['commitment'],event['at'])
            state['active_leases']={}
            state['integration_release']={'event_number':number,'transaction':event['transaction'],
                'after_tree_sha256':sha(value['expected_after_inventory']['source_entities']),
                'native_qualified':False,'comparison_eligible':False}
        else:
            raise ValueError('Unknown ledger operation')
        state['event_count'] += 1
        state['head_sha256'] = sha(event)
    return state


def append(folder, state, operation, **values):
    event = dict(number=state['event_count'], previous_sha256=state['head_sha256'],
                 configuration_sha256=state['configuration_sha256'], at=time.time(),
                 operation=operation, **values)
    # Validate the exact event (including its later clock sample) before commit.
    read(folder, _pending=event)
    atomic_json(Path(folder) / 'events' / f'{state["event_count"]:04d}.json', event, exclusive=True)
    return read(folder)


def reserve_worker(folder, goal, scope, snapshot, mode='write'):
    with locked(folder):
        state = read(folder); config = state['configuration']
        require(config['started_at'] <= time.time() < config['deadline'], 'Original deadline exhausted')
        require(len(state['workers']) < 2, 'No replacement or third worker')
        require(isinstance(goal, str) and goal.strip() and mode in ('write', 'review'), 'Invalid goal/mode')
        require(isinstance(scope, list) and all(isinstance(p, str) for p in scope)
                and len(set(scope)) == len(scope), 'Invalid scope')
        require(set(scope) <= set(config['editable_paths']) and
                (bool(scope) if mode == 'write' else not scope), 'Scope violates mode/contract')
        require(not set(scope) & set(state['active_leases']), 'Overlapping worker leases')
        validate_tree(snapshot)
        require(set(snapshot) == set(config['initial_tree']) and all(
                snapshot[p] == entity for p, entity in config['initial_tree'].items()
                if p not in config['editable_paths']), 'Protected tree drift')
        require(all(snapshot[p]['kind'] == 'file' and snapshot[p]['mode'] ==
                    config['initial_tree'][p]['mode'] for p in config['editable_paths']), 'Editable kind/mode drift')
        check_root_changes(state, snapshot)
        return append(folder, state, 'reserve', worker=dict(slot=f'worker{len(state["workers"]) + 1}',
                      goal=goal, scope=sorted(scope), mode=mode, snapshot=snapshot, snapshot_sha256=sha(snapshot)))


def allocation_error(folder, slot, error):
    with locked(folder):
        state = read(folder)
        require(slot in state['workers'] and isinstance(error, Exception), 'Unknown allocation/error')
        return append(folder, state, 'allocation_error', slot=slot,
                      error={'type':type(error).__name__, 'message':str(error) or type(error).__name__})


def check_root_changes(state, current_tree):
    """Post-command guard only. Does not claim a universal filesystem firewall."""
    validate_tree(current_tree)
    config = state['configuration']; base = config['initial_tree']
    require(set(current_tree) == set(base), 'Tree additions/removals forbidden')
    for name, entity in base.items():
        if name not in config['editable_paths']:
            require(current_tree[name] == entity, 'Protected entity changed')
        else:
            require(current_tree[name]['kind'] == entity['kind']
                    and current_tree[name]['mode'] == entity['mode'], 'Editable kind/mode changed')
            slot = state['active_leases'].get(name)
            if slot:
                require(current_tree[name] == state['workers'][slot]['snapshot'][name], 'Root changed leased file')
    return True


def verified_install(folder, state, transaction_reference, original_reference, commitment_reference, release_at):
    """Pinned raw install proof only. Native fences remain caller authority."""
    import improvement_optional_checkout_artifacts_v2 as checkout
    import improvement_optional_artifacts_v2 as artifacts
    references = (transaction_reference, original_reference, commitment_reference)
    for reference in references:
        require(isinstance(reference, dict) and set(reference) == {'path', 'kind', 'mode', 'bytes', 'sha256'}
                and type(reference['mode']) is int and type(reference['bytes']) is int,
                'Exact typed install proof required')
        p = Path(reference['path'])
        require(p.is_absolute() and not p.is_symlink() and checkout.file_pin(p) == reference,
                'Install proof pin drift')
    path = Path(transaction_reference['path'])
    require(original_reference['path'] == str(path.with_name(path.stem + '.intent.json'))
            and commitment_reference['path'] == str(path.with_name(path.stem + '.commit.json')),
            'Wrong install proof namespace')
    original = strict.decoded(Path(original_reference['path']).read_bytes())
    current = strict.decoded(path.read_bytes())
    commitment = strict.decoded(Path(commitment_reference['path']).read_bytes())
    require(original['state'] == 'intent'
            and current['state'] == 'raw_files_integrated_pending_lease_native_runtime_and_verification'
            and set(current) == set(original)
            and all(encoded(current[k]) == encoded(v) for k, v in original.items() if k != 'state'),
            'Install status differs from original intent')
    require(encoded(original['registry_state']) == encoded(state)
            and original['registry_folder'] == str(Path(folder).resolve())
            and original['configuration_sha256'] == state['configuration_sha256'], 'Wrong original lease state')
    require(set(commitment) == {'original_intent', 'expected_after_sha256', 'committed_at', 'native_qualified'}
            and commitment['original_intent'] == original_reference
            and commitment['expected_after_sha256'] == sha(original['expected_after_inventory'])
            and commitment['native_qualified'] is False
            and type(commitment['committed_at']) in (int, float) and math.isfinite(commitment['committed_at'])
            and state['configuration']['started_at'] <= commitment['committed_at'] < state['configuration']['deadline'],
            'Original terminal commitment missing')
    require(type(original['started_at']) in (int, float) and math.isfinite(original['started_at'])
            and type(release_at) in (int, float) and math.isfinite(release_at)
            and state['configuration']['started_at'] <= original['started_at']
            <= commitment['committed_at'] <= release_at < state['configuration']['deadline'],
            'Release chronology predates original install or terminal commitment')
    before = original['before_inventory']['source_entities']; after = original['expected_after_inventory']['source_entities']
    check_root_changes(state, before); validate_tree(after)
    choices = original['decisions']; require(isinstance(choices, list) and len(choices) == len(state['workers']),
                                         'Every reserved worker decision required')
    payloads = {}; seen = set()
    for reference in choices:
        decision = artifacts.pinned(reference); slot = decision.get('slot')
        require(slot in state['workers'] and slot not in seen
                and reference == artifacts.pin(Path(folder) / 'decisions' / (slot + '.json')),
                'Original canonical worker decision required')
        require(set(decision) == {'configuration_sha256', 'slot', 'artifact', 'view', 'decision', 'reason',
                'actual_native_decision_verified', 'comparison_eligible'}
                and decision['configuration_sha256'] == state['configuration_sha256']
                and decision['decision'] in ('accept', 'reject') and isinstance(decision['reason'], str)
                and decision['reason'].strip() and decision['actual_native_decision_verified'] is False
                and decision['comparison_eligible'] is False, 'Invalid decision receipt')
        value = artifacts.artifact(state, decision['artifact']); view = artifacts.pinned(decision['view'])
        require(value['slot'] == slot and view['slot'] == slot and view['configuration_sha256'] == state['configuration_sha256']
                and view['artifact'] == decision['artifact'] and view['displayed_payloads'] == value['payloads']
                and view['displayed_findings'] == value['findings'] and view['actual_native_view_verified'] is False,
                'Original exact contribution view required')
        seen.add(slot)
        if decision['decision'] == 'accept':
            row = state['workers'][slot]
            require(all(before[p] == row['snapshot'][p] for p in row['scope']), 'Accepted original base drift')
            require(not set(payloads) & set(value['payloads']), 'Contribution overlap')
            payloads.update({p: bytes.fromhex(v['hex']) for p, v in value['payloads'].items()})
    require(seen == set(state['workers']) and payloads == {p: bytes.fromhex(v) for p, v in original['after_payloads'].items()},
            'Raw install lacks every canonical contribution decision')
    expected = {**before, **{p: {'kind': 'file', 'mode': before[p]['mode'],
                'sha256': hashlib.sha256(raw).hexdigest()} for p, raw in payloads.items()}}
    require(after == expected, 'Released source tree differs from approved contribution bytes')
    require(all(original.get(k) is False for k in ('native_qualified', 'runtime_qualified', 'leases_released',
                'comparison_eligible', 'superiority_proven')), 'Filesystem install cannot grant native authority')
    return original


def release_after_install(folder, transaction_reference, original_reference, commitment_reference):
    """Final release, not slot reuse. Caller must hold stopped-root/native fences."""
    import improvement_optional_source_v2 as source
    with locked(folder):
        state = read(folder); require('integration_release' not in state, 'No repeat final integration')
        value = verified_install(folder, state, transaction_reference, original_reference, commitment_reference, time.time())
        require(source.inventory(value['root'], state['configuration']['deadline']) == value['expected_after_inventory'],
                'Raw root does not match committed complete inventory')
        return append(folder, state, 'integration_release', transaction=transaction_reference,
                      original_intent=original_reference, commitment=commitment_reference)
