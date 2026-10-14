"""ROOT-authenticated actor-free SDK cleanup, never native-actor cleanup.

External ROOT caller trust is required. The original parent source must prove
that the exact product root has never been dispatched, including uncertain ACK.
Only captured exact create IDs and the original owned root job are eligible.
Unknown create identity stays unresolved. No broad prune, retry or actor stop.
"""
import copy
import hashlib
from pathlib import Path
import re

import improvement_baseline_root_source_v4 as source
import improvement_baseline_failure_close_v5 as closer
import improvement_baseline_question_coordinator_v11 as coordinator

runtime=closer.runtime
ROOT=coordinator.ROOT
require=runtime.require
encoded=runtime.encoded
CALIBRATION_NAME='baseline-startup-cleanup-qualification-v1'
CALIBRATION_ACTOR='/root/baseline_startup_cleanup_qualification_v1'


def source_fence(entities):
    coordinator.source_fence(entities,[runtime.question_reference(Path(__file__).resolve())])


def no_product_spawn(owner,actor_path,previous=b'',capability_sha256=None):
    require(type(actor_path) is str and re.fullmatch('/root/[A-Za-z0-9_]+',actor_path),
            'Exact original product root path required')
    raw,entity=owner.parent()
    require(raw.startswith(previous),'Original parent source rewritten or truncated during startup cleanup')
    # A partial tail could contain a dispatched but not yet fully recorded call.
    # Retain resources until the original complete parent prefix is available.
    require(raw.endswith(b'\n'),'Actor-free cleanup cannot use a partial current parent tail')
    for event in source.membership.original.core.parse(raw):
        payload=event['payload']
        launch=source.membership.original.core.route(payload,'collaboration','spawn_agent')
        delivery=source.membership.original.core.route(payload,'collaboration','followup_task') or source.membership.original.core.route(payload,'collaboration','send_message')
        if payload.get('type')=='function_call' and (launch or delivery):
            args=source.membership.original.core.decode(payload['arguments'])
            name=args.get('task_name')
            require(not launch or name!=actor_path.removeprefix('/root/'),
                    'Original root dispatch exists; actual native closure is required even without ACK')
            if capability_sha256 is not None:
                candidates=re.findall(r'(?<![0-9a-f])[0-9a-f]{48}(?![0-9a-f])',str(args.get('message','')))
                require(not any(runtime.hashed(value)==capability_sha256 for value in candidates),
                        'Original SDK capability was delivered to a native actor; actual closure required')
    return {'original_parent_entity':entity,'parent_bytes':len(raw),
            'parent_sha256':hashlib.sha256(raw).hexdigest(),'actor_path':actor_path,
            'native_actor_dispatch_observed':False},raw


def original_actor(folder,config):
    """Namespace and frozen original preparation select the actor, not a claim."""
    rows=[row for row in coordinator.inputs.sequence() if folder.name==row['run_id']]
    if rows:
        require(len(rows)==1,'Ambiguous original runtime row')
        row=rows[0]
        path=ROOT/'results/improvement-v1/baseline-comparison-preparation-v4'/row['run_id']/'preflight.json'
        reference=runtime.question_reference(path)
        preflight=runtime.strict.decoded(runtime.question_reference_bytes(reference))
        require(encoded(preflight['row'])==encoded(row)
                and preflight['preparation_started_at']<=config['started_at']
                and preflight['task']==config['task']
                and encoded(preflight['public_contract'])==encoded(config['public_contract']),
                'Original pre-SDK registered preparation required')
        expected=row['actor_path'];refs=[reference]
    else:
        require(folder.name==CALIBRATION_NAME,'Unknown startup namespace cannot authorize cleanup')
        row=next(r for r in coordinator.inputs.sequence() if r['case_id']=='B01'
                 and r['condition']=='A' and r['worker_cap']==0)
        expected=CALIBRATION_ACTOR;refs=[]
    require(config['case']==row['case_id'] and config['condition']==row['condition']
            and type(config['worker_cap']) is int and config['worker_cap']==row['worker_cap']
            and config['task']==coordinator.inputs.public_task(row)
            and encoded(config['public_contract'])==encoded(coordinator.inputs.public_contract(row)),
            'Original fixed namespace/case/condition/cap/task/public execution required')
    return expected,refs


def create_receipt_references(folder,state):
    refs=[];identities=set();job=state['jobs']['root']
    for path in sorted((folder/'events').glob('*.json')):
        event=runtime.strict.decoded(path.read_bytes())
        if event.get('op')!='engine_create_receipt':continue
        require(event.get('job')=='root','Actor-free cleanup cannot include worker creation')
        reference=runtime.question_reference(path);receipt_path=Path(event['receipt'])
        require(receipt_path.parent.parent==folder/'engine-creations' and receipt_path.name=='receipt.json',
                'Original root create receipt locator required')
        receipt_ref=runtime.question_reference(receipt_path)
        require(receipt_ref['entity']['sha256']==event['receipt_sha256'],'Original engine creation receipt changed')
        receipt=runtime.strict.decoded(runtime.question_reference_bytes(receipt_ref))
        require(receipt['job']=='root' and receipt['run_id']==state['run_id']
                and receipt['configuration_sha256']==state['configuration_sha256']
                and receipt['args'][:3]==['create','--name',job['container']],
                'Original root engine creation origin required')
        result=receipt['result']
        require(result['output_complete'] is True and type(result['exit_code']) is int
                and result['exit_code']==0 and not result.get('transport_error'),
                'Original successful fully captured engine create required')
        stdout=result['raw_output']['stdout'];stdout_ref=runtime.question_reference(Path(stdout['path']))
        require(stdout_ref['path']==str(receipt_path.parent/'commands/root-00000.stdout')
                and stdout_ref['entity']['bytes']==stdout['bytes']
                and stdout_ref['entity']['sha256']==stdout['sha256'],'Original captured create stdout required')
        identity=runtime.question_reference_bytes(stdout_ref).decode('ascii').strip()
        require(re.fullmatch('[0-9a-f]{64}',identity) and identity==job['container_id'],
                'Exact original captured root create ID required')
        identities.add(identity);refs.extend([reference,receipt_ref,stdout_ref])
    require(len(identities)==1,'Exactly one original captured root create identity required')
    return refs


