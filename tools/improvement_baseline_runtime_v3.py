"""Baseline prospective draft copied from improvement_optional_runtime_v10.
No native qualification, preventive filesystem authority or model admission.

Trusted optional Docker lifecycle and contribution precursor, not native authority.

Native termination/no-more-delivery must be established before final cleanup by
the future coordinator. This module never claims actor or comparison authority.
Lock order: job -> registry (if needed) -> brief state lock. Never wait for a job
while holding state lock; Dockerexec and host inventories happen outside it.
"""
import contextlib
import fcntl
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import os
import selectors
import subprocess
import time
import uuid
import re

import improvement_optional_inventory_v3 as strict
import improvement_baseline_case_catalog_v1 as catalog

import improvement_optional_source_v2 as source
import improvement_baseline_registry_v1 as registry
import improvement_baseline_artifacts_v1 as artifacts
import improvement_baseline_checkout_artifacts_v1 as checkout
from improvement_software_artifacts_v3 import atomic_json, encoded
from improvement_q04_runtime_v3 import IMAGE, docker
from improvement_q04_broker_v1 import archive_tmp

require=registry.require


def hashed(text):return hashlib.sha256(text.encode()).hexdigest()


QUESTION_SOURCES = {
    'tools/improvement_baseline_runtime_v3.py',
    'tools/improvement_baseline_broker_v3.py',
    'tools/improvement_baseline_native_dispatch_v3.py',
    'tools/improvement_baseline_question_branch_v1.py',
    'tools/improvement_baseline_question_lifecycle_v2.py',
}


def question_file_entity(path):
    """Local byte/mode identity, not external native/reviewer authentication."""
    import stat
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path
            and path.is_relative_to(catalog.ROOT), 'Canonical local question source required')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
            and 0 < before.st_size <= 256 * 1024**2, 'Bounded single-link question file required')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024**2),b''):digest.update(chunk)
    after = path.lstat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            'Question file changed during capture')
    return {'kind':'file','mode':stat.S_IMODE(before.st_mode),'bytes':before.st_size,
            'sha256':digest.hexdigest()}


def question_reference(path):
    path = Path(path)
    return {'path':str(path), 'entity':question_file_entity(path)}


def question_source_closure():
    """Exact local tool dependency closure. Does not qualify those dependencies."""
    import ast
    paths={catalog.ROOT/key for key in QUESTION_SOURCES};queue=list(paths)
    while queue:
        path=queue.pop()
        for node in ast.walk(ast.parse(path.read_bytes())):
            names=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) else []
            for name in names:
                if name:
                    local=catalog.ROOT/'tools'/(name.split('.')[0]+'.py')
                    if local.is_file() and local not in paths:
                        paths.add(local);queue.append(local)
    return {str(path.relative_to(catalog.ROOT)):question_file_entity(path) for path in sorted(paths)}


def question_verify_reference(reference):
    import improvement_baseline_question_branch_v1 as branch
    require(type(reference) is dict and set(reference) == {'path','entity'}
            and type(reference['path']) is str, 'Exact local question reference required')
    branch.entity(reference['entity'])
    path = Path(reference['path'])
    require(encoded(question_file_entity(path)) == encoded(reference['entity']),
            'Frozen question reference changed')
    return path


def question_reference_bytes(reference):
    path=question_verify_reference(reference)
    require(reference['entity']['bytes']<=2*1024**2,'Bounded question control body required')
    raw = path.read_bytes()
    require(encoded(question_file_entity(path)) == encoded(reference['entity']),
            'Question reference changed while reading')
    return raw


