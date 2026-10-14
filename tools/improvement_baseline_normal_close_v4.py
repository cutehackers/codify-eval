"""Prospective normal close: full native audit, stopped grading, owned cleanup.

No model comparison is admitted here. The original coordinator must authenticate
the frozen authority callback, observer, current API inventory and delivery fence.
"""
import copy
from pathlib import Path
import time
import math

import improvement_baseline_failure_close_v4 as preservation
import improvement_baseline_native_audit_v4 as audit
import improvement_baseline_grading_v1 as grading

runtime=grading.runtime
coordinator=grading.coordinator
require=runtime.require
encoded=runtime.encoded
ROOT=grading.ROOT



def parent_extension_fence(original,current,previous):
    """Only ordinary ROOT control/log appends may follow the frozen NMD prefix.

    Same source inode is checked by native_capture. New native collaboration
    calls (including newer inventory) invalidate the original authority. An
    incomplete tail remains unresolved and cannot authorize SDK effects.
    """
    require(type(original) is bytes and type(current) is bytes and type(previous) is bytes
            and current.startswith(original) and current.startswith(previous),
            'Original coordinator prefix rewritten or truncated')
    require(original.endswith(b'\n') and current.endswith(b'\n'),
            'Current coordinator partial tail requires completed source before closure')
    if current==original:return current
    core=preservation.membership.original.core
    events=core.parse(current);preservation.inventory.finite(events)
    boundary=len(core.parse(original))
    for event in events[boundary:]:
        payload=event['payload']
        require(event.get('type') not in ('session_meta','turn_context'),
                'Coordinator session or turn changed after original terminal commitment')
        require(payload.get('type') not in ('task_started','task_complete','turn_aborted'),
                'Coordinator lifecycle changed after original terminal commitment')
        if payload.get('type') in ('function_call','custom_tool_call'):
            require(event.get('type')=='response_item','Original coordinator tool event type required')
            allowed=any(core.route(payload,'functions',name) for name in ('exec','wait'))
            require(allowed,'Native allocation/delivery/inventory or unknown tool after original terminal commitment')
    return current


def verified_grading_result(folder,row,selection,graded):
    reference=graded['receipt_reference']
    require(reference['path']==str(Path(folder)/'grading/verifier/receipt.json'), 'Exact original grader receipt required')
    receipt=runtime.strict.decoded(runtime.question_reference_bytes(reference))
    contract,private=grading.selected_contract(row['case_id'],selection)
    actual=grading.classifier.classify(receipt,contract['expected_nonloading_tests'],commands=contract['inner_argv'])
    require(encoded(actual)==encoded(graded['classification']), 'Persisted grader classification differs from actual receipt')
    require(graded['grading_kind']==('private' if private else 'public_only_unresolved_decision'), 'Original grading kind changed')
    software=actual['software_pass'] if private else None
    require(encoded(graded['software_pass'])==encoded(software), 'Original software result changed')
    clean=receipt.get('removed') is True and receipt.get('cleanup_errors')==[]
    errors=copy.deepcopy(receipt.get('cleanup_errors',[]))
    require(type(errors) is list,'Explicit grader cleanup errors required')
    if not clean and not errors:errors=[{'type':'GraderCleanupUnknown','message':'Original grader removal is not verified'}]
    return {'classification':actual,'software_pass':software,
            'grader_owned_cleanup_verified':clean,'grader_cleanup_errors':errors}


