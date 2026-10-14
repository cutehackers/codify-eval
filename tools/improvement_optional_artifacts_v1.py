"""Optional contribution files/decisions/rollback, pending broker qualification.

Caller must independently verify native member terminality, exact owned stopped
containers, no-more-delivery and registry fencing before seal/integration/recovery.
This filesystem core cannot authenticate that caller or claim those conditions.
"""
import json
from pathlib import Path
import stat
import time
import uuid

import improvement_optional_registry_v2 as registry
from improvement_software_artifacts_v3 import (
    LIMIT, digest, encoded, tree, atomic_json, locked, staging_paths, apply_files,
)

require = registry.require


def regular_bytes(path, limit=8 * LIMIT):
    path = Path(path)
    require(stat.S_ISREG(path.lstat().st_mode) and path.stat().st_size <= limit,
            'Artifact must be bounded regular file')
    return path.read_bytes()


def pin(path):
    path = Path(path)
    raw = regular_bytes(path)
    return {'path':str(path.resolve()), 'sha256':digest(raw)}


def pinned(reference):
    require(isinstance(reference, dict) and set(reference) == {'path','sha256'}, 'Invalid artifact pin')
    raw = regular_bytes(reference['path'])
    require(digest(raw) == reference['sha256'], 'Artifact pin drift')
    return json.loads(raw)


def seal(state, slot, repo, destination, findings=''):
    require(slot in state['workers'], 'Unallocated worker')
    row = state['workers'][slot]
    snapshot = row['snapshot']; current = tree(repo)
    changed = {p for p in set(snapshot) | set(current) if snapshot.get(p) != current.get(p)}
    require(changed <= set(row['scope']) and set(current) == set(snapshot), 'Worker scope/entity violation')
    require(all(current[p]['kind'] == snapshot[p]['kind'] and current[p]['mode'] == snapshot[p]['mode']
                for p in current), 'Worker permission/kind violation')
    require(isinstance(findings,str) and len(findings.encode()) <= LIMIT, 'Invalid review findings')
    if row['mode'] == 'review':
        require(not changed and findings.strip(), 'Read-only review needs findings and unchanged tree')
    payloads = {}
    for name in sorted(changed):
        raw = regular_bytes(Path(repo) / name, LIMIT)
        require(digest(raw) == current[name]['sha256'], 'Worker changed while sealing')
        payloads[name] = {'hex':raw.hex(), 'sha256':digest(raw), 'mode':current[name]['mode']}
    require(tree(repo) == current, 'Worker changed during seal')
    value = dict(slot=slot, configuration_sha256=state['configuration_sha256'],
                 snapshot_sha256=row['snapshot_sha256'], scope=row['scope'], mode=row['mode'],
                 current_tree_sha256=registry.sha(current), payloads=payloads, findings=findings,
                 native_qualified=False, stopped_container_qualified=False, comparison_eligible=False)
    destination=Path(destination)
    require(destination.resolve() != Path(repo).resolve() and
            Path(repo).resolve() not in destination.resolve().parents, 'Seal journal must be external to worker')
    require(len(encoded(value)) <= 8*LIMIT, 'Encoded artifact exceeds limit')
    destination.parent.mkdir(parents=True,exist_ok=True)
    atomic_json(destination,value,exclusive=True)
    return pin(destination)


def artifact(state, reference):
    value=pinned(reference);row=state['workers'].get(value.get('slot'))
    require(row is not None and value['configuration_sha256'] == state['configuration_sha256'],
            'Artifact allocation mismatch')
    require(value['snapshot_sha256'] == row['snapshot_sha256'] and value['scope'] == row['scope']
            and value['mode'] == row['mode'], 'Artifact lease mismatch')
    expected=dict(row['snapshot'])
    require(isinstance(value['payloads'],dict) and set(value['payloads']) <= set(row['scope']),
            'Unleased contribution')
    for name,payload in value['payloads'].items():
        require(set(payload) == {'hex','sha256','mode'} and isinstance(payload['hex'],str), 'Invalid payload')
        raw=bytes.fromhex(payload['hex'])
        require(len(raw) <= LIMIT and digest(raw) == payload['sha256'] and
                type(payload['mode']) is int and payload['mode'] == row['snapshot'][name]['mode'],
                'Contribution bytes/permission drift')
        expected[name]={'kind':'file','mode':payload['mode'],'sha256':payload['sha256']}
    require(registry.sha(expected) == value['current_tree_sha256'], 'Sealed tree digest mismatch')
    require(isinstance(value['findings'],str) and len(value['findings'].encode()) <= LIMIT,
            'Invalid findings')
    require(value['mode'] != 'review' or (not value['payloads'] and value['findings'].strip()),
            'Invalid read-only review contribution')
    require(value['native_qualified'] is False and value['stopped_container_qualified'] is False
            and value['comparison_eligible'] is False, 'Filesystem artifact cannot grant qualification')
    return value