@contextlib.contextmanager
def question_operation_lock(folder):
    """Broker-job lock -> question lock -> brief state lock. No inverse wait."""
    path = Path(folder) / 'question'
    if not path.exists():
        yield
        return
    require(path.resolve(strict=True) == path and path.is_dir(), 'Canonical question control directory required')
    with (path / 'transition.lock').open('a+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def _question_snapshot(folder, closing=False):
    """Recompute every immutable local commitment on each transition/operation."""
    folder = Path(folder).resolve(); directory = folder / 'question'
    control_raw = (directory / 'configuration.json').read_bytes()
    origin = strict.decoded((directory / 'configuration-origin.json').read_bytes())
    require(type(origin) is dict and set(origin) == {'configuration_entity'}
            and encoded(question_file_entity(directory / 'configuration.json'))
            == encoded(origin['configuration_entity']), 'Original question commitment changed')
    control = strict.decoded(control_raw)
    required = {'schema_version','binding','coordinator_identity','coordinator_capability_sha256',
                'runtime_configuration','registry_configuration','root_capability_sha256',
                'original_started_at','original_deadline','worker_cap','retries',
                'source_entities','source_pin_digest','external_authentication_required'}
    require(type(control) is dict and set(control) == required
            and type(control['schema_version']) is int and control['schema_version'] == 1
            and control['external_authentication_required'] is True,
            'Exact coordinator-owned question commitment required')
    for reference in (control['runtime_configuration'], control['registry_configuration']):
        question_reference_bytes(reference)
    require(type(control['source_entities']) is dict
            and encoded(control['source_entities'])==encoded(question_source_closure())
            and control['source_pin_digest'] == hashlib.sha256(encoded(control['source_entities'])).hexdigest(),
            'Question source closure changed')
    for key, entity in control['source_entities'].items():
        require(type(key) is str and key.startswith('tools/') and '..' not in Path(key).parts,
                'Explicit local tool source required')
        question_verify_reference({'path':str(catalog.ROOT / key),'entity':entity})
    state = load(folder); config = strict.decoded(question_reference_bytes(control['runtime_configuration']))
    config_keys={'case','condition','image','task','editable_paths','started_at','deadline',
                 'model','effort','worker_cap','retries','public_contract'}
    require(type(config) is dict and set(config)==config_keys
            and config['case'] in ('B03','B04') and config['model']=='gpt-6.1-sol'
            and config['effort']=='medium' and config['image']==IMAGE
            and type(config['worker_cap']) is int and config['worker_cap'] in (0,2)
            and type(config['retries']) is int and config['retries']==0,
            'Exact original fixed-model question runtime configuration required')
    execution=catalog.declared_execution(config['case'],config['condition'],config['worker_cap'])
    require(encoded(config['public_contract'])==encoded(execution)
            and sorted(execution['editable_paths'])==config['editable_paths']==state['editable_paths'],
            'Original current qualified public contract or scope changed')
    binding = control['binding']
    require(type(binding) is dict and set(binding) == {
        'run_id','case_id','root_native_uuid','parent_native_uuid','agent_path'}
        and all(type(v) is str and bool(v) for v in binding.values())
        and binding['root_native_uuid'] != binding['parent_native_uuid']
        and re.fullmatch('/root/[A-Za-z0-9_]+', binding['agent_path']) is not None,
        'Original native question binding changed')
    import math
    require(type(control['coordinator_identity']) is str and bool(control['coordinator_identity'])
            and control['coordinator_identity']==binding['parent_native_uuid']
            and type(control['coordinator_capability_sha256']) is str
            and re.fullmatch('[0-9a-f]{64}',control['coordinator_capability_sha256']) is not None
            and all(type(control[key]) in (int,float) and math.isfinite(control[key])
                    for key in ('original_started_at','original_deadline')),
            'Typed coordinator identity and original question clock required')
    require(binding['run_id'] == state['run_id'] and binding['case_id'] == config['case']
            and encoded(control['original_started_at']) == encoded(state['started_at']) == encoded(config['started_at'])
            and encoded(control['original_deadline']) == encoded(state['deadline']) == encoded(config['deadline'])
            and control['original_deadline'] == control['original_started_at'] + 1200,
            'Original question identity or whole clock changed')
    require(type(control['worker_cap']) is int and control['worker_cap'] in (0,2)
            and type(state['worker_cap']) is int and state['worker_cap'] == control['worker_cap'] == config['worker_cap']
            and type(control['retries']) is int and control['retries'] == 0
            and type(state['retries']) is int and state['retries'] == 0
            and state['jobs']['root']['capability_sha256'] == control['root_capability_sha256']
            and state['configuration_sha256'] == hashlib.sha256(encoded(config)).hexdigest(),
            'Root capability, cap or retry identity changed')
    if not closing:
        require(not (directory / 'no-more-delivery.json').exists(), 'Coordinator has committed no more delivery')
        budget(state)
    history = []; previous = hashlib.sha256(control_raw).hexdigest()
    for path in sorted((directory / 'events').iterdir()):
        require(path.name == f'{len(history):04d}.json', 'Question transition sequence changed')
        row = strict.decoded(path.read_bytes())
        require(type(row) is dict and set(row) == {'number','previous_sha256','operation','at','payload'}
                and type(row['number']) is int and row['number'] == len(history)
                and row['previous_sha256'] == previous and type(row['payload']) is dict,
                'Exact chained question transition required')
        import math
        require(type(row['at']) in (int,float) and math.isfinite(row['at'])
                and control['original_started_at'] <= row['at'] < control['original_deadline']
                and (not history or history[-1]['at'] <= row['at']), 'Question transition outside original clock')
        allowed = {'committed':{'paused'}, 'paused':{'authority'}, 'authority':{'staged'},
                   'staged':{'resumed'}, 'resumed':{'reply_read_completed'}}
        prior = history[-1]['operation'] if history else 'committed'
        require(row['operation'] in allowed.get(prior,set()), 'Unapproved or repeated question transition')
        fields = {'paused':({'references'},{'first_seal'}),
                  'authority':({'references'},{'authority','semantic_review','private_assignment'}),
                  'staged':({'references','root_container_id'},{'reply'}),
                  'resumed':({'root_container_id'},set()),
                  'reply_read_completed':({'references'},{'broker_receipt','claim'})}
        payload_keys,reference_keys=fields[row['operation']]
        require(set(row['payload'])==payload_keys
                and type(row['payload'].get('references',{})) is dict
                and set(row['payload'].get('references',{}))==reference_keys,
                'Exact operation-specific question transition payload required')
        if 'root_container_id' in row['payload']:
            require(row['payload']['root_container_id']==state['jobs']['root']['container_id'],
                    'Original root engine ID changed')
        for reference in row['payload'].get('references',{}).values():
            question_verify_reference(reference)
        history.append(row); previous = hashlib.sha256(path.read_bytes()).hexdigest()
    return state, control, history


def question_validate(folder):
    if (Path(folder) / 'question').exists():
        return _question_snapshot(folder)
    return None


def question_coordinator_auth(folder, capability, closing=False):
    state, control, history = _question_snapshot(folder, closing)
    require(type(capability) is str and re.fullmatch('[0-9a-f]{48}',capability) is not None
            and secrets.compare_digest(hashed(capability),control['coordinator_capability_sha256']),
            'Private question coordinator capability required')
    return state, control, history


def _question_append(folder, control, history, operation, payload):
    directory = Path(folder) / 'question'; number = len(history)
    before = directory / 'configuration.json' if not history else directory / 'events' / f'{number-1:04d}.json'
    atomic_json(directory / 'events' / f'{number:04d}.json', {
        'number':number,'previous_sha256':hashlib.sha256(before.read_bytes()).hexdigest(),
        'operation':operation,'at':time.time(),'payload':payload},exclusive=True)


def create_question_control(folder, root_capability, *, coordinator_capability,
                            coordinator_identity, binding, source_entities):
    """Coordinator-only sidecar. Its native/reviewer provenance remains an adapter gate."""
    folder = Path(folder).resolve(); state = role(folder,'root',root_capability)
    require(type(coordinator_capability) is str and re.fullmatch('[0-9a-f]{48}',coordinator_capability) is not None
            and coordinator_capability != root_capability and type(coordinator_identity) is str
            and bool(coordinator_identity), 'Separate private coordinator identity/capability required')
    require(type(source_entities) is dict and encoded(source_entities)==encoded(question_source_closure()),
            'Exact frozen full question source closure required')
    for key,entity in source_entities.items():
        question_verify_reference({'path':str(catalog.ROOT / key),'entity':entity})
    control = {'schema_version':1,'binding':binding,'coordinator_identity':coordinator_identity,
        'coordinator_capability_sha256':hashed(coordinator_capability),
        'runtime_configuration':question_reference(folder/'configuration.json'),
        'registry_configuration':question_reference(folder/'registry/configuration.json'),
        'root_capability_sha256':state['jobs']['root']['capability_sha256'],
        'original_started_at':state['started_at'],'original_deadline':state['deadline'],
        'worker_cap':state['worker_cap'],'retries':0,'source_entities':source_entities,
        'source_pin_digest':hashlib.sha256(encoded(source_entities)).hexdigest(),
        'external_authentication_required':True}
    directory = folder / 'question'; directory.mkdir(); (directory/'events').mkdir()
    atomic_json(directory/'configuration.json',control,exclusive=True)
    atomic_json(directory/'configuration-origin.json',{
        'configuration_entity':question_file_entity(directory/'configuration.json')},exclusive=True)
    _question_snapshot(folder)
    return question_reference(directory/'configuration.json')


def guard_question_startup(folder, job, capability, operation):
    """Unbound B03/B04 actors may only use their unique root public read.

    Internal root preparation is permitted while the original trusted runtime is
    still preparing. Native UUID/reviewer provenance is never inferred here.
    No lock, action intent, snapshot or container operation occurs in this guard.
    """
    folder=Path(folder)
    config=strict.decoded((folder/'configuration.json').read_bytes())
    state=load(folder)
    require(type(config) is dict and config.get('case') in ('B01','B02','B03','B04')
            and state['configuration_sha256']==hashlib.sha256(encoded(config)).hexdigest(),
            'Original startup runtime configuration required')
    if config['case'] in ('B01','B02'):
        require(operation!='read_reply', 'No committed question reply authority')
        return
    keys={'case','condition','image','task','editable_paths','started_at','deadline',
          'model','effort','worker_cap','retries','public_contract'}
    require(set(config)==keys and config['condition'] in ('A','C0','C23')
            and config['model']=='gpt-6.1-sol' and config['effort']=='medium' and config['image']==IMAGE
            and type(config['worker_cap']) is int and config['worker_cap'] in (0,2)
            and type(state.get('worker_cap')) is int and state['worker_cap']==config['worker_cap']
            and type(config['retries']) is int and config['retries']==0
            and type(state.get('retries')) is int and state['retries']==0,
            'Strict original startup cap/model/retries required')
    import math
    require(type(config['started_at']) in (int,float) and math.isfinite(config['started_at'])
            and type(config['deadline']) in (int,float) and math.isfinite(config['deadline'])
            and 0<config['started_at']<=time.time() and config['deadline']==config['started_at']+1200
            and encoded(state['started_at'])==encoded(config['started_at'])
            and encoded(state['deadline'])==encoded(config['deadline'])
            and config['editable_paths']==state['editable_paths']
            and type(config['public_contract']) is dict
            and config['public_contract']['case_id']==config['case']
            and config['public_contract']['condition']==config['condition']
            and type(config['public_contract']['worker_cap']) is int
            and config['public_contract']['worker_cap']==config['worker_cap']
            and sorted(config['public_contract']['editable_paths'])==config['editable_paths'],
            'Original startup clock/public scope changed')
    row=state['jobs'].get(job)
    require(job=='root' and type(capability) is str and re.fullmatch('[0-9a-f]{48}',capability) is not None
            and type(row) is dict and row.get('status')=='running'
            and secrets.compare_digest(hashed(capability),row['capability_sha256']),
            'Only original unbound root capability is permitted')
    budget(state)
    if state['phase']=='preparing':
        require(operation=='exec', 'Only trusted original internal root preparation may execute before binding')
    else:
        require(state['phase']=='running' and operation=='read',
                'Unbound question root permits sole public read; committed native question control required before work')


def guard_question_operation(folder, job, capability, operation, *, _completion=False):
    value = question_validate(folder)
    if value is None:
        guard_question_startup(folder,job,capability,operation)
        return
    state, control, history = value; row = state['jobs'].get(job)
    require(row is not None and type(capability) is str
            and secrets.compare_digest(hashed(capability),row['capability_sha256']), 'Original role capability required')
    phase = history[-1]['operation'] if history else 'committed'
    if phase == 'committed':
        require(operation != 'read_reply', 'Reply before semantic authority')
    elif phase == 'resumed':
        require(job == 'root' and operation == 'read_reply', 'Second turn first complete reply read required')
        require(_completion or not (Path(folder)/'question/reply-read-intent.json').exists(),
                'Original claimed reply read cannot retry')
    elif phase == 'reply_read_completed':
        require(operation not in ('read','read_reply'), 'Original public/reply reads cannot repeat')
    else:
        raise ValueError('Product work forbidden during question pause/authority/staging')


def pause_for_question(folder, coordinator_capability, first_seal_reference):
    with question_operation_lock(folder):
        state, control, history = question_coordinator_auth(folder,coordinator_capability)
        require(not history, 'First question pause is create-only')
        seal = strict.decoded(question_reference_bytes(first_seal_reference))
        keys = {'schema_version','binding','original_started_at','original_deadline',
                'first_completed_at','sealed_at','first_turn_id','member_native_uuids','evidence_entities'}
        require(type(seal) is dict and set(seal) == keys and type(seal['schema_version']) is int
                and seal['schema_version'] == 1 and encoded(seal['binding']) == encoded(control['binding'])
                and encoded(seal['original_started_at']) == encoded(control['original_started_at'])
                and encoded(seal['original_deadline']) == encoded(control['original_deadline'])
                and type(seal['first_turn_id']) is str and bool(seal['first_turn_id']), 'Exact frozen first seal required')
        import improvement_baseline_question_branch_v1 as branch
        completed,sealed=map(branch.finite,(seal['first_completed_at'],seal['sealed_at']))
        require(control['original_started_at'] <= completed <= sealed <= time.time() < control['original_deadline'],
                'First completion/quiescent seal chronology changed')
        members = registry.read(Path(folder)/'registry')
        jobs = {'root'} | set(members['workers'])
        require(set(state['jobs']) == jobs == set(seal['member_native_uuids'])
                and seal['member_native_uuids']['root'] == control['binding']['root_native_uuid']
                and all(type(v) is str and bool(v) for v in seal['member_native_uuids'].values())
                and control['binding']['parent_native_uuid'] not in seal['member_native_uuids'].values()
                and len(set(seal['member_native_uuids'].values())) == len(jobs), 'Every actual cumulative member required')
        require(type(seal['evidence_entities']) is dict and bool(seal['evidence_entities']), 'Sealed native/source evidence required')
        for path,entity in seal['evidence_entities'].items():
            question_verify_reference({'path':path,'entity':entity})
        for job in jobs:
            require(state['jobs'][job]['status'] in ('stopped','sealed_stopped')
                    and not inspect(folder,state,job)['State']['Running'], 'Every allocated product must already be quiescent')
        _question_append(folder,control,history,'paused',{'references':{'first_seal':first_seal_reference}})
        with lock(folder):
            state=load(folder);state['phase']='question_paused';save(folder,state)
        return question_reference(Path(folder)/'question/events/0000.json')


def commit_question_authority(folder, coordinator_capability, *, semantic_review_reference,
                              private_assignment_reference, reviewer_identity, policy_sha256):
    """Recompute branch schema/pins. Reviewer/native provenance is still external."""
    import improvement_baseline_question_branch_v1 as branch
    with question_operation_lock(folder):
        state,control,history=question_coordinator_auth(folder,coordinator_capability)
        require(len(history)==1 and history[-1]['operation']=='paused', 'Original first pause required')
        seal_ref=history[0]['payload']['references']['first_seal']
        seal=strict.decoded(question_reference_bytes(seal_ref)); review=question_reference_bytes(semantic_review_reference)
        question_verify_reference(private_assignment_reference)
        authority=branch.authority(review,binding=control['binding'],
            semantic_review_entity=semantic_review_reference['entity'],first_seal_entity=seal_ref['entity'],
            evidence_entities=seal['evidence_entities'],reviewer_identity=reviewer_identity,
            private_assignment_entity=private_assignment_reference['entity'],source_pin_digest=control['source_pin_digest'],
            original_started_at=control['original_started_at'],original_deadline=control['original_deadline'],
            first_completed_at=seal['first_completed_at'],sealed_at=seal['sealed_at'],decided_at=time.time(),policy_sha256=policy_sha256)
        path=Path(folder)/'question/branch-authority.json';atomic_json(path,authority,exclusive=True)
        refs={'authority':question_reference(path),'semantic_review':semantic_review_reference,
              'private_assignment':private_assignment_reference}
        _question_append(folder,control,history,'authority',{'references':refs})
        return question_reference(path)


def stage_question_reply(folder, coordinator_capability, reply_bytes):
    import improvement_baseline_question_branch_v1 as branch
    with question_operation_lock(folder):
        state,control,history=question_coordinator_auth(folder,coordinator_capability)
        require(history[-1]['operation']=='authority', 'One original semantic authority required')
        authority=strict.decoded(question_reference_bytes(history[-1]['payload']['references']['authority']))
        require(authority['expected_root_turns']==2 and authority['reply_kind'] in ('policy','neutral'), 'No reply on no-question branch')
        raw=branch.reply_bytes(reply_bytes)
        require(hashlib.sha256(raw).hexdigest()==authority['reply_sha256_or_null'], 'Only original authorized reply bytes may stage')
        if authority['reply_kind']=='neutral':require(raw==branch.NEUTRAL,'Neutral branch cannot acquire policy body')
        target=Path(folder)/'root/input/turn-2.txt'
        require(not target.exists() and not target.is_symlink(), 'Reply stage is create-only')
        with target.open('xb') as stream:stream.write(raw)
        target.chmod(0o444)
        _question_append(folder,control,history,'staged',{'references':{'reply':question_reference(target)},
            'root_container_id':state['jobs']['root']['container_id']})
        return {'reply_entity':question_file_entity(target),'reply_kind':authority['reply_kind'],
                'original_deadline':control['original_deadline'],'transport_verified':False}


def resume_for_reply(folder, coordinator_capability):
    with question_operation_lock(folder):
        state,control,history=question_coordinator_auth(folder,coordinator_capability)
        require(history[-1]['operation']=='staged' and state['phase']=='question_paused'
                and state['jobs']['root']['container_id']==history[-1]['payload']['root_container_id'],
                'Only same staged original root container may resume')
        with lock(folder):
            state=load(folder);state['phase']='running';save(folder,state)
        try:start(folder,'root')
        except BaseException as error:
            failure(folder,error);raise
        state,control,current=question_coordinator_auth(folder,coordinator_capability)
        require(current==history,'Question authority changed while resuming')
        _question_append(folder,control,history,'resumed',{'root_container_id':state['jobs']['root']['container_id']})
        return {'binding':control['binding'],'original_deadline':control['original_deadline'],
                'native_delivery_authorized_by_adapter':False}


def read_question_reply(folder, root_capability, broker_intent):
    """Called only under broker's question lock; claim never retries on failure."""
    guard_question_operation(folder,'root',root_capability,'read_reply')
    state,control,history=_question_snapshot(folder)
    claim=Path(folder)/'question/reply-read-intent.json'
    require(not claim.exists() and not claim.is_symlink(), 'Original reply read cannot retry')
    stage=next(r for r in history if r['operation']=='staged')
    reference=stage['payload']['references']['reply'];raw=question_reference_bytes(reference)
    broker_intent=Path(broker_intent)
    require(broker_intent.name=='intent.json'
            and broker_intent.parent.parent==Path(folder)/'broker/root/actions'
            and re.fullmatch('[0-9]{6}',broker_intent.parent.name) is not None,
            'Original registered root broker action required')
    intent=strict.decoded(broker_intent.read_bytes())
    require(intent['request']=={'job':'root','op':'read_reply','data':{}}
            and intent['run_id']==state['run_id']
            and intent['configuration_sha256']==state['configuration_sha256'],
            'Exact current root reply-read action required')
    atomic_json(claim,{'broker_intent':question_reference(broker_intent),
        'reply':reference,'question_configuration':question_reference(Path(folder)/'question/configuration.json')},exclusive=True)
    question_validate(folder)
    return {'text':raw.decode('utf-8')}


def complete_question_reply_read(folder, root_capability, broker_receipt):
    """Claim and completed immutable broker result precede opening product work."""
    guard_question_operation(folder,'root',root_capability,'read_reply',_completion=True)
    state,control,history=_question_snapshot(folder)
    claim=strict.decoded((Path(folder)/'question/reply-read-intent.json').read_bytes())
    require(set(claim)=={'broker_intent','reply','question_configuration'}, 'Exact original reply claim required')
    intent_raw=question_reference_bytes(claim['broker_intent'])
    question_reference_bytes(claim['question_configuration'])
    raw=question_reference_bytes(claim['reply']);receipt=strict.decoded(Path(broker_receipt).read_bytes())
    require(Path(broker_receipt)==Path(claim['broker_intent']['path']).with_name('receipt.json')
            and type(receipt) is dict and set(receipt)=={'status','intent_sha256','finished_at','result'}
            and receipt.get('status')=='completed' and receipt['intent_sha256']==hashlib.sha256(intent_raw).hexdigest()
            and receipt['result']=={'text':raw.decode('utf-8')}, 'Complete original successful reply receipt required')
    import improvement_baseline_question_branch_v1 as branch
    ended=branch.finite(receipt['finished_at']);began=branch.finite(strict.decoded(intent_raw)['started_at'])
    require(control['original_started_at']<=began<=ended<control['original_deadline'],
            'Original reply receipt clock changed')
    _question_append(folder,control,history,'reply_read_completed',{
        'references':{'broker_receipt':question_reference(broker_receipt),'claim':question_reference(Path(folder)/'question/reply-read-intent.json')}})


def commit_question_no_more_delivery(folder, coordinator_capability, reason, commitment_reference):
    with question_operation_lock(folder):
        state,control,history=question_coordinator_auth(folder,coordinator_capability,closing=True)
        require(type(reason) is str and bool(reason.strip()), 'Explicit coordinator close reason required')
        commitment=strict.decoded(question_reference_bytes(commitment_reference))
        require(type(commitment) is dict and set(commitment)=={
            'schema_version','binding','coordinator_identity','native_source_entities','no_more_delivery','committed_at'}
            and type(commitment['schema_version']) is int and commitment['schema_version']==1
            and encoded(commitment['binding'])==encoded(control['binding'])
            and commitment['coordinator_identity']==control['coordinator_identity']
            and commitment['no_more_delivery'] is True
            and type(commitment['native_source_entities']) is dict and bool(commitment['native_source_entities']),
            'Exact coordinator no-more-delivery commitment required')
        import improvement_baseline_question_branch_v1 as branch
        at=branch.finite(commitment['committed_at'])
        require(control['original_started_at']<=at<=time.time(),'No-more-delivery commitment clock changed')
        for path,entity in commitment['native_source_entities'].items():
            question_verify_reference({'path':path,'entity':entity})
        path=Path(folder)/'question/no-more-delivery.json'
        atomic_json(path,{'schema_version':1,'binding':control['binding'],'reason':reason,
            'commitment':commitment_reference,'original_deadline':control['original_deadline'],
            'no_more_delivery':True,'committed_at':time.time()},exclusive=True)
        return question_reference(path)


def load(folder):return json.loads((Path(folder)/'state.json').read_bytes())


@contextlib.contextmanager
def lock(folder,name='state'):
    require(name in ('state','root','worker1','worker2'),'Unknown lock')
    with (Path(folder)/(name+'.lock')).open('a+b') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX);yield