def close(row,prepared_reference,audit_inputs_reference,coordinator_source,member_sources,selection,*,
          root_capability,validated_authority,authority_contract,coordinator_verifier,verifier_contract):
    grading.inputs.row_valid(row)
    row=runtime.strict.decoded(encoded(row));folder=ROOT/'runtime'/row['run_id']
    prepared=runtime.strict.decoded(runtime.question_reference_bytes(prepared_reference))
    require(encoded(prepared['row'])==encoded(row),'Original prepared comparison row required')
    require(prepared_reference['path']==str(folder/'coordinator/prepared.json'),'Original prepared path required')
    runtime.question_verify_reference(prepared['configuration_reference'])
    state,members=runtime.declared_runtime(folder,root_capability)
    original_jobs=preservation.immutable_job_fields(state)
    require(state.get('first_error') is None,'Unsuccessful runtime needs failure closure')
    require(encoded(state['started_at'])==encoded(prepared['original_started_at'])
            and encoded(state['deadline'])==encoded(prepared['original_deadline']), 'Original prepared clock changed')
    require(type(prepared['preparation_started_at']) in (int,float)
            and math.isfinite(prepared['preparation_started_at'])
            and prepared['preparation_started_at']<=state['started_at'], 'Actual whole preparation start required')
    authority_contract=copy.deepcopy(authority_contract)
    require(encoded(coordinator.callback_contract(validated_authority))==encoded(authority_contract),
            'Frozen actual authority implementation required')
    coordinator.authenticate(coordinator_verifier,verifier_contract,'original_normal_closer_authority',
        {'prepared_reference':prepared_reference,'authority_contract':authority_contract,
         'audit_inputs_reference':audit_inputs_reference,'member_sources':member_sources})
    require(encoded(runtime.load(folder))==encoded(state),'Runtime changed during normal-close authentication')
    output=folder/'normal-close';output.mkdir();(output/'prefixes').mkdir()
    record={'row':row,'status':'preserving','software_pass':None,'usage':None,
            'owned_cleanup_verified':False,'product_owned_cleanup_verified':False,'grader_owned_cleanup_verified':False,'first_error':None,'cleanup_errors':[],'grader_cleanup_errors':[],
            'preparation_started_at':prepared['preparation_started_at'],
            'model_pilot_admitted':False,'superiority_proven':False}
    runtime.atomic_json(output/'intent.json',record,exclusive=True)
    fence=None
    try:
        config=members['configuration'];snapshot=preservation.membership.reservation_prefix(folder/'registry')
        require(encoded(snapshot['state'])==encoded(members),'Original registry frontier changed')
        config_paths=[folder/'configuration.json',folder/'native-dispatch/configuration.json']
        intent_directory=folder/'native-dispatch/intents'
        intent_names=sorted(p.name for p in intent_directory.iterdir())
        require(set(intent_names)=={job+'.json' for job in state['jobs']},'Exact cumulative dispatch intents required')
        paths=config_paths+[intent_directory/name for name in intent_names]
        controls={str(p):preservation.capture.native_capture(p) for p in paths}
        dispatch_config=runtime.strict.decoded(controls[str(config_paths[1])][0])
        rows={Path(path).stem:runtime.strict.decoded(raw) for path,(raw,_) in controls.items()
              if Path(path).parent==intent_directory}
        root=row['actor_path'];require(root in member_sources,'Original root source required')
        parent,parent_pin=preservation.capture.native_capture(coordinator_source)
        latest_parent=parent
        with (output/'prefixes/coordinator.jsonl').open('xb') as stream:stream.write(parent)
        captures={};sources={}
        for i,(path,locator) in enumerate(member_sources.items()):
            destination=output/'prefixes'/f'member-{i}.jsonl'
            try:
                raw,pin=preservation.capture.native_capture(locator)
                with destination.open('xb') as stream:stream.write(raw)
                captures[path]=(raw,pin);sources[path]=raw
            except Exception as error:
                available=getattr(error,'native_raw',None)
                if type(available) is bytes:
                    with destination.open('xb') as stream:stream.write(available)
                raise
        observation={'configuration':copy.deepcopy(config),'registry_state':copy.deepcopy(members),
                     'dispatch_rows':copy.deepcopy(rows),'coordinator_raw':parent,
                     'member_raw_by_path':sources,'first_error':None}
        def read_authority():
            nonlocal latest_parent
            current,_=preservation.capture.native_capture(coordinator_source,parent_pin)
            latest_parent=parent_extension_fence(parent,current,latest_parent)
            require(encoded(coordinator.callback_contract(validated_authority))==encoded(authority_contract),
                    'Authority code changed')
            current_observation=copy.deepcopy(observation)
            current_observation['current_coordinator_raw']=latest_parent
            value=validated_authority(current_observation)
            require(encoded(coordinator.callback_contract(validated_authority))==encoded(authority_contract),
                    'Authority changed during authentication')
            return preservation.authority(value,config,validated_authority,authority_contract['source_reference'])
        auth=read_authority()
        require(auth['mode']=='normal_terminal' and not auth['ambiguous_delivery'],'Only genuine normal terminal authority')
        runtime.atomic_json(output/'authority.json',auth,exclusive=True)
        audit_inputs=runtime.strict.decoded(runtime.question_reference_bytes(audit_inputs_reference))
        require(set(audit_inputs)=={'contracts','turn_contracts','inventory_call_id','commitment'},
                'Exact original native audit inputs required')
        require(encoded(audit_inputs['turn_contracts'][root])==encoded(auth['root_lifecycle_contract'])
                and audit_inputs['inventory_call_id']==auth['inventory_call_id']
                and encoded(audit_inputs['commitment'])==encoded(auth['commitment']),
                'Audit input differs from original terminal authority')
        children={path:raw for path,raw in sources.items() if path!=root}
        provision={'run_id':config['run_id'],'configuration_sha256':preservation.registry.sha(config),
                   'jobs':{job:value['provision'] for job,value in rows.items()}}
        ledgers={path:audit.original_ledger(folder,contract['job']) for path,contract in audit_inputs['contracts'].items()}
        proof=audit.audit(config,members,rows['root']['intent'],
            {job:value['intent'] for job,value in rows.items() if job!='root'},parent,sources[root],children,
            provision,folder/'registry',audit_inputs['contracts'],ledgers,member_sources,
            auth['inventory_call_id'],auth['commitment'],turn_contracts=audit_inputs['turn_contracts'])
        require(proof['membership']['coordinator_native_id']==dispatch_config['coordinator_id'],
                'Actual original coordinator UUID changed')
        require(encoded({m['agent_path']:m['native_session_id'] for m in proof['membership']['members']})
                ==encoded(auth['member_native_ids']),'Original full cost-member native UUID map changed')
        runtime.atomic_json(output/'native-audit.json',proof,exclusive=True)
        def current_fence():
            nonlocal latest_parent
            require(encoded(read_authority())==encoded(auth),'Original terminal authority changed')
            runtime.declared_runtime(folder,root_capability)
            require(encoded(coordinator.callback_contract(validated_authority))==encoded(authority_contract),'Authority code changed')
            require(encoded(preservation.immutable_job_fields(runtime.load(folder)))==encoded(original_jobs),
                    'Original container IDs/ownership changed')
            require(preservation.registry_snapshot_fingerprint(preservation.membership.reservation_prefix(folder/'registry'))
                    ==preservation.registry_snapshot_fingerprint(snapshot),'Original registry frontier changed')
            runtime.question_verify_reference(prepared_reference)
            runtime.question_verify_reference(audit_inputs_reference)
            require(sorted(p.name for p in intent_directory.iterdir())==intent_names,'Original dispatch membership changed')
            for path,(raw,pin) in controls.items():require(preservation.capture.native_capture(path,pin)[0]==raw,'Original config/dispatch changed')
            current,_=preservation.capture.native_capture(coordinator_source,parent_pin)
            latest_parent=parent_extension_fence(parent,current,latest_parent)
            for path,(raw,pin) in captures.items():require(preservation.capture.native_capture(member_sources[path],pin)[0]==raw,'Original member prefix changed')
            preservation.question_closure_fence(folder,config,auth,dispatch_config,member_sources,coordinator_source)
        fence=current_fence;fence()
        record['usage']=proof['usage'];record['all_member_usage_observed']=proof['all_member_usage_observed']
        with runtime.lock(folder,'root'):
            fence();stopped=runtime.snapshot(folder,'root');fence()
        events=sorted((folder/'events').glob('*.json'))
        matching=[p for p in events if runtime.strict.decoded(p.read_bytes()).get('export')==stopped['export']]
        require(len(matching)==1,'Exact owned stopped snapshot event required')
        graded=grading.grade(row,runtime.question_reference(matching[0]),selection,
            coordinator_verifier=coordinator_verifier,verifier_contract=verifier_contract)
        fence();record['grading']=graded
        grading_result=verified_grading_result(folder,row,selection,graded)
        record['grader_owned_cleanup_verified']=grading_result['grader_owned_cleanup_verified']
        record['grader_cleanup_errors']=grading_result['grader_cleanup_errors']
        require(grading_result['grader_owned_cleanup_verified'], 'Grader resource cleanup is incomplete; receipt retained')
        require(grading_result['classification']['classification']!='evaluation_error', 'Grading remains unqualified evaluation error')
        record['software_pass']=grading_result['software_pass']
    except Exception as error:
        record['first_error']={'type':type(error).__name__,'message':str(error)}
    if fence is not None:
        try:
            fence();cleaned=preservation.fenced_cleanup(folder,fence,original_jobs=original_jobs);fence()
            record['product_owned_cleanup_verified']=cleaned['owned_cleanup_verified']
            record['owned_cleanup_verified']=cleaned['owned_cleanup_verified'] and record['grader_owned_cleanup_verified']
            record['cleanup_errors']=record['grader_cleanup_errors']+cleaned['errors']
            record['blocked_jobs']=cleaned['blocked_jobs']
        except Exception as error:record['cleanup_errors'].append({'type':type(error).__name__,'message':str(error)})
    record['status']='closed' if record['owned_cleanup_verified'] and record['first_error'] is None else 'closure_incomplete'
    record['finished_at']=time.time();record['whole_observed_seconds']=record['finished_at']-record['preparation_started_at']
    runtime.atomic_json(output/'outcome.json',record,exclusive=True)
    return record
