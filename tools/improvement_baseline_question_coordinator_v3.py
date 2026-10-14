"""ROOT-owned preparation and one-shot native launch for the baseline pilot.

Native API calls remain with ROOT. These records do not authenticate their own
provenance. A separately frozen ROOT verifier must authenticate every transition.
Question binding/review/continuation and final closure are not yet implemented.
"""
import hashlib
import ast
import inspect
import marshal
from pathlib import Path
import time
from datetime import datetime

import improvement_baseline_comparison_inputs_v1 as inputs
import improvement_baseline_runtime_v4 as runtime
import improvement_baseline_native_dispatch_v5 as dispatch
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


def source_closure(references=()):
    paths=set();todo=[Path(__file__).resolve()];tools=ROOT/'tools'
    for reference in references:
        path=runtime.question_verify_reference(reference)
        require(path.is_relative_to(ROOT) and path.suffix=='.py','ROOT-owned callback Python source required')
        todo.append(path)
    while todo:
        path=todo.pop()
        if path in paths:continue
        paths.add(path)
        for node in ast.walk(ast.parse(path.read_bytes())):
            modules=[entry.name for entry in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) else []
            for name in modules:
                if name:
                    target=tools/(name.split('.')[0]+'.py')
                    if target.is_file():todo.append(target)
    return {str(path.relative_to(ROOT)):runtime.question_file_entity(path) for path in sorted(paths)}


def source_fence(entities, references=()):
    require(type(entities) is dict and bool(entities),'Separately frozen full source graph required')
    require(encoded(entities)==encoded(source_closure(references)),'Exact current complete coordinator tool import graph required')
    for name,entity in entities.items():
        require(type(name) is str and bool(name),'Exact source graph path required')
        path=Path(name)
        if not path.is_absolute():path=ROOT/path
        runtime.question_verify_reference({'path':str(path),'entity':entity})


def preparation_preflight(row, frozen_skill_inventory, opaque_assignment_reference,
                          source_entities, *, observer_authority_reference, coordinator_verifier, verifier_contract):
    started=time.time()
    inputs.row_valid(row)
    row=runtime.strict.decoded(encoded(row))
    runtime.question_verify_reference(observer_authority_reference)
    task=inputs.public_task(row);public=inputs.public_contract(row)
    source_entities=runtime.strict.decoded(encoded(source_entities));source_fence(source_entities,[observer_authority_reference,verifier_contract['source_reference']])
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
           'observer_authority_reference':observer_authority_reference,
           'preparation_started_at':started,'actual_native_authenticated':False,'model_pilot_admitted':False}
    folder=ROOT/'runtime'/row['run_id']
    require(not folder.exists(),'Preflight must precede SDK runtime allocation')
    authenticate(coordinator_verifier,verifier_contract,'pre_sdk_freeze',value)
    source_fence(source_entities,[observer_authority_reference,verifier_contract['source_reference']])
    directory=ROOT/'results/improvement-v1/baseline-comparison-preparation-v1'/row['run_id']
    directory.parent.mkdir(exist_ok=True);directory.mkdir()
    path=directory/'preflight.json';atomic_json(path,value,exclusive=True)
    return runtime.question_reference(path)


def prepare(preflight_reference, root_capability, *, coordinator_verifier, verifier_contract):
    frozen=runtime.strict.decoded(runtime.question_reference_bytes(preflight_reference))
    row=frozen['row'];inputs.row_valid(row)
    require(encoded(frozen['verifier_contract'])==encoded(verifier_contract),'Original preflight verifier changed')
    source_fence(frozen['source_entities'],[frozen['observer_authority_reference'],frozen['verifier_contract']['source_reference']])
    folder=ROOT/'runtime'/row['run_id']
    state,members=runtime.declared_runtime(folder,root_capability)
    runtime.question_validate(folder)
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
    source_fence(frozen['source_entities'],[frozen['observer_authority_reference'],frozen['verifier_contract']['source_reference']])
    directory=folder/'coordinator';directory.mkdir()
    value={'schema_version':1,'preflight_reference':preflight_reference,'row':row,
           'configuration_reference':runtime.question_reference(folder/'configuration.json'),
           'original_started_at':state['started_at'],'original_deadline':state['deadline'],
           'preparation_started_at':frozen['preparation_started_at'],'native_qualified':False}
    path=directory/'prepared.json';atomic_json(path,value,exclusive=True)
    return runtime.question_reference(path)


