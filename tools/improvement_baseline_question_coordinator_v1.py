"""ROOT-owned preparation and one-shot native launch for the baseline pilot.

Native API calls remain with ROOT. These records do not authenticate their own
provenance. A separately frozen ROOT verifier must authenticate every transition.
Question binding/review/continuation and final closure are not yet implemented.
"""
import hashlib
import inspect
import marshal
from pathlib import Path
import time

import improvement_baseline_comparison_inputs_v1 as inputs
import improvement_baseline_runtime_v4 as runtime
import improvement_baseline_native_dispatch_v4 as dispatch
from improvement_software_artifacts_v3 import atomic_json

ROOT=inputs.ROOT
require=runtime.require
encoded=runtime.encoded


def callback_contract(callback):
    require(inspect.isfunction(callback) and callback.__closure__ is None
            and callback.__qualname__==callback.__name__
            and callback.__defaults__ is None and callback.__kwdefaults__ is None,
            'Frozen top-level verifier function without closure/default state required')
    source=inspect.getsourcefile(callback)
    require(source is not None,'Original verifier source required')
    return {'module':callback.__module__,'qualname':callback.__qualname__,
            'code_sha256':hashlib.sha256(marshal.dumps(callback.__code__)).hexdigest(),
            'source_reference':runtime.question_reference(Path(source).resolve())}


def authenticate(callback, frozen_contract, purpose, proof):
    require(encoded(callback_contract(callback))==encoded(frozen_contract),
            'Frozen verifier implementation changed')
    require(callback(purpose,proof) is None,'Verifier must authenticate or raise, never return JSON approval')
    require(encoded(callback_contract(callback))==encoded(frozen_contract),
            'Verifier changed during authentication')


def source_fence(entities):
    require(type(entities) is dict and bool(entities),'Separately frozen full source graph required')
    require(str(Path(__file__).resolve().relative_to(ROOT)) in entities,'Coordinator must be in frozen graph')
    for name,entity in entities.items():
        require(type(name) is str and bool(name),'Exact source graph path required')
        path=Path(name)
        if not path.is_absolute():path=ROOT/path
        runtime.question_verify_reference({'path':str(path),'entity':entity})


def preparation_preflight(row, frozen_skill_inventory, opaque_assignment_reference,
                          source_entities, *, coordinator_verifier, verifier_contract):
    started=time.time()
    inputs.row_valid(row)
    row=runtime.strict.decoded(encoded(row))
    task=inputs.public_task(row);public=inputs.public_contract(row)
    source_entities=runtime.strict.decoded(encoded(source_entities));source_fence(source_entities)
    if row['condition']=='A':require(frozen_skill_inventory is None,'No-skill control cannot export a skill')
    else:
        require(type(frozen_skill_inventory) is dict,'Frozen selected skill inventory required')
        skill=ROOT/'snapshots'/row['condition']
        require(encoded(runtime.source.inventory(skill))==encoded(frozen_skill_inventory),'Original selected skill changed')
    if row['case_id'] in ('B03','B04'):
        require(type(opaque_assignment_reference) is dict,'Preassigned opaque reply reference required')
        runtime.question_verify_reference(opaque_assignment_reference)
    else:require(opaque_assignment_reference is None,'Fully specified task has no owner assignment')
    value={'schema_version':1,'row':row,'task':task,'public_contract':public,
           'frozen_skill_inventory':frozen_skill_inventory,'opaque_assignment_reference':opaque_assignment_reference,
           'source_entities':source_entities,'verifier_contract':verifier_contract,
           'preparation_started_at':started,'actual_native_authenticated':False,'model_pilot_admitted':False}
    folder=ROOT/'runtime'/row['run_id']
    require(not folder.exists(),'Preflight must precede SDK runtime allocation')
    authenticate(coordinator_verifier,verifier_contract,'pre_sdk_freeze',value)
    source_fence(source_entities)
    directory=ROOT/'results/improvement-v1/baseline-comparison-preparation-v1'/row['run_id']
    directory.parent.mkdir(exist_ok=True);directory.mkdir()
    path=directory/'preflight.json';atomic_json(path,value,exclusive=True)
    return runtime.question_reference(path)