def view(state, reference, destination):
    value=artifact(state,reference)
    receipt={'configuration_sha256':state['configuration_sha256'], 'slot':value['slot'],
             'artifact':reference, 'displayed_payloads':value['payloads'], 'displayed_findings':value['findings'],
             'actual_native_view_verified':False}
    atomic_json(Path(destination),receipt,exclusive=True)
    return pin(destination), receipt


def decide(state, reference, view_reference, decision, reason, destination):
    require(decision in ('accept','reject') and isinstance(reason,str) and reason.strip(),
            'Explicit original decision/reason required')
    value=artifact(state,reference);receipt=pinned(view_reference)
    require(receipt['configuration_sha256'] == state['configuration_sha256'] and
            receipt['slot'] == value['slot'] and receipt['artifact'] == reference and
            receipt['displayed_payloads'] == value['payloads'] and
            receipt['displayed_findings'] == value['findings'], 'Decision missing exact artifact view')
    row={'configuration_sha256':state['configuration_sha256'], 'slot':value['slot'],
         'artifact':reference, 'view':view_reference, 'decision':decision, 'reason':reason,
         'actual_native_decision_verified':False, 'comparison_eligible':False}
    atomic_json(Path(destination),row,exclusive=True)
    return pin(destination)


def selected(state, decisions, current):
    require(isinstance(decisions,list), 'Decision registry required')
    require(len(decisions) == len(state['workers']), 'Every allocated worker requires a decision')
    seen=set();payloads={};leased=set()
    for reference in decisions:
        decision=pinned(reference);slot=decision.get('slot')
        require(slot in state['workers'] and slot not in seen and
                decision['configuration_sha256'] == state['configuration_sha256'], 'Duplicate/unknown decision')
        require(decision['decision'] in ('accept','reject') and isinstance(decision['reason'],str)
                and decision['reason'].strip(), 'Decision invalid')
        receipt=pinned(decision['view']);value=artifact(state,decision['artifact'])
        require(value['slot'] == slot and receipt['slot'] == slot and
                receipt['configuration_sha256'] == state['configuration_sha256'] and
                receipt['artifact'] == decision['artifact'] and
                receipt['displayed_payloads'] == value['payloads'] and
                receipt['displayed_findings'] == value['findings'], 'Decision view/artifact mismatch')
        seen.add(slot)
        if decision['decision'] == 'reject':
            continue
        row=state['workers'][slot]
        require(not leased & set(row['scope']), 'Accepted contribution overlap')
        leased.update(row['scope'])
        require(all(current.get(name) == row['snapshot'][name] for name in row['scope']),
                'Accepted contribution base changed')
        payloads.update({name:bytes.fromhex(payload['hex']) for name,payload in value['payloads'].items()})
    require(seen == set(state['workers']), 'Missing allocation decision')
    return payloads