def root_dispatch_inputs(folder, row, root_capability, coordinator_id, registered, expected_task):
    dispatch_path=folder/'native-dispatch/configuration.json'
    intent_path=folder/'native-dispatch/intents/root.json'
    configuration=runtime.strict.decoded(dispatch.original_broker.original(dispatch_path))
    value=runtime.strict.decoded(dispatch.original_broker.original(intent_path))
    require(set(configuration)=={'run_id','configuration_sha256','runtime_configuration_sha256','root_path',
            'coordinator_id','model','effort','broker_script','native_qualified','comparison_eligible'}
            and configuration['native_qualified'] is False and configuration['comparison_eligible'] is False,
            'Exact original native dispatch schema required')
    require(set(value)=={'intent','native_bootstrap','bootstrap_sha256','provision','dispatch_configuration_pin',
            'native_qualified','comparison_eligible'} and value['native_qualified'] is False
            and value['comparison_eligible'] is False,'Exact original prepared native row required')
    runtime_hash=dispatch.runtime_identity(folder,registered)
    require(configuration['root_path']==row['actor_path'] and configuration['coordinator_id']==coordinator_id
            and configuration['run_id']==registered['run_id']
            and configuration['configuration_sha256']==dispatch.registry.sha(registered)
            and configuration['runtime_configuration_sha256']==runtime_hash
            and configuration['model']=='gpt-6.1-sol' and configuration['effort']=='medium'
            and configuration['broker_script']==str(dispatch.BROKER_SCRIPT)
            and encoded(value['dispatch_configuration_pin'])==encoded(dispatch.checkout.file_pin(dispatch_path)),
            'Original native configuration or preparation pin changed')
    intent=value['intent'];provision=value['provision']
    request=dispatch.original_broker.original(folder/'root/input/request.txt')
    require(type(expected_task) is str and request==expected_task.encode('utf-8'),
            'Original native public request differs from pre-SDK frozen task')
    digest=hashlib.sha256(request).hexdigest()
    require(set(intent)=={'job','agent_path','at','public_request_sha256','configuration_sha256','reservation_worker_sha256'}
            and intent['job']=='root' and intent['agent_path']==row['actor_path']
            and intent['public_request_sha256']==digest and intent['configuration_sha256']==dispatch.registry.sha(registered)
            and intent['reservation_worker_sha256'] is None
            and set(provision)=={'job','agent_path','intent_sha256','public_request_sha256','status'}
            and provision['job']=='root' and provision['agent_path']==row['actor_path']
            and provision['intent_sha256']==dispatch.registry.sha(intent)
            and provision['public_request_sha256']==digest and provision['status']=='prepared',
            'Original root allocation/provision/request changed')
    require(type(intent['at']) is str and registered['started_at']<=datetime.fromisoformat(intent['at'].replace('Z','+00:00')).timestamp()<registered['deadline'],
            'Original allocation timestamp outside shared clock')
    require(value['bootstrap_sha256']==hashlib.sha256(value['native_bootstrap'].encode()).hexdigest()
            and value['native_bootstrap']==dispatch.bootstrap(folder.name,'root',root_capability,row['worker_cap']),
            'Original bootstrap differs from canonical role instructions')
    return value,configuration


