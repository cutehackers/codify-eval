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

import improvement_baseline_root_source_v3 as source
import improvement_baseline_failure_close_v4 as closer
import improvement_baseline_question_coordinator_v8 as coordinator

runtime=closer.runtime
ROOT=coordinator.ROOT
require=runtime.require
encoded=runtime.encoded


def source_fence(entities):
    coordinator.source_fence(entities,[runtime.question_reference(Path(__file__).resolve())])


def no_product_spawn(owner,actor_path):
    require(type(actor_path) is str and re.fullmatch('/root/[A-Za-z0-9_]+',actor_path),
            'Exact original product root path required')
    raw,entity=owner.parent()
    # A partial tail could contain a dispatched but not yet fully recorded call.
    # Retain resources until the original complete parent prefix is available.
    require(raw.endswith(b'\n'),'Actor-free cleanup cannot use a partial current parent tail')
    for event in source.membership.original.core.parse(raw):
        payload=event['payload']
        if payload.get('type')=='function_call' and source.membership.original.core.route(payload,'collaboration','spawn_agent'):
            args=source.membership.original.core.decode(payload['arguments'])
            name=args.get('task_name')
            require(name!=actor_path.removeprefix('/root/'),
                    'Original root dispatch exists; actual native closure is required even without ACK')
    return {'original_parent_entity':entity,'parent_bytes':len(raw),
            'parent_sha256':hashlib.sha256(raw).hexdigest(),'actor_path':actor_path,
            'native_actor_dispatch_observed':False}


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
    original=runtime.strict.decoded(runtime.question_reference_bytes(original_state_reference))
    require(set(original['jobs'])=={'root'} and type(original['jobs']['root'].get('container_id')) is str
            and re.fullmatch('[0-9a-f]{64}',original['jobs']['root']['container_id']),
            'Original root-only captured exact container ID required; unresolved identity is retained')
    require(configuration_reference['path']==str(folder/'configuration.json'),'Original runtime configuration reference required')
    config=runtime.strict.decoded(runtime.question_reference_bytes(configuration_reference))
    require(original['configuration_sha256']==hashlib.sha256(encoded(config)).hexdigest()
            and encoded(original['started_at'])==encoded(config['started_at'])
            and encoded(original['deadline'])==encoded(config['deadline']), 'Original configuration/clock required')
    jobs=closer.immutable_job_fields(original)
    refs=create_receipt_references(folder,original)
    initial_origin=no_product_spawn(owner,actor_path)
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
    directory=folder/'actor-free-startup-close';directory.mkdir()
    runtime.atomic_json(directory/'preparation.json',{'actor_path':actor_path,'original_state_reference':original_state_reference,
        'configuration_reference':configuration_reference,'creation_references':refs,'original_origin':initial_origin,
        'original_first_error':original.get('first_error'),'model_pilot_admitted':False},exclusive=True)
    def fence():
        source_fence(frozen_sources);no_product_spawn(owner,actor_path)
        runtime.question_verify_reference(original_state_reference);runtime.question_verify_reference(configuration_reference)
        for reference in refs:runtime.question_verify_reference(reference)
        current=runtime.load(folder)
        require(encoded({key:current[key] for key in run_fields})==encoded(run_fields)
                and encoded(closer.immutable_job_fields(current))==encoded(jobs), 'Original startup SDK identity/clock/scope changed')
        if (folder/'registry').exists():require(not runtime.registry.read(folder/'registry')['workers'],
                                              'Actor-free startup cannot include worker reservations')
        if observer is not None:require(observer.proc.poll() is not None,'Original observer process became live')
    result=closer.fenced_cleanup(folder,fence,original_jobs=jobs)
    value={'cleanup_kind':'actor_free_startup_only','owned_cleanup_verified':result['owned_cleanup_verified'],
        'errors':result['errors'],'blocked_jobs':result['blocked_jobs'],'original_first_error':original.get('first_error'),
        'model_allocations':0,'software':None,'model_pilot_admitted':False,'native_actor_cleanup_authorized':False}
    runtime.atomic_json(directory/'result.json',value,exclusive=True)
    return value