def save(folder,state):atomic_json(Path(folder)/'state.json',state)


def event(folder,value):
    # Caller holds state lock; immutable numbered individual receipts.
    state=load(folder);number=state['events'];state['events']+=1
    atomic_json(Path(folder)/'events'/f'{number:05d}.json',dict(value,observed_at=time.time()),exclusive=True)
    save(folder,state)


def budget(state):
    remaining=state['deadline']-time.time();require(remaining>=1,'Original trajectory deadline exhausted')
    return remaining


def call(state,args,cleanup=False,check=True,seconds=30):
    return docker(args,timeout=seconds if cleanup else min(seconds,budget(state)),check=check)


def bounded_exec(folder,job,number,args,seconds):
    """Exact raw output preservation with shared 16MiB infrastructure limit."""
    directory=Path(folder)/'commands';directory.mkdir(exist_ok=True)
    paths={name:directory/f'{job}-{number:05d}.{name}' for name in ('stdout','stderr')}
    process=None;buffers={name:bytearray() for name in paths};error=None
    with paths['stdout'].open('xb') as stdout,paths['stderr'].open('xb') as stderr:
        selector=selectors.DefaultSelector();began=time.monotonic()
        try:
            process=subprocess.Popen(['docker']+args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            selector.register(process.stdout,selectors.EVENT_READ,('stdout',stdout))
            selector.register(process.stderr,selectors.EVENT_READ,('stderr',stderr))
            while selector.get_map():
                remaining=seconds-(time.monotonic()-began)
                if remaining<=0:raise TimeoutError('Command transport deadline')
                for key,_ in selector.select(timeout=min(remaining,0.2)):
                    raw=os.read(key.fileobj.fileno(),65536)
                    if not raw:selector.unregister(key.fileobj);continue
                    name,stream=key.data
                    if sum(map(len,buffers.values()))+len(raw)>16*1024**2:
                        raise ValueError('Command output budget exceeded; partial raw output retained')
                    stream.write(raw);buffers[name].extend(raw)
            remaining=seconds-(time.monotonic()-began)
            if remaining<=0:raise TimeoutError('Command receipt deadline')
            code=process.wait(timeout=remaining)
        except (TimeoutError,subprocess.TimeoutExpired,ValueError) as failure:
            error={'type':type(failure).__name__,'message':str(failure)};code=124 if isinstance(failure,(TimeoutError,subprocess.TimeoutExpired)) else 125
        finally:
            if process is not None:
                if process.poll() is None:process.kill()
                process.wait(timeout=5);process.stdout.close();process.stderr.close()
            selector.close()
            for stream in (stdout,stderr):stream.flush();os.fsync(stream.fileno())
    value={'exit_code':code,'stdout':buffers['stdout'].decode(errors='replace'),
           'stderr':buffers['stderr'].decode(errors='replace'),'output_complete':error is None,
           'raw_output':{name:{'path':str(path),'bytes':len(buffers[name]),
                              'sha256':hashlib.sha256(buffers[name]).hexdigest()} for name,path in paths.items()}}
    if error:value['transport_error']=error
    return value


def engine_capture(folder, state, job, args, category, cleanup=False, check=True):
    """Bounded original engine bytes, immutable receipt before interpretation."""
    require(category in ('inspect','create') and job in ('root','worker1','worker2'), 'Unknown engine capture')
    directory=Path(folder)/('engine-inspections' if category=='inspect' else 'engine-creations')/uuid.uuid4().hex
    directory.mkdir(parents=True)
    intent={'job':job,'args':args,'run_id':state['run_id'],'configuration_sha256':state['configuration_sha256'],
            'cleanup':cleanup,'started_at':time.time(),'native_qualified':False}
    atomic_json(directory/'intent.json',intent,exclusive=True)
    seconds=30 if cleanup else min(30,budget(state))
    value=bounded_exec(directory,job,0,args,seconds)
    receipt=dict(intent,finished_at=time.time(),result=value)
    atomic_json(directory/'receipt.json',receipt,exclusive=True)
    with lock(folder):
        event(folder,{'op':'engine_'+category+'_receipt','job':job,'args':args,
                      'receipt':str(directory/'receipt.json'),
                      'receipt_sha256':hashlib.sha256((directory/'receipt.json').read_bytes()).hexdigest()})
    require(cleanup or receipt['finished_at']<=state['deadline'], 'Original engine deadline exceeded; raw output retained')
    require(value['output_complete'] and not value.get('transport_error'), 'Engine transport incomplete; raw output retained')
    buffers={}
    for name in ('stdout','stderr'):
        pin=value['raw_output'][name];raw=Path(pin['path']).read_bytes()
        require(len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'], 'Engine raw receipt drift')
        buffers[name]=raw
    try:
        result=subprocess.CompletedProcess(['docker']+args,value['exit_code'],buffers['stdout'].decode('utf-8'),buffers['stderr'].decode('utf-8'))
    except UnicodeDecodeError as error:
        raise ValueError('Invalid engine UTF8; original raw output retained') from error
    result.raw_stdout=buffers['stdout'];result.raw_stderr=buffers['stderr'];result.engine_receipt=str(directory/'receipt.json')
    if check:result.check_returncode()
    return result


def engine_inspect(folder,state,job,target,cleanup=False,check=True):
    """Caller holds job lock; validate target before any query capture."""
    require(job in ('root','worker1','worker2'),'Unknown inspection job')
    row=state['jobs'].get(job,{})
    allowed={f'codify-optional-{state["run_id"]}-{job}',row.get('container'),row.get('container_id')} - {None}
    require(isinstance(target,str) and target in allowed,'Foreign inspection target')
    return engine_capture(folder,state,job,['inspect',target],'inspect',cleanup,check)


def engine_create(folder,state,job,args):
    """Private coordinator precursor. Public actors cannot call this API."""
    row=state['jobs'].get(job,{})
    require(state['phase'] in ('preparing','running') and row.get('status')=='creation_intent'
            and row.get('container_id') is None,'No new/replacement creation after binding')
    require(isinstance(args,list) and args[:3]==['create','--name',f'codify-optional-{state["run_id"]}-{job}'],
            'Wrong creation namespace')
    return engine_capture(folder,state,job,args,'create')


def inspect(folder,state,job,cleanup=False):
    row=state['jobs'][job];values=strict.decoded(engine_inspect(folder,state,job,row['container_id'],cleanup).stdout)
    require(isinstance(values,list) and len(values)==1 and isinstance(values[0],dict),'One owned engine object required')
    info=values[0]
    labels=info['Config'].get('Labels',{})
    require(info['Id']==row['container_id'] and info['Image']==IMAGE and
            labels.get('codify.optional.run')==state['run_id'] and
            labels.get('codify.optional.configuration')==state['configuration_sha256'] and
            labels.get('codify.optional.job')==job and info['HostConfig']['NetworkMode']=='none',
            'Owned container identity/image/labels/network changed')
    expected={'/work/repo':(str(Path(folder)/job/'repo'),True),
              '/eval-input':(str(Path(folder)/job/'input'),False)}
    require(len(info['Mounts'])==2 and {m['Destination'] for m in info['Mounts']}==set(expected),'Unexpected mounts')
    for mount in info['Mounts']:
        path,writable=expected[mount['Destination']]
        require(mount['Type']=='bind' and mount['Source']==path and mount['RW'] is writable,
                'Mount source/permission changed')
    return info


def status(folder,job,value):
    with lock(folder):
        state=load(folder);state['jobs'][job]['status']=value;save(folder,state)


def stop(folder,job,cleanup=False):
    """Caller holds this job lock. Stopped Docker is not terminal native proof."""
    state=load(folder);info=inspect(folder,state,job,cleanup)
    if info['State']['Running']:
        try:call(state,['stop','-t','2',state['jobs'][job]['container_id']],cleanup,seconds=10)
        except (subprocess.TimeoutExpired,subprocess.CalledProcessError):
            call(state,['kill',state['jobs'][job]['container_id']],cleanup,seconds=10)
    require(not inspect(folder,state,job,cleanup)['State']['Running'],'Filesystem not stopped')
    status(folder,job,'stopped')


def start(folder,job):
    state=load(folder);require(state['phase'] in ('preparing','running'),'Runtime closing or failed')
    inspect(folder,state,job)
    call(state,['start',state['jobs'][job]['container_id']])
    require(inspect(folder,state,job)['State']['Running'],'Start unconfirmed');status(folder,job,'running')


def guard_question_worker_backend(folder, job):
    """Trusted worker provisioning must still wait for original native binding."""
    if job=='root':return  # Initial trusted root provisioning precedes its UUID.
    config=strict.decoded((Path(folder)/'configuration.json').read_bytes())
    state=load(folder)
    require(type(config) is dict and state['configuration_sha256']==hashlib.sha256(encoded(config)).hexdigest(),
            'Original backend configuration required')
    if config['case'] in ('B03','B04'):
        value=question_validate(folder)
        require(value is not None, 'Question worker backend requires committed native control before effects')
        _,_,history=value
        require(not history or history[-1]['operation']=='reply_read_completed',
                'Question worker backend closed until original complete reply read')


def provision(folder,job,task):
    guard_question_worker_backend(folder,job)
    with lock(folder,job):
        return _provision(folder,job,task)


def _provision(folder,job,task):
    guard_question_worker_backend(folder,job)
    state=load(folder);cap=secrets.token_hex(24);name='codify-optional-'+state['run_id']+'-'+job
    controls=Path(folder)/job/'input';controls.mkdir();(controls/'request.txt').write_text(task)
    found=engine_inspect(folder,state,job,name,check=False)
    require(found.returncode!=0 and 'No such object:' in found.stderr,'New owned namespace required')
    with lock(folder):
        state=load(folder);require(state['phase'] in ('preparing','running'),'Runtime closing or failed')
        require(job not in state['jobs'],'No job retry/replacement')
        state['jobs'][job]={'container':name,'container_id':None,'capability_sha256':hashed(cap),
                            'status':'creation_intent','commands':0};save(folder,state)
    created=engine_create(folder,state,job,['create','--name',name,'--network','none',
                '--label','codify.optional.run='+state['run_id'],
                '--label','codify.optional.configuration='+state['configuration_sha256'],
                '--label','codify.optional.job='+job,
                '-v',str(Path(folder)/job/'repo')+':/work/repo',
                '-v',str(controls)+':/eval-input:ro','-w','/work/repo',
                '-e','GIT_OPTIONAL_LOCKS=0','-e','PYTHONDONTWRITEBYTECODE=1',IMAGE,'sleep','infinity'])
    created_id=created.raw_stdout.decode('ascii').strip()
    require(re.fullmatch('[0-9a-f]{64}',created_id) is not None,'Exact engine create ID unavailable; creation intent retained')
    with lock(folder):
        state=load(folder);state['jobs'][job]['container_id']=created_id;save(folder,state)
        event(folder,{'op':'created_identity_receipt','job':job,'container_id':created_id,'create_stdout':created.stdout,'create_stderr':created.stderr})
    values=strict.decoded(engine_inspect(folder,state,job,created_id).stdout)
    require(isinstance(values,list) and len(values)==1 and isinstance(values[0],dict),'One created engine object required')
    info=values[0]
    require(info['Id']==created_id,'Original create receipt/engine identity changed')
    inspect(folder,load(folder),job);start(folder,job)
    with lock(folder):event(folder,{'op':'provisioned','job':job,'container_id':info['Id']})
    return cap


def command(folder,job,cap,text,seconds=120):
    guard_question_operation(folder, job, cap, 'exec')
    folder=Path(folder).resolve();require(job in ('root','worker1','worker2'),'Unknown job')
    require(isinstance(cap,str) and isinstance(text,str) and len(text.encode())<=65536 and
            type(seconds) is int and 1<=seconds<=120,'Invalid command')
    with lock(folder,job):
        with lock(folder):
            state=load(folder);row=state['jobs'].get(job)
            require(row is not None and secrets.compare_digest(hashed(cap),row['capability_sha256']),
                    'Wrong job capability')
            require(state['phase'] in ('preparing','running') and row['status']=='running','Closed job')
            duration=min(seconds,int(budget(state))-3);require(duration>=1,'No termination/receipt budget')
            row['commands']+=1;number=row['commands'];save(folder,state)
            event(folder,{'op':'command_intent','job':job,'number':number,'command':text,'seconds':duration})
        info=inspect(folder,state,job);require(info['State']['Running'],'Job stopped')
        begin=time.time();duration=min(duration,int(budget(state))-3);require(duration>=1,'Intent exhausted budget')
        value=bounded_exec(folder,job,number,['exec',row['container_id'],'timeout','--signal=TERM','--kill-after=2s',
                              str(duration)+'s','bash','-lc','cd /work/repo && '+text],min(duration+3,budget(state)))
        end=time.time()
        if end>state['deadline']:value.update(observed_exit_code=value['exit_code'],exit_code=124,deadline_exceeded=True)
        value.update(job=job,number=number,command=text,started_at=begin,finished_at=end,
                     native_qualified=False,scope_checked=False)
        with lock(folder):event(folder,dict(value,op='command_result'))
        # Host reads are deliberately deferred until an owned stopped snapshot.
        return value


def snapshot(folder,job,restart=False,cleanup=False):
    """Caller holds job lock; actor cannot dispatch another same-job command."""
    state=load(folder);stop(folder,job,cleanup)
    inventory=source.inventory(Path(folder)/job/'repo',None if cleanup else state['deadline'])
    baseline=state['jobs'][job].get('baseline')
    scope_error=None
    try:
        if baseline is not None:
            if job=='root':
                source.check_changes(baseline,inventory,state['editable_paths'])
                registry.check_root_changes(registry.read(Path(folder)/'registry'),inventory['source_entities'])
            else:
                row=registry.read(Path(folder)/'registry')['workers'][job]
                source.check_changes(baseline,inventory,row['scope'])
    except ValueError as error:
        scope_error={'type':type(error).__name__,'message':str(error)}
        failure(folder,error)
    path=Path(folder)/'snapshots'/(job+'-'+uuid.uuid4().hex);path.parent.mkdir(exist_ok=True)
    source.export(Path(folder)/job/'repo',inventory,path,None if cleanup else state['deadline'])
    receipt={'job':job,'export':str(path),'inventory':inventory,'scope_error':scope_error,
             'container_id':state['jobs'][job]['container_id']}
    with lock(folder):event(folder,dict(receipt,op='stopped_snapshot'))
    if scope_error is not None and not cleanup:raise ValueError(scope_error['message'])
    if restart:start(folder,job)
    return receipt


def create(folder,starting,case,condition,task,editable_paths,record_ownership=None, *, worker_cap):
    started=time.time();folder=Path(folder).resolve();starting=Path(starting).resolve()
    execution=catalog.declared_execution(case,condition,worker_cap)
    require(isinstance(editable_paths,list) and all(type(p) is str for p in editable_paths)
            and sorted(editable_paths)==sorted(execution['editable_paths']), 'Exact qualified editable paths required')
    editable_paths=sorted(editable_paths)
    require(catalog.encoded(catalog.materializer.inventory(starting))==catalog.encoded(execution['public_inventory']),
            'Starting source differs from current independently qualified public fixture')
    require(time.time()<started+1200, 'Original validation clock exhausted')
    require(not folder.exists() and folder!=starting and starting not in folder.parents,'Exclusive external runtime required')
    require(shutil.disk_usage(folder.parent).free>=3*1024**3,'Insufficient allocation disk')
    config={'case':case,'condition':condition,'image':IMAGE,'task':task,'editable_paths':editable_paths,
            'started_at':started,'deadline':started+1200,'model':'gpt-6.1-sol','effort':'medium',
            'worker_cap':worker_cap,'retries':0,'public_contract':execution}
    require(record_ownership is None or callable(record_ownership),'Valid ownership callback required')
    folder.mkdir()
    if record_ownership is not None:record_ownership(folder)
    (folder/'events').mkdir();(folder/'root').mkdir()
    atomic_json(folder/'configuration.json',config,exclusive=True)
    state={'run_id':uuid.uuid4().hex,'configuration_sha256':hashlib.sha256(encoded(config)).hexdigest(),
           'started_at':started,'deadline':started+1200,'phase':'preparing','editable_paths':editable_paths,
           'jobs':{},'events':0,'first_error':None,'native_qualified':False,'comparison_eligible':False,
           'worker_cap':worker_cap,'retries':0}
    save(folder,state)
    try:
        initial=source.inventory(starting,state['deadline']);source.export(starting,initial,folder/'root/repo',state['deadline'])
        cap=provision(folder,'root',task)
        for text in ('git init -q','git config diff.autoRefreshIndex false','git -c user.name=Fixture -c user.email=fixture@localhost add .',
                     'git -c user.name=Fixture -c user.email=fixture@localhost commit -q -m baseline',
                     '/sdks/flutter/bin/flutter pub get --offline'):
            result=command(folder,'root',cap,text);require(result['exit_code']==0,'Fixed preparation failed: '+text)
        with lock(folder,'root'):
            receipt=snapshot(folder,'root')
            registry.create(folder/'registry',state['run_id'],case,condition,started,
                            receipt['inventory']['source_entities'],editable_paths,worker_cap=worker_cap)
            with lock(folder):
                state=load(folder);state['jobs']['root']['baseline']=receipt['inventory'];state['phase']='running';save(folder,state)
            start(folder,'root')
        return {'root_capability':cap,'folder':str(folder),'run_id':state['run_id']}
    except BaseException as error:
        failure(folder,error);raise


def declared_runtime(folder, root_cap):
    """Read-only cap/config provenance guard before locks, snapshots or intents."""
    folder=Path(folder);state=load(folder)
    row=state.get('jobs',{}).get('root')
    require(isinstance(root_cap,str) and isinstance(row,dict)
            and secrets.compare_digest(hashed(root_cap),row['capability_sha256']), 'Root capability required')
    config=strict.decoded((folder/'configuration.json').read_bytes())
    require(state['configuration_sha256']==hashlib.sha256(encoded(config)).hexdigest(), 'Runtime configuration drift')
    execution=config['public_contract']
    require(type(config.get('worker_cap')) is int and config['worker_cap'] in (0,2)
            and type(state.get('worker_cap')) is int and state['worker_cap']==config['worker_cap']
            and type(config.get('retries')) is int and config['retries']==0
            and type(state.get('retries')) is int and state['retries']==0
            and config['model']=='gpt-6.1-sol' and config['effort']=='medium'
            and execution['case_id']==config['case'] and execution['condition']==config['condition']
            and execution['worker_cap']==config['worker_cap']
            and sorted(execution['editable_paths'])==config['editable_paths']==state['editable_paths'],
            'Declared fixed runtime contract changed')
    members=registry.read(folder/'registry');registered=members['configuration']
    require(registered['case_id']==config['case'] and registered['condition']==config['condition']
            and registered['worker_cap']==config['worker_cap'] and registered['editable_paths']==config['editable_paths']
            and state['run_id']==registered['run_id']
            and registered['started_at']==config['started_at']==state['started_at']
            and registered['deadline']==config['deadline']==state['deadline'], 'Original runtime registry clock/scope/cap changed')
    return state,members


def worker(folder,root_cap,goal,scope,mode='write'):
    guard_question_operation(folder, 'root', root_cap, 'worker')
    folder=Path(folder).resolve()
    initial,_=declared_runtime(folder,root_cap)
    require(initial['worker_cap']==2, 'Solo cap0 denies worker before root stop or snapshot')
    with lock(folder,'root'):
        state,members=declared_runtime(folder,root_cap)
        require(state['worker_cap']==2, 'Solo cap0 forbids worker')
        require(len(members['workers'])<state['worker_cap'], 'No replacement or third worker')
        require(secrets.compare_digest(hashed(root_cap),state['jobs']['root']['capability_sha256']),
                                   'Root capability required')
        require(state['phase']=='running','Closed allocation')
        require('integration_release' not in registry.read(folder/'registry'),'No allocation after final integration')
        receipt=snapshot(folder,'root')
        try:
            members=registry.reserve_worker(folder/'registry',goal,scope,receipt['inventory']['source_entities'],mode)
            job=list(members['workers'])[-1]
            (folder/job).mkdir();shutil.copytree(receipt['export'],folder/job/'repo')
            if (folder/'root/repo/.git').exists():
                shutil.copytree(folder/'root/repo/.git',folder/job/'repo/.git')
            cap=provision(folder,job,goal)
            prepared=command(folder,job,cap,'/sdks/flutter/bin/flutter pub get --offline')
            require(prepared['exit_code']==0 and prepared['output_complete'],'Worker preparation failed')
            with lock(folder,job):
                sealed=snapshot(folder,job)
                require(sealed['inventory']['source_entities']==members['workers'][job]['snapshot'],
                        'Worker preparation changed reserved source')
                with lock(folder):
                    state=load(folder);state['jobs'][job]['baseline']=sealed['inventory'];save(folder,state)
                start(folder,job)
            return {'job':job,'capability':cap,'snapshot_sha256':members['workers'][job]['snapshot_sha256']}
        except BaseException as error:
            if 'job' in locals():registry.allocation_error(folder/'registry',job,error)
            failure(folder,error);raise
        finally:
            if load(folder)['phase']=='running':start(folder,'root')


def role(folder, job, cap):
    question_validate(folder)
    state=load(folder);row=state['jobs'].get(job)
    require(job in ('root','worker1','worker2') and isinstance(cap,str) and row is not None
            and secrets.compare_digest(hashed(cap),row['capability_sha256']), 'Wrong role capability')
    require(state['phase']=='running' and row['status']=='running','Closed role job')
    budget(state)
    return state


def seal(folder, job, cap, findings=''):
    guard_question_operation(folder, job, cap, 'seal')
    folder=Path(folder).resolve();require(job in ('worker1','worker2'),'Only allocated worker may seal')
    with lock(folder,job), registry.locked(folder/'registry'):
        state=role(folder,job,cap);members=registry.read(folder/'registry')
        require('integration_release' not in members and job in members['workers'],'Closed or unallocated contribution')
        require(isinstance(findings,str) and len(findings.encode())<=1024*1024
                and (members['workers'][job]['mode']!='review' or findings.strip()), 'Invalid worker findings')
        try:
            receipt=snapshot(folder,job)
            info=inspect(folder,load(folder),job);require(not info['State']['Running'],'Sealing requires exact stopped container')
            reference=artifacts.seal(members,job,receipt['export'],folder/'contributions'/(job+'.json'),findings)
            require(source.inventory(folder/job/'repo',state['deadline'])==receipt['inventory'],'Worker checkout drift during seal')
            with lock(folder):
                current=load(folder);current['jobs'][job].update(status='sealed_stopped',sealed_artifact=reference,views=[]);save(folder,current)
                event(folder,{'op':'sealed_contribution','job':job,'artifact':reference,
                              'source_inventory_sha256':registry.sha(receipt['inventory']), 'native_qualified':False})
            return {'job':job,'artifact':reference,'native_qualified':False}
        except BaseException as error:
            failure(folder,error);raise


def sealed(folder, members, slot):
    require(slot in ('worker1','worker2') and slot in members['workers'],'Unallocated contribution slot')
    row=load(folder)['jobs'].get(slot)
    require(row is not None and row['status']=='sealed_stopped' and 'sealed_artifact' in row,'Original stopped contribution required')
    reference=row['sealed_artifact']
    require(reference['path']==str(Path(folder)/'contributions'/(slot+'.json'))
            and artifacts.pin(reference['path'])==reference,'Owned original contribution changed')
    return reference,row


def view(folder, root_cap, slot):
    guard_question_operation(folder, 'root', root_cap, 'view')
    folder=Path(folder).resolve()
    with lock(folder,'root'):
        role(folder,'root',root_cap);members=registry.read(folder/'registry')
        require('integration_release' not in members,'Views closed after final integration')
        reference,row=sealed(folder,members,slot)
        destination=folder/'views'/slot/(uuid.uuid4().hex+'.json');destination.parent.mkdir(parents=True,exist_ok=True)
        view_reference,receipt=artifacts.view(members,reference,destination)
        with lock(folder):
            current=load(folder);current['jobs'][slot]['views'].append(view_reference);save(folder,current)
            event(folder,{'op':'contribution_view','slot':slot,'view':view_reference,'native_qualified':False})
        return {'view':view_reference,'receipt':receipt,'native_qualified':False}


def decide(folder, root_cap, slot, view_reference, decision, reason):
    guard_question_operation(folder, 'root', root_cap, 'decide')
    folder=Path(folder).resolve()
    with lock(folder,'root'):
        role(folder,'root',root_cap);members=registry.read(folder/'registry')
        require('integration_release' not in members,'Decisions closed after final integration')
        reference,row=sealed(folder,members,slot)
        require(isinstance(view_reference,dict) and any(encoded(view_reference)==encoded(v) for v in row['views']),
                'Only original returned view may support a decision')
        result=artifacts.decide(members,reference,view_reference,decision,reason,
                folder/'registry/decisions'/(slot+'.json'),registry_folder=folder/'registry')
        with lock(folder):event(folder,{'op':'contribution_decision','slot':slot,'decision':result,'native_qualified':False})
        return {'decision':result,'native_qualified':False}


def integrate(folder, root_cap):
    guard_question_operation(folder, 'root', root_cap, 'integrate')
    folder=Path(folder).resolve()
    with contextlib.ExitStack() as stack:
        stack.enter_context(lock(folder,'root'));state=role(folder,'root',root_cap)
        members=registry.read(folder/'registry');require('integration_release' not in members,'No repeat final integration')
        for slot in members['workers']:
            stack.enter_context(lock(folder,slot));sealed(folder,members,slot)
            info=inspect(folder,load(folder),slot);require(not info['State']['Running'],'Worker source fence missing')
        decisions=[artifacts.pin(folder/'registry/decisions'/(slot+'.json')) for slot in members['workers']]
        original_pins=[]
        def record_intent(reference):
            original_pins.append(reference)
            with lock(folder):event(folder,{'op':'raw_integration_intent','intent':reference,'native_qualified':False})
        try:
            before=snapshot(folder,'root')
            transaction=checkout.install(folder/'root/repo',members,decisions,state['jobs']['root']['baseline'],
                before['inventory'],folder/'raw-integration',folder/'registry',deadline=state['deadline'],record_intent=record_intent)
            transaction_reference=checkout.file_pin(transaction)
            commitment_reference=checkout.file_pin(transaction.with_name(transaction.stem+'.commit.json'))
            released=registry.release_after_install(folder/'registry',transaction_reference,original_pins[0],commitment_reference)
            with lock(folder):
                current=load(folder);current['integration']={'transaction':transaction_reference,'intent':original_pins[0],
                    'commitment':commitment_reference,'release_head_sha256':released['head_sha256']};save(folder,current)
                event(folder,{'op':'raw_integration_released','proofs':current['integration'],'native_qualified':False})
            budget(load(folder));start(folder,'root')
            return {'transaction':transaction_reference,'release_head_sha256':released['head_sha256'],
                    'native_qualified':False,'runtime_qualified':False,'comparison_eligible':False}
        except BaseException as error:
            failure(folder,error);raise


def verify(folder, root_cap):
    guard_question_operation(folder, 'root', root_cap, 'verify')
    """Fixed public commands only; fresh independent grading remains external."""
    folder=Path(folder).resolve();role(folder,'root',root_cap)
    public=command(folder,'root',root_cap,'/sdks/flutter/bin/flutter test --no-pub --machine')
    require(public['output_complete'] and not public.get('transport_error'),'Public verification transport incomplete')
    analyzed=command(folder,'root',root_cap,'/sdks/flutter/bin/flutter analyze --no-pub')
    require(analyzed['output_complete'] and not analyzed.get('transport_error'),'Analysis transport incomplete')
    return {'public':public,'analyze':analyzed,'native_qualified':False,'fresh_verifier_qualified':False,
            'software_pass_qualified':False}


def failure(folder,error):
    with lock(folder):
        state=load(folder)
        if state['first_error'] is None:state['first_error']={'type':type(error).__name__,'message':str(error)}
        state['phase']='failed_preservation_required';save(folder,state)


def recover_created_identity(folder, state, job):
    """Recover a captured successful create ID even if qualification failed late."""
    candidates=set()
    for path in sorted((Path(folder)/'events').glob('*.json')):
        event_value=strict.decoded(path.read_bytes())
        if event_value.get('op')!='engine_create_receipt' or event_value.get('job')!=job:
            continue
        receipt_path=Path(event_value['receipt'])
        require(receipt_path.parent.parent==Path(folder)/'engine-creations'
                and receipt_path.name=='receipt.json' and receipt_path.is_file() and not receipt_path.is_symlink(),
                'Creation receipt locator changed')
        raw=receipt_path.read_bytes();require(hashlib.sha256(raw).hexdigest()==event_value['receipt_sha256'],'Creation receipt changed')
        receipt=strict.decoded(raw)
        require(receipt['job']==job and receipt['run_id']==state['run_id']
                and receipt['configuration_sha256']==state['configuration_sha256']
                and receipt['args'][:3]==['create','--name',state['jobs'][job]['container']], 'Creation receipt origin changed')
        value=receipt['result']
        if value.get('output_complete') is not True or type(value.get('exit_code')) is not int or value['exit_code']!=0 or value.get('transport_error'):
            continue
        pin=value['raw_output']['stdout'];stdout_path=Path(pin['path'])
        require(stdout_path==receipt_path.parent/'commands'/(job+'-00000.stdout')
                and stdout_path.is_file() and not stdout_path.is_symlink(),'Creation stdout locator changed')
        stdout=stdout_path.read_bytes()
        require(type(pin['bytes']) is int and len(stdout)==pin['bytes'] and hashlib.sha256(stdout).hexdigest()==pin['sha256'], 'Creation stdout changed')
        try:identity=stdout.decode('ascii').strip()
        except UnicodeDecodeError:continue
        if re.fullmatch('[0-9a-f]{64}',identity):candidates.add(identity)
    require(len(candidates)<=1,'Ambiguous captured creation identities')
    if not candidates:return None
    identity=next(iter(candidates))
    with lock(folder):
        current=load(folder);require(current['jobs'][job]['container_id'] in (None,identity),'Recorded creation identity drift')
        current['jobs'][job]['container_id']=identity;save(folder,current)
        event(folder,{'op':'recovered_creation_identity','job':job,'container_id':identity})
    return identity


def cleanup(folder):
    """Actor-free caller now; future caller must first prove native closure."""
    folder=Path(folder).resolve()
    with lock(folder):state=load(folder);state['phase']='closing';save(folder,state)
    errors=[]
    for job in list(state['jobs']):
        with lock(folder,job):
            try:
                current=load(folder);row=current['jobs'][job]
                if row['container_id'] is None:
                    recover_created_identity(folder,current,job)
                    current=load(folder);row=current['jobs'][job]
                if row['status']=='removed':
                    require(row['container_id'] is not None,'Previously removed creation identity remains unknown')
                    absent=engine_inspect(folder,current,job,row['container_id'] or row['container'],cleanup=True,check=False)
                    require(absent.returncode!=0 and 'No such object:' in absent.stderr,'Previously removed resource reappeared')
                    continue
                if row['container_id'] is None:
                    found=engine_inspect(folder,current,job,row['container'],cleanup=True,check=False)
                    if found.returncode:
                        require('No such object:' in found.stderr,'Creation absence unknown')
                        raise ValueError('Dispatched creation identity unresolved; name absence cannot prove removal')
                    with lock(folder):
                        current=load(folder);values=strict.decoded(found.stdout)
                        require(isinstance(values,list) and len(values)==1 and isinstance(values[0],dict),'One reconciled engine object required')
                        current['jobs'][job]['container_id']=values[0]['Id'];save(folder,current)
                snapshot(folder,job,cleanup=True)
                current=load(folder);inspect(folder,current,job,cleanup=True)
                archive_tmp(folder,current['jobs'][job]['container_id'],job)
                call(current,['rm',current['jobs'][job]['container_id']],cleanup=True)
                absent=engine_inspect(folder,current,job,current['jobs'][job]['container_id'],cleanup=True,check=False)
                require(absent.returncode!=0 and 'No such object:' in absent.stderr,'Exact removal unconfirmed')
                status(folder,job,'removed')
                with lock(folder):event(folder,{'op':'removed','job':job,'container_id':current['jobs'][job]['container_id']})
            except BaseException as error:errors.append({'job':job,'type':type(error).__name__,'message':str(error)})
    with lock(folder):
        current=load(folder);current['cleanup_errors']=errors
        current['phase']='preservation_failed' if errors else 'closed_docker_only';save(folder,current)
    require(not errors,'Stopped owned resources retained for unpreserved diagnostics: '+str(errors))
    return current