def integrate(repo, state, decisions, expected_tree, journal, after_each=None, after_stage=None):
    """Stopped-root file transaction. Empty solo/rejected payloads are valid."""
    with locked(repo,journal):
        current=tree(repo)
        require(current == expected_tree,'Root changed before integration')
        registry.check_root_changes(state,current)
        payloads=selected(state,decisions,current)
        before={name:regular_bytes(Path(repo)/name,LIMIT).hex() for name in payloads}
        require(all(digest(bytes.fromhex(raw)) == current[name]['sha256'] for name,raw in before.items()),
                'Root changed while preserving integration base')
        require(tree(repo) == current,'Root changed while preparing transaction')
        expected={**current,**{name:{'kind':'file','mode':current[name]['mode'],'sha256':digest(raw)}
                              for name,raw in payloads.items()}}
        path=Path(journal)/(uuid.uuid4().hex+'.json')
        intent=dict(state='intent',root=str(Path(repo).resolve()),configuration_sha256=state['configuration_sha256'],
                    before_tree=current,expected_after=expected,before_payloads=before,
                    after_payloads={name:raw.hex() for name,raw in payloads.items()},decisions=decisions,
                    created_at=time.time(),staging_paths=staging_paths(payloads,path),
                    native_qualified=False,runtime_qualified=False,comparison_eligible=False,
                    complete_final_cost=False,superiority_proven=False)
        atomic_json(path,intent,exclusive=True)
        try:
            apply_files(repo,payloads,intent['staging_paths'],after_each,after_stage)
            require(tree(repo) == expected,'Integrated bytes differ from exact expected tree')
        except BaseException as error:
            intent.update(state='failed_pending_rollback',first_error={'type':type(error).__name__,
                          'message':str(error),'staging_cleanup_errors':getattr(error,'staging_cleanup_errors',[])})
            atomic_json(path,intent)
            try:
                rollback(repo,path,_already_locked=True)
            except BaseException as rollback_error:
                intent=json.loads(path.read_bytes())
                intent['rollback_error']={'type':type(rollback_error).__name__,'message':str(rollback_error)}
                atomic_json(path,intent)
            error.__dict__['preserved_transaction']=str(path)
            raise
        intent['state']='files_integrated_pending_native_runtime_and_public_verification'
        atomic_json(path,intent)
        return path


def rollback(repo, transaction, _already_locked=False):
    transaction=Path(transaction)
    if not _already_locked:
        with locked(repo,transaction.parent):
            return rollback(repo,transaction,_already_locked=True)
    intent=json.loads(regular_bytes(transaction,16*LIMIT))
    require(intent['state'] in ('intent','failed_pending_rollback') and
            intent['root'] == str(Path(repo).resolve()),'Wrong transaction/root/state')
    before=intent['before_tree'];after=intent['expected_after']
    registry.validate_tree(before);registry.validate_tree(after)
    old={name:bytes.fromhex(raw) for name,raw in intent['before_payloads'].items()}
    new={name:bytes.fromhex(raw) for name,raw in intent['after_payloads'].items()}
    require(set(old) == set(new) and set(old) <= set(before),'Recovery payload mismatch')
    require(all(len(old[p])<=LIMIT and len(new[p])<=LIMIT and digest(old[p]) == before[p]['sha256']
                and after[p] == {'kind':'file','mode':before[p]['mode'],'sha256':digest(new[p])}
                for p in old),'Recovery payload/tree drift')
    require(after == {**before,**{p:after[p] for p in old}},'Unexpected recovery entity change')
    install_staging=staging_paths(new,transaction)
    restore_staging=staging_paths(old,transaction.with_name(transaction.stem+'-rollback.json'))
    require(intent['staging_paths'] == install_staging,'Unowned staging paths')
    current=tree(repo);extras=set(current)-set(before)
    owned_staging={**{p:(new[n],before[n]['mode']) for n,p in install_staging.items()},
                   **{p:(old[n],before[n]['mode']) for n,p in restore_staging.items()}}
    require(set(before)<=set(current) and extras<=set(owned_staging), 'Unknown recovery tree entity')
    require(all(current[p] in (before[p],after[p]) for p in before),'Unexpected root bytes; retain and reject')
    for name in extras:
        raw=regular_bytes(Path(repo)/name,LIMIT);payload,mode=owned_staging[name]
        require(current[name]['mode'] in (0o600,mode) and payload.startswith(raw),'Unrecognized staging bytes')
    attempt={'started_at':time.time(),'prior_state':intent['state'],'owned_staging_to_remove':sorted(extras)}
    intent.setdefault('rollback_attempts',[]).append(attempt);atomic_json(transaction,intent)
    try:
        for name in extras:(Path(repo)/name).unlink()
        apply_files(repo,old,restore_staging)
        require(tree(repo) == before,'Rollback tree differs from preserved base')
        intent['state']='rolled_back_preserved_failure'
        attempt['status']='restored_exact_before_tree'
    except BaseException as error:
        attempt['status']='failed';attempt['error']={'type':type(error).__name__,'message':str(error)}
        raise
    finally:
        atomic_json(transaction,intent)
    return transaction