def close(folder,actor_path,owner,original_state_reference,configuration_reference,*,frozen_sources,observer=None):
    """Preserve original startup error/resources, then remove only exact SDK ID."""
    folder=Path(folder)
    require(folder.is_absolute() and folder==folder.resolve(strict=True) and folder.parent==ROOT/'runtime',
            'Original owned runtime namespace required')
    source_fence(frozen_sources)
    state_path=runtime.question_verify_reference(original_state_reference)
    require(state_path!=folder/'state.json' and state_path.is_relative_to(ROOT/'results/improvement-v1'),
            'Separately preserved immutable ROOT state snapshot required')
    original=runtime.strict.decoded(runtime.question_reference_bytes(original_state_reference))
    require(set(original['jobs'])=={'root'} and type(original['jobs']['root'].get('container_id')) is str
            and re.fullmatch('[0-9a-f]{64}',original['jobs']['root']['container_id']),
            'Original root-only captured exact container ID required; unresolved identity is retained')
    require(configuration_reference['path']==str(folder/'configuration.json'),'Original runtime configuration reference required')
    config=runtime.strict.decoded(runtime.question_reference_bytes(configuration_reference))
    expected,allocation_refs=original_actor(folder,config)
    require(actor_path==expected,'Original namespace-selected actor path required; aliases cannot establish absence')
    require(original['configuration_sha256']==hashlib.sha256(encoded(config)).hexdigest()
            and encoded(original['started_at'])==encoded(config['started_at'])
            and encoded(original['deadline'])==encoded(config['deadline']), 'Original configuration/clock required')
    jobs=closer.immutable_job_fields(original)
    refs=allocation_refs+create_receipt_references(folder,original)
    cap_hash=original['jobs']['root']['capability_sha256']
    original_commands=original['jobs']['root']['commands']
    require(type(cap_hash) is str and re.fullmatch('[0-9a-f]{64}',cap_hash)
            and type(original_commands) is int and original_commands>=0,'Typed original startup capability hash and command count required')
    initial_origin,parent_prefix=no_product_spawn(owner,actor_path,capability_sha256=cap_hash)
    if observer is not None:
        require(observer.folder==folder and observer.value['row']['actor_path']==actor_path,
                'Same original owned observer required for startup cleanup')
        require(observer.proc is not None and observer.proc.poll() is not None,
                'Original observer must be confirmed terminated before SDK cleanup')
        outcome=observer.wait(1)
        require(outcome['completed'] is True,'Original observer termination unconfirmed')
    else:require(not (folder/'native-observer').exists(),
                 'Observer evidence exists; original process termination must be authenticated')
    before=runtime.load(folder)
    run_fields={key:copy.deepcopy(original[key]) for key in ('run_id','configuration_sha256','started_at','deadline','editable_paths','worker_cap','retries')}
    require(encoded(closer.immutable_job_fields(before))==encoded(jobs),'Original SDK root ownership changed')
    require(type(before['jobs']['root']['commands']) is int and before['jobs']['root']['commands']==original_commands,
            'SDK commands appeared after the original actor-free startup snapshot')
    directory=folder/'actor-free-startup-close';directory.mkdir()
    runtime.atomic_json(directory/'preparation.json',{'actor_path':actor_path,'original_state_reference':original_state_reference,
        'configuration_reference':configuration_reference,'creation_references':refs,'original_origin':initial_origin,
        'original_first_error':original.get('first_error'),'model_pilot_admitted':False},exclusive=True)
    def fence():
        nonlocal parent_prefix
        source_fence(frozen_sources);_,parent_prefix=no_product_spawn(owner,actor_path,parent_prefix,cap_hash)
        runtime.question_verify_reference(original_state_reference);runtime.question_verify_reference(configuration_reference)
        for reference in refs:runtime.question_verify_reference(reference)
        current=runtime.load(folder)
        require(encoded({key:current[key] for key in run_fields})==encoded(run_fields)
                and encoded(closer.immutable_job_fields(current))==encoded(jobs), 'Original startup SDK identity/clock/scope changed')
        require(type(current['jobs']['root']['commands']) is int
                and current['jobs']['root']['commands']==original_commands,
                'SDK commands appeared after the original actor-free startup snapshot')
        if (folder/'registry').exists():require(not runtime.registry.read(folder/'registry')['workers'],
                                              'Actor-free startup cannot include worker reservations')
        if observer is not None:require(observer.proc.poll() is not None,'Original observer process became live')
    result=closer.fenced_cleanup(folder,fence,original_jobs=jobs)
    value={'cleanup_kind':'actor_free_startup_only','owned_cleanup_verified':result['owned_cleanup_verified'],
        'errors':result['errors'],'blocked_jobs':result['blocked_jobs'],'original_first_error':original.get('first_error'),
        'model_allocations':0,'software':None,'model_pilot_admitted':False,'native_actor_cleanup_authorized':False}
    runtime.atomic_json(directory/'result.json',value,exclusive=True)
    return value