def launch_root(prepared_reference, observer_ready_reference, root_capability, *,
                coordinator_id, coordinator_verifier, verifier_contract):
    prepared=runtime.strict.decoded(runtime.question_reference_bytes(prepared_reference))
    frozen=runtime.strict.decoded(runtime.question_reference_bytes(prepared['preflight_reference']))
    row=prepared['row'];inputs.row_valid(row);folder=ROOT/'runtime'/row['run_id']
    source_fence(frozen['source_entities'],[frozen['observer_authority_reference'],frozen['verifier_contract']['source_reference']])
    require(encoded(verifier_contract)==encoded(frozen['verifier_contract']),'Original verifier changed')
    runtime.question_verify_reference(prepared['configuration_reference'])
    state,members=runtime.declared_runtime(folder,root_capability)
    runtime.question_validate(folder)
    require(state['phase']=='running' and set(state['jobs'])=={'root'} and not members['workers'],
            'Original prepared root before all native allocation required')
    require(encoded(prepared['original_started_at'])==encoded(state['started_at'])
            and encoded(prepared['original_deadline'])==encoded(state['deadline']),
            'Prepared original clock differs from current runtime')
    ready=runtime.strict.decoded(runtime.question_reference_bytes(observer_ready_reference))
    require(set(ready)=={'started_at','original_started_at','deadline','root_path','parent_id','root_native_id',
            'observer_restarts','actor_control','authority_callback_reference','native_qualified'}
            and ready['native_qualified'] is False
            and type(ready['started_at']) in (int,float),'Exact original observer-ready schema required')
    require(ready.get('actor_control') is False
            and encoded(ready.get('authority_callback_reference'))==encoded(frozen['observer_authority_reference'])
            and observer_ready_reference['path']==str(folder/'native-observer/ready.json')
            and ready['root_path']==row['actor_path'] and ready['parent_id']==coordinator_id
            and ready['root_native_id'] is None and type(ready['observer_restarts']) is int and ready['observer_restarts']==0
            and encoded(ready['original_started_at'])==encoded(prepared['original_started_at'])
            and encoded(ready['deadline'])==encoded(prepared['original_deadline'])
            and state['started_at']<=ready['started_at']<=time.time()<state['deadline'],
            'Original observer ready before original root spawn required')
    authenticate(coordinator_verifier,verifier_contract,'original_observer_ready',
                 {'prepared_reference':prepared_reference,'observer_ready_reference':observer_ready_reference,'ready':ready})
    source_fence(frozen['source_entities'],[frozen['observer_authority_reference'],frozen['verifier_contract']['source_reference']])
    path=folder/'coordinator/launch-intent.json'
    require(not path.exists(),'Original launch intent cannot be retried after uncertain ACK')
    dispatch_row,config=root_dispatch_inputs(folder,row,root_capability,coordinator_id,members['configuration'],frozen['task'])
    arguments={'task_name':row['actor_path'].removeprefix('/root/'),'message':dispatch_row['native_bootstrap'],
               'fork_turns':'none','model':'gpt-6.1-sol','reasoning_effort':'medium'}
    authenticate(coordinator_verifier,verifier_contract,'one_original_root_launch',
                 {'prepared_reference':prepared_reference,'observer_ready_reference':observer_ready_reference,'arguments':arguments})
    source_fence(frozen['source_entities'],[frozen['observer_authority_reference'],frozen['verifier_contract']['source_reference']])
    runtime.question_validate(folder)
    runtime.declared_runtime(folder,root_capability)
    require(time.time()<state['deadline'],'Original launch deadline exhausted during verifier')
    current_dispatch,current_config=root_dispatch_inputs(folder,row,root_capability,coordinator_id,members['configuration'],frozen['task'])
    require(encoded(current_dispatch)==encoded(dispatch_row) and encoded(current_config)==encoded(config),
            'Original dispatch changed during final launch verification')
    runtime.question_validate(folder)
    require(time.time()<state['deadline'],'Original clock exhausted before launch intent')
    atomic_json(path,{'schema_version':1,'arguments':arguments,'prepared_reference':prepared_reference,
                     'observer_ready_reference':observer_ready_reference,'status':'dispatch_once_or_preserve_uncertain_ack',
                     'started_at':time.time(),'actual_native_authenticated':False},exclusive=True)
    require(time.time()<state['deadline'],'Original launch intent preserved after clock exhausted; do not dispatch')
    return {'intent_reference':runtime.question_reference(path),'arguments':arguments,'native_qualified':False}
