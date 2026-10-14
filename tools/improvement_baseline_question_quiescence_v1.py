"""ROOT-owned first-turn quiescence for prospective question cap0 runs.

This component grants no reply, reviewer, allocation or comparison authority.
The caller must already be the trusted original ROOT coordinator. Real native
origin and first completion are checked before any owned Docker effects.
"""
import copy
from pathlib import Path
import time

import improvement_baseline_question_coordinator_v12 as coordinator
import improvement_baseline_root_source_v4 as source

runtime=coordinator.runtime
require=runtime.require
encoded=runtime.encoded


def validate_frontier(row, prepared, state, members, control, history, parent_id):
    """Pure boundary check. This does not authenticate caller or native bytes."""
    coordinator.inputs.row_valid(row)
    require(row['case_id'] in ('B03','B04') and type(row['worker_cap']) is int
            and row['worker_cap']==0, 'First quiescence supports registered question cap0 only')
    require(encoded(prepared['row'])==encoded(row)
            and state['phase']=='running' and set(state['jobs'])=={'root'}
            and state['jobs']['root']['status'] in ('running','stopped')
            and not members['workers'] and not members['active_leases'],
            'Original root-only first frontier required')
    binding=control['binding']
    require(type(history) is list and not history and binding['run_id']==row['run_id']
            and binding['case_id']==row['case_id'] and binding['agent_path']==row['actor_path']
            and binding['parent_native_uuid']==parent_id
            and binding['root_native_uuid']!=parent_id,
            'Committed original question binding without prior pause required')
    require(encoded(state['started_at'])==encoded(prepared['original_started_at'])
            ==encoded(control['original_started_at'])
            and encoded(state['deadline'])==encoded(prepared['original_deadline'])
            ==encoded(control['original_deadline'])
            and type(state['worker_cap']) is int and state['worker_cap']==0
            and type(control['worker_cap']) is int and control['worker_cap']==0,
            'Original question clock and cumulative cap required')
    require(control['root_capability_sha256']==state['jobs']['root']['capability_sha256'],
            'Original root capability binding required')
    return copy.deepcopy(binding)


def quiesce_first(prepared_reference, root_capability, coordinator_capability,
                  *, owner, root_locator, frozen_sources):
    require(isinstance(owner,source.RootSource), 'Trusted original ROOT source object required')
    coordinator.source_fence(frozen_sources,[runtime.question_reference(Path(__file__).resolve())])
    prepared=runtime.strict.decoded(runtime.question_reference_bytes(prepared_reference))
    row=prepared['row'];folder=coordinator.ROOT/'runtime'/row['run_id']
    require(prepared_reference['path']==str(folder/'coordinator/prepared.json'),
            'Exact original prepared question reference required')
    directory=folder/'question-root-quiescence'
    require(not directory.exists() and not directory.is_symlink(),
            'Original quiescence cannot repeat after an intent or uncertain effect')
    with runtime.question_operation_lock(folder), runtime.lock(folder,'root'):
        state,members=runtime.declared_runtime(folder,root_capability)
        question_state,control,history=runtime.question_coordinator_auth(folder,coordinator_capability)
        require(encoded(question_state)==encoded(state), 'Original question runtime changed')
        binding=validate_frontier(row,prepared,state,members,control,history,owner.value['parent_native_id'])
        require(time.time()<state['deadline'], 'Original first-quiescence deadline exhausted')
        origin=owner.root_origin(root_locator,row['actor_path'])
        require(origin['native_join']['child_native_id']==binding['root_native_uuid'],
                'Original bound actor native UUID changed')
        raw,_=source.capture.native_capture(root_locator,origin['child_entity'])
        require(raw.endswith(b'\n'), 'Complete original first-turn frontier required; partial append cannot be ignored')
        contract=coordinator.adapter.turn_contract(raw,binding,0,'first_seal')
        require(contract['expected_turns']==1, 'No second root turn before first quiescence')
        _,turns=coordinator.adapter.lifecycle.lifecycle(raw,
            coordinator.adapter.native_binding(binding),1,{},turn_contract=contract)
        completed=coordinator.adapter.core.instant(turns[0]['completed_at']).timestamp()
        require(state['started_at']<=completed<=time.time()<state['deadline'],
                'Genuine original first completion within clock required')
        runtime.question_verify_reference(prepared_reference)
        coordinator.source_fence(frozen_sources,[runtime.question_reference(Path(__file__).resolve())])
        post,m=runtime.declared_runtime(folder,root_capability)
        q,c,h=runtime.question_coordinator_auth(folder,coordinator_capability)
        require(encoded(post)==encoded(q)==encoded(state) and encoded(m)==encoded(members)
                and encoded(c)==encoded(control) and encoded(h)==encoded(history),
                'Original frontier changed before owned quiescence')
        require(source.capture.native_capture(root_locator,origin['child_entity'])[0]==raw,
                'Original first-turn source appended before quiescence')
        directory.mkdir()
        runtime.atomic_json(directory/'intent.json',{
            'schema_version':1,'binding':binding,'prepared_reference':prepared_reference,
            'original_started_at':state['started_at'],'original_deadline':state['deadline'],
            'root_container_id':state['jobs']['root']['container_id'],
            'first_native_sha256':coordinator.adapter.core.digest(raw),
            'first_completed_at':completed,'restart_permitted':False},exclusive=True)
        try:
            receipt=runtime.snapshot(folder,'root',restart=False,cleanup=False)
            after,after_members=runtime.declared_runtime(folder,root_capability)
            _,after_control,after_history=runtime.question_coordinator_auth(folder,coordinator_capability)
            immutable=lambda job:{k:v for k,v in job.items() if k!='status'}
            require(after['phase']==state['phase'] and after['jobs']['root']['status']=='stopped'
                    and encoded(immutable(after['jobs']['root']))==encoded(immutable(state['jobs']['root']))
                    and encoded(after['started_at'])==encoded(state['started_at'])
                    and encoded(after['deadline'])==encoded(state['deadline'])
                    and encoded(after_members)==encoded(members)
                    and encoded(after_control)==encoded(control) and encoded(after_history)==encoded(history)
                    and not runtime.inspect(folder,after,'root')['State']['Running'],
                    'Same owned root must be stopped without clock/control/membership changes')
            require(source.capture.native_capture(root_locator,origin['child_entity'])[0]==raw,
                    'Original first-turn source appended or changed during quiescence')
            runtime.question_verify_reference(prepared_reference)
            coordinator.source_fence(frozen_sources,[runtime.question_reference(Path(__file__).resolve())])
            owner.parent()
            runtime.atomic_json(directory/'receipt.json',{
                'schema_version':1,'snapshot':receipt,'first_native_sha256':coordinator.adapter.core.digest(raw),
                'original_first_completion_verified':True,'owned_root_stopped':True,
                'question_pause_committed':False,'reply_authorized':False,
                'native_full_audit_qualified':False,'comparison_admitted':False},exclusive=True)
            return runtime.question_reference(directory/'receipt.json')
        except BaseException as error:
            try:
                runtime.atomic_json(directory/'error.json',{'error_type':type(error).__name__,
                    'error_message':str(error),'restart_permitted':False,
                    'original_owned_cleanup_required':True},exclusive=True)
            except BaseException as preservation_error:
                raise error from preservation_error
            raise
