"""ROOT-owned startup composition, with no native API calls or admission.

The calling ROOT must authenticate its own environment and separately freeze
this driver graph. No JSON document establishes caller trust. Product actors
must not receive capabilities, anchors, grading data or this control graph.
The prebirth observer runs in a fresh ROOT-owned process. Preparation returns
private control data to ROOT only, never directly to an evaluated actor.
"""
import copy
import os
import json
import sys
from pathlib import Path

import improvement_baseline_root_controller_v8 as controller
import improvement_baseline_skill_export_v4 as skills

coordinator=controller.coordinator
runtime=controller.runtime
require=controller.require
ROOT=controller.ROOT
encoded=controller.encoded


def driver_fence(frozen_driver_sources):
    reference=runtime.question_reference(Path(__file__).resolve())
    coordinator.source_fence(frozen_driver_sources,[reference])


def prepare_startup(row,owner,skill_inventory,assignment_reference,*,frozen_driver_sources):
    """One synchronous preparation; actual actor allocation remains external."""
    driver_fence(frozen_driver_sources)
    row=copy.deepcopy(row);coordinator.inputs.row_valid(row)
    skill_inventory=copy.deepcopy(skill_inventory);assignment_reference=copy.deepcopy(assignment_reference)
    reference=runtime.question_reference(Path(controller.__file__).resolve())
    graph=coordinator.source_closure([reference])
    context=controller.StartupController(row,owner,None,graph,skill_inventory,assignment_reference)
    controller.configure(context)
    contract=coordinator.callback_contract(controller.verify)
    preflight=coordinator.preparation_preflight(row,skill_inventory,assignment_reference,graph,
        observer_authority_reference=reference,coordinator_verifier=controller.verify,verifier_contract=contract)
    driver_fence(frozen_driver_sources)
    public=coordinator.inputs.public_contract(row)
    owned=None;stage='sdk_create';result=None
    def record_ownership(folder):
        nonlocal owned
        require(Path(folder)==context.folder,'Original create-owned folder required')
        owned=context.folder/'root-driver';owned.mkdir()
        runtime.atomic_json(owned/'ownership.json',{'folder':str(folder),'row':row,
            'preflight_reference':preflight,'model_pilot_admitted':False},exclusive=True)
    try:
        with skills.skill_export(row,context.folder,skill_inventory):
            result=runtime.create(context.folder,ROOT/public['public_root'],row['case_id'],row['condition'],
                coordinator.inputs.public_task(row),public['editable_paths'],record_ownership,worker_cap=row['worker_cap'])
        require(owned is not None,'Original runtime ownership callback required')
        # Recoverable ROOT-only control secret. This file is never mounted in
        # the product container or included in product input/evidence exports.
        fd=os.open(owned/'private-create-result.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(encoded(result))
        stage='post_create_source_fence';driver_fence(frozen_driver_sources)
        stage='bind';binding=context.bind_runtime_capability(result,preflight)
        stage='prepare';prepared=coordinator.prepare(preflight,result['root_capability'],coordinator_verifier=controller.verify,verifier_contract=contract)
        stage='pre_register_source_fence';driver_fence(frozen_driver_sources)
        stage='register';coordinator.dispatch.original_broker.register(context.folder,'root',result['root_capability'])
        stage='pre_dispatch_source_fence';driver_fence(frozen_driver_sources)
        stage='dispatch';coordinator.dispatch.create(context.folder,row['actor_path'],owner.value['parent_native_id'],result['root_capability'])
        stage='final_prepared';context.prepared();driver_fence(frozen_driver_sources)
    except BaseException as error:
        if owned is not None:
            try:
                runtime.atomic_json(owned/'failure.json',{'stage':stage,
                    'error':{'type':type(error).__name__,'message':str(error)},
                    'actual_sdk_create_returned':result is not None,'cleanup_authorized':False,
                    'cleanup_required':True,'model_pilot_admitted':False},exclusive=True)
            except BaseException as preservation_error:
                diagnostic={'reason':'driver_failure_record_unavailable','stage':stage,
                    'original_error_type':type(error).__name__,
                    'preservation_error_type':type(preservation_error).__name__,'cleanup_required':True}
                error.driver_preservation_error=diagnostic
                try:sys.stderr.write(json.dumps(diagnostic)+'\n')
                except BaseException:pass
        raise
    return {'prepared_reference':prepared,'binding_reference':binding,'root_capability':result['root_capability'],
            'verifier_contract':contract,'observer_authority_reference':reference,'row':row,
            'actual_native_authenticated':False,'model_pilot_admitted':False}


def restore_observer(binding_reference,capability,owner,*,frozen_driver_sources):
    """Fresh trusted process adopts the exact original successful binding."""
    driver_fence(frozen_driver_sources)
    require(controller._context is None,'Observer restoration requires a fresh trusted ROOT process')
    binding=runtime.strict.decoded(runtime.question_reference_bytes(binding_reference))
    require(type(binding) is dict and set(binding)=={'schema_version','row','preflight_reference',
        'unbound_context_sha256','capability_sha256','runtime_run_id','root_job','configuration_reference',
        'original_started_at','original_deadline','actual_native_authenticated','model_pilot_admitted'},
        'Exact original startup binding schema required')
    row=binding['row'];coordinator.inputs.row_valid(row);folder=ROOT/'runtime'/row['run_id']
    require(binding_reference['path']==str(folder/'root-startup-binding/binding.json')
            and type(binding['schema_version']) is int and binding['schema_version']==1
            and binding['actual_native_authenticated'] is False and binding['model_pilot_admitted'] is False,
            'Original ROOT startup binding reference required')
    preflight=runtime.strict.decoded(runtime.question_reference_bytes(binding['preflight_reference']))
    require(encoded(preflight['row'])==encoded(row)
            and binding['preflight_reference']['path']==str(ROOT/'results/improvement-v1/baseline-comparison-preparation-v4'/row['run_id']/'preflight.json'),
            'Original observer preflight row/path required')
    reference=runtime.question_reference(Path(controller.__file__).resolve())
    require(encoded(preflight['verifier_contract'])==encoded(coordinator.callback_contract(controller.verify))
            and encoded(preflight['observer_authority_reference'])==encoded(reference),
            'Original callback contract required in observer process')
    context=controller.StartupController(row,owner,None,preflight['source_entities'],
        preflight['frozen_skill_inventory'],preflight['opaque_assignment_reference'])
    context.current()
    parent,_=owner.parent()
    for event in controller.source.membership.original.core.parse(controller.source.complete_prefix(parent)):
        payload=event['payload']
        if payload.get('type')=='function_call' and controller.source.membership.original.core.route(payload,'collaboration','spawn_agent'):
            args=controller.source.membership.original.core.decode(payload['arguments'])
            require(args.get('task_name')!=row['actor_path'].removeprefix('/root/'),
                    'Observer restoration must precede the original native root spawn')
    require(controller.source.membership.original.core.digest(context.unbound_context_commitment)==binding['unbound_context_sha256'],
            'Original unbound ROOT context changed')
    runtime.question_verify_reference(binding['configuration_reference'])
    require(type(capability) is str and runtime.hashed(capability)==binding['capability_sha256'],
            'Original actual root capability required in observer process')
    state,members=runtime.declared_runtime(folder,capability)
    require(state['run_id']==binding['runtime_run_id'] and not members['workers']
            and encoded(state['jobs']['root'])==encoded(binding['root_job'])
            and encoded(state['started_at'])==encoded(binding['original_started_at'])
            and encoded(state['deadline'])==encoded(binding['original_deadline']),
            'Original bound root job/clock required before observer readiness')
    info=runtime.inspect(folder,state,'root');require(info['State']['Running'] is True,'Actual original SDK root must run')
    # This is a validated reconstruction in a fresh trusted process, never a
    # rebind of an existing configured controller or a new allocation.
    restored=controller.StartupController(row,owner,capability,preflight['source_entities'],
        preflight['frozen_skill_inventory'],preflight['opaque_assignment_reference'])
    restored.prepared()
    require(encoded(restored.configuration_reference)==encoded(binding['configuration_reference']),
            'Original observer configuration pin required')
    skill=folder/'root/repo/.agents/skills/codify'
    if row['condition']=='A':require(not skill.exists(),'No-skill observer cannot adopt a selected skill')
    else:require(encoded(runtime.source.inventory(skill,state['deadline']))==encoded(preflight['frozen_skill_inventory']),
                 'Original protected skill required in observer process')
    driver_fence(frozen_driver_sources);controller.configure(restored)
    return {'context':restored,'authority_reference':reference}


def supervise_original(binding_reference,capability,owner,*,frozen_driver_sources):
    installed=restore_observer(binding_reference,capability,owner,frozen_driver_sources=frozen_driver_sources)
    context=installed['context']
    return controller.watch.supervise(context.folder,context.row['actor_path'],owner.value['parent_native_id'],
        validated_authority=controller.observer_authority,authority_callback_reference=installed['authority_reference'])


def prepare_launch(prepared_reference,ready_reference,capability,owner,*,frozen_driver_sources):
    driver_fence(frozen_driver_sources)
    result=coordinator.launch_root(prepared_reference,ready_reference,capability,
        coordinator_id=owner.value['parent_native_id'],coordinator_verifier=controller.verify,
        verifier_contract=coordinator.callback_contract(controller.verify))
    driver_fence(frozen_driver_sources)
    return result