def prepare(preflight_reference, root_capability, *, coordinator_verifier, verifier_contract):
    frozen=runtime.strict.decoded(runtime.question_reference_bytes(preflight_reference))
    row=frozen['row'];inputs.row_valid(row)
    require(encoded(frozen['verifier_contract'])==encoded(verifier_contract),'Original preflight verifier changed')
    source_fence(frozen['source_entities'])
    folder=ROOT/'runtime'/row['run_id']
    state,members=runtime.declared_runtime(folder,root_capability)
    configuration=runtime.strict.decoded((folder/'configuration.json').read_bytes())
    require(set(state['jobs'])=={'root'} and not members['workers'] and state['phase']=='running',
            'SDK prepared root only, no worker/native allocation before adoption')
    require(configuration['task']==frozen['task'] and configuration['case']==row['case_id']
            and configuration['condition']==row['condition'] and type(configuration['worker_cap']) is int
            and configuration['worker_cap']==row['worker_cap']
            and encoded(configuration['public_contract'])==encoded(frozen['public_contract']),
            'Original prepared runtime differs from frozen row/task/public contract')
    require(type(frozen['preparation_started_at']) in (int,float)
            and frozen['preparation_started_at']<=state['started_at']<time.time()<state['deadline'],
            'Adopt original SDK clock; never reset preparation or model deadline')
    skill=folder/'root/repo/.agents/skills/codify'
    if row['condition']=='A':require(not skill.exists(),'No-skill checkout contains selected skill')
    else:require(encoded(runtime.source.inventory(skill,state['deadline']))==encoded(frozen['frozen_skill_inventory']),
                 'Prepared protected skill differs from frozen selected source')
    authenticate(coordinator_verifier,verifier_contract,'adopt_prepared_runtime',
                 {'preflight_reference':preflight_reference,'row':row,'configuration':configuration,'state':state})
    source_fence(frozen['source_entities'])
    directory=folder/'coordinator';directory.mkdir()
    value={'schema_version':1,'preflight_reference':preflight_reference,'row':row,
           'configuration_reference':runtime.question_reference(folder/'configuration.json'),
           'original_started_at':state['started_at'],'original_deadline':state['deadline'],
           'preparation_started_at':frozen['preparation_started_at'],'native_qualified':False}
    path=directory/'prepared.json';atomic_json(path,value,exclusive=True)
    return runtime.question_reference(path)


def launch_root(prepared_reference, observer_ready_reference, root_capability, *,
                coordinator_id, coordinator_verifier, verifier_contract):
    prepared=runtime.strict.decoded(runtime.question_reference_bytes(prepared_reference))
    frozen=runtime.strict.decoded(runtime.question_reference_bytes(prepared['preflight_reference']))
    row=prepared['row'];inputs.row_valid(row);folder=ROOT/'runtime'/row['run_id']
    source_fence(frozen['source_entities'])
    require(encoded(verifier_contract)==encoded(frozen['verifier_contract']),'Original verifier changed')
    runtime.question_verify_reference(prepared['configuration_reference'])
    state,members=runtime.declared_runtime(folder,root_capability)
    require(state['phase']=='running' and set(state['jobs'])=={'root'} and not members['workers'],
            'Original prepared root before all native allocation required')
    ready=runtime.strict.decoded(runtime.question_reference_bytes(observer_ready_reference))
    require(observer_ready_reference['path']==str(folder/'native-observer/ready.json')
            and ready['root_path']==row['actor_path'] and ready['parent_id']==coordinator_id
            and ready['root_native_id'] is None and type(ready['observer_restarts']) is int and ready['observer_restarts']==0
            and encoded(ready['original_started_at'])==encoded(prepared['original_started_at'])
            and encoded(ready['deadline'])==encoded(prepared['original_deadline'])
            and state['started_at']<=ready['started_at']<=time.time()<state['deadline'],
            'Original observer ready before original root spawn required')
    authenticate(coordinator_verifier,verifier_contract,'original_observer_ready',
                 {'prepared_reference':prepared_reference,'observer_ready_reference':observer_ready_reference,'ready':ready})
    source_fence(frozen['source_entities'])
    path=folder/'coordinator/launch-intent.json'
    require(not path.exists(),'Original launch intent cannot be retried after uncertain ACK')
    dispatch_row=runtime.strict.decoded((folder/'native-dispatch/intents/root.json').read_bytes())
    config=runtime.strict.decoded((folder/'native-dispatch/configuration.json').read_bytes())
    require(config['root_path']==row['actor_path'] and config['coordinator_id']==coordinator_id
            and config['runtime_configuration_sha256']==dispatch.runtime_identity(folder,members['configuration'])
            and dispatch_row['intent']['agent_path']==row['actor_path']
            and dispatch_row['bootstrap_sha256']==hashlib.sha256(dispatch_row['native_bootstrap'].encode()).hexdigest(),
            'Original canonical dispatch and bootstrap required')
    arguments={'task_name':row['actor_path'].removeprefix('/root/'),'message':dispatch_row['native_bootstrap'],
               'fork_turns':'none','model':'gpt-6.1-sol','reasoning_effort':'medium'}
    authenticate(coordinator_verifier,verifier_contract,'one_original_root_launch',
                 {'prepared_reference':prepared_reference,'observer_ready_reference':observer_ready_reference,'arguments':arguments})
    atomic_json(path,{'schema_version':1,'arguments':arguments,'prepared_reference':prepared_reference,
                     'observer_ready_reference':observer_ready_reference,'status':'dispatch_once_or_preserve_uncertain_ack',
                     'started_at':time.time(),'actual_native_authenticated':False},exclusive=True)
    return {'intent_reference':runtime.question_reference(path),'arguments':arguments,'native_qualified':False}
