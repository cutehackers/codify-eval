"""Canonical contribution projection and raw Flutter checkout transaction.

Caller owns job/container/native write fences. No actor, container or delivery
authority follows from this filesystem module. Leases remain held after install
until a separately authenticated coordinator releases them.
"""
import copy
import hashlib
import os
from pathlib import Path
import stat
import time
import uuid

import improvement_optional_source_v2 as source
import improvement_optional_registry_v2 as registry
import improvement_optional_artifacts_v2 as artifacts
import improvement_optional_inventory_v3 as strict
from improvement_software_artifacts_v3 import LIMIT, atomic_json, locked, apply_files, staging_paths, encoded

require = registry.require


def payload(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        s = os.fstat(fd)
        require(stat.S_ISREG(s.st_mode) and s.st_size <= LIMIT, 'Bounded regular payload required')
        with os.fdopen(fd, 'rb', closefd=False) as stream: raw = stream.read(LIMIT + 1)
        after = os.fstat(fd)
        require(len(raw) == s.st_size and (s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns) ==
                (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Payload changed during read')
        return raw
    finally:
        os.close(fd)


def seal_checkout(repo, state, slot, baseline, export_path, artifact_path, findings='', deadline=None):
    require(slot in state['workers'], 'Unallocated worker')
    snapshot = source.inventory(repo, deadline)
    require(baseline['source_entities'] == state['workers'][slot]['snapshot'], 'Wrong prepared worker baseline')
    source.check_changes(baseline, snapshot, state['workers'][slot]['scope'])
    source.export(repo, snapshot, export_path, deadline)
    reference = artifacts.seal(state, slot, export_path, artifact_path, findings)
    require(source.inventory(repo, deadline) == snapshot, 'Checkout changed during seal')
    return {'artifact': reference, 'export': str(Path(export_path).resolve()),
            'inventory': snapshot, 'native_qualified': False, 'container_stopped_qualified': False}


def projected(before, old, new):
    after = copy.deepcopy(before)
    for name, raw in new.items():
        entity = {'kind': 'file', 'mode': before['source_entities'][name]['mode'],
                  'sha256': hashlib.sha256(raw).hexdigest()}
        after['source_entities'][name] = entity; after['all_entities'][name] = entity
    after['total_regular_bytes'] += sum(len(new[p]) - len(old[p]) for p in new)
    return after


def install(repo, state, decisions, baseline, before, journal, registry_folder,
            deadline=None, after_each=None, after_stage=None):
    repo = Path(repo).resolve(); journal = Path(journal).resolve()
    require(repo != Path(registry_folder).resolve() and repo not in Path(registry_folder).resolve().parents,
            'Registry must be outside checkout')
    with registry.locked(registry_folder), locked(repo, journal):
        artifacts.checked_state(state, registry_folder)
        source.clock(deadline)
        require(source.inventory(repo, deadline) == before, 'Raw root changed before install')
        source.check_changes(baseline, before, state['configuration']['editable_paths'])
        registry.check_root_changes(state, before['source_entities'])
        new = artifacts.selected(state, decisions, before['source_entities'], registry_folder)
        old = {p: payload(repo / p) for p in new}
        require(all(hashlib.sha256(raw).hexdigest() == before['source_entities'][p]['sha256'] for p, raw in old.items()),
                'Root payload differs from preserved snapshot')
        require(source.inventory(repo, deadline) == before, 'Root changed while preparing install')
        after = projected(before, old, new)
        transaction = journal / (uuid.uuid4().hex + '.json')
        intent = {'state': 'intent', 'root': str(repo), 'configuration_sha256': state['configuration_sha256'],
                  'before_inventory': before, 'expected_after_inventory': after,
                  'before_payloads': {p: raw.hex() for p, raw in old.items()},
                  'after_payloads': {p: raw.hex() for p, raw in new.items()},
                  'decisions': decisions, 'staging_paths': staging_paths(new, transaction),
                  'started_at': time.time(), 'native_qualified': False, 'runtime_qualified': False,
                  'leases_released': False, 'comparison_eligible': False, 'superiority_proven': False}
        require(len(encoded(intent)) + 1 <= 16 * LIMIT, 'Transaction metadata exceeds recovery allowance before writes')
        atomic_json(transaction, intent, exclusive=True)
        try:
            source.clock(deadline)
            apply_files(repo, new, intent['staging_paths'], after_each, after_stage)
            require(source.inventory(repo, deadline) == after, 'Raw checkout differs from exact expected install')
        except BaseException as error:
            intent.update(state='failed_pending_rollback', first_error={'type': type(error).__name__,
                          'message': str(error), 'staging_cleanup_errors': getattr(error, 'staging_cleanup_errors', [])})
            atomic_json(transaction, intent)
            try:
                rollback(repo, transaction, _already_locked=True)
            except BaseException as recovery_error:
                intent = strict.decoded(transaction.read_bytes())
                intent['rollback_error'] = {'type': type(recovery_error).__name__, 'message': str(recovery_error)}
                atomic_json(transaction, intent)
            error.__dict__['preserved_transaction'] = str(transaction)
            raise
        intent['state'] = 'raw_files_integrated_pending_lease_native_runtime_and_verification'
        atomic_json(transaction, intent)
        return transaction


def rollback(repo, transaction, _already_locked=False):
    """Restore exact original checkout, retaining unknown drift and first error."""
    repo = Path(repo).resolve(); transaction = Path(transaction).resolve()
    require(repo != transaction.parent and repo not in transaction.parents, 'External recovery journal required')
    if not _already_locked:
        with locked(repo, transaction.parent):
            return rollback(repo, transaction, _already_locked=True)
    require(stat.S_ISREG(transaction.lstat().st_mode) and transaction.stat().st_size <= 24 * LIMIT,
            'Bounded regular recovery transaction required')
    intent = strict.decoded(transaction.read_bytes())
    require(intent['state'] in ('intent', 'failed_pending_rollback') and intent['root'] == str(repo),
            'Wrong transaction root/state')
    require(all(intent.get(k) is False for k in ('native_qualified', 'runtime_qualified', 'leases_released',
                'comparison_eligible', 'superiority_proven')), 'Filesystem journal cannot grant qualification')
    before = intent['before_inventory']; after = intent['expected_after_inventory']
    for snapshot in (before, after):
        for key in ('all_entities', 'source_entities', 'git_entities'):
            registry.validate_tree(snapshot[key]) if key != 'git_entities' else None
    old = {p: bytes.fromhex(raw) for p, raw in intent['before_payloads'].items()}
    new = {p: bytes.fromhex(raw) for p, raw in intent['after_payloads'].items()}
    require(set(old) == set(new) <= set(before['source_entities']), 'Recovery payload paths changed')
    require(all(len(old[p]) <= LIMIT and len(new[p]) <= LIMIT
                and hashlib.sha256(old[p]).hexdigest() == before['source_entities'][p]['sha256'] for p in old),
            'Preserved original payload changed')
    require(after == projected(before, old, new), 'Recovery expected inventory changed')
    install_stage = staging_paths(new, transaction)
    restore_stage = staging_paths(old, transaction.with_name(transaction.stem + '-rollback.json'))
    require(intent['staging_paths'] == install_stage, 'Unowned installation staging')
    current = source.inventory(repo)
    original_entities = before['all_entities']; actual = current['all_entities']; extras = set(actual) - set(original_entities)
    owned = {**{s: (new[p], original_entities[p]['mode']) for p, s in install_stage.items()},
             **{s: (old[p], original_entities[p]['mode']) for p, s in restore_stage.items()}}
    require(set(original_entities) <= set(actual) and extras <= set(owned), 'Unknown recovery entity drift')
    require(all(actual[p] in (entity, after['all_entities'][p]) for p, entity in original_entities.items()),
            'Unknown source/Git/cache changes; retain and reject recovery')
    for name in extras:
        raw = payload(repo / name); expected, mode = owned[name]
        require(actual[name]['kind'] == 'file' and actual[name]['mode'] in (0o600, mode) and expected.startswith(raw),
                'Unknown staging bytes or permissions')
    attempt = {'started_at': time.time(), 'prior_state': intent['state'], 'owned_staging_to_remove': sorted(extras)}
    intent.setdefault('rollback_attempts', []).append(attempt); atomic_json(transaction, intent)
    try:
        for name in extras: (repo / name).unlink()
        apply_files(repo, old, restore_stage)
        require(source.inventory(repo) == before, 'Rollback differs from full preserved raw checkout')
        intent['state'] = 'rolled_back_preserved_failure'; attempt['status'] = 'restored_full_raw_checkout'
    except BaseException as error:
        attempt.update(status='failed', error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        atomic_json(transaction, intent)
    return transaction
