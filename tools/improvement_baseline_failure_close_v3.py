"""Prospective baseline failure preservation and per-job fenced Docker cleanup.

The caller must authenticate the frozen callback implementation and its original
coordinator provenance outside this module. Matching JSON is never admission.
Only genuine normal terminal actors pass this decoder. Interrupt/error branches
retain resources pending a separately qualified native receipt decoder.
No native API, retry, delivery, actor interruption or cost inference occurs here.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import time
import uuid

import improvement_baseline_registry_v1 as registry
import improvement_baseline_membership_v2 as membership
import improvement_baseline_runtime_v4 as runtime
import improvement_baseline_native_dispatch_v4 as dispatch
import improvement_baseline_native_inventory_v2 as inventory
import improvement_baseline_question_lifecycle_v3 as lifecycle
import improvement_baseline_native_watch_v2 as capture
from improvement_software_artifacts_v3 import atomic_json

ROOT=Path(__file__).resolve().parents[1]
require=registry.require
AUTHORITY_KEYS={'schema_version','mode','run_id','original_started_at','original_deadline',
                'root_lifecycle_contract','inventory_call_id','commitment','control_pins',
                'ambiguous_delivery','interrupt_receipt_references','member_native_ids'}


def first_error(value):
    require(type(value) is dict and set(value)=={'type','message'}
            and all(type(value[k]) is str and bool(value[k]) for k in value),
            'Exact original first error required')
    return copy.deepcopy(value)


def authority(value, config, callback, callback_reference):
    capture.callback_reference(callback,callback_reference)
    require(type(value) is dict and set(value)==AUTHORITY_KEYS
            and type(value['schema_version']) is int and value['schema_version']==1,
            'Exact trusted callback result required')
    require(value['mode'] in ('normal_terminal','pending_interrupt','pending_native_error')
            and value['run_id']==config['run_id']
            and registry.encoded(value['original_started_at'])==registry.encoded(config['started_at'])
            and registry.encoded(value['original_deadline'])==registry.encoded(config['deadline']),
            'Original mode/run/clock required')
    require(type(value['ambiguous_delivery']) is list
            and all(type(x) is str and bool(x) for x in value['ambiguous_delivery'])
            and type(value['interrupt_receipt_references']) is dict
            and type(value['control_pins']) is dict and bool(value['control_pins']),
            'Explicit ambiguity, interrupt receipts and immutable controls required')
    for refs in (value['control_pins'],value['interrupt_receipt_references']):
        for key,ref in refs.items():
            require(type(key) is str and bool(key),'Explicit control reference name required')
            runtime.question_verify_reference(ref)
    require(type(value['member_native_ids']) is dict and bool(value['member_native_ids'])
            and all(type(path) is str and bool(path) and type(native) is str and bool(native)
                    for path,native in value['member_native_ids'].items())
            and len(set(value['member_native_ids'].values()))==len(value['member_native_ids']),
            'Frozen exact all-member native UUID map required')
    if value['mode']=='normal_terminal':
        require(not value['ambiguous_delivery'] and not value['interrupt_receipt_references']
                and type(value['root_lifecycle_contract']) is dict
                and value['root_lifecycle_contract'].get('phase')=='terminal'
                and type(value['inventory_call_id']) is str and bool(value['inventory_call_id'])
                and type(value['commitment']) is dict,'Normal closure cannot hide ambiguity/interrupts')
    return registry.strict.decoded(registry.encoded(value))


def binding(member):
    origin=member['binding']
    require(member['agent_path']==origin['child_path']
            and member['native_session_id']==origin['child_native_id'], 'Original lifecycle allocation changed')
    return {'agent_path':member['agent_path'],'actor_native_id':member['native_session_id'],
            'parent_native_id':origin['parent_native_id']}


def terminal_gate(config,state,rows,parent,sources,registry_folder,auth):
    """Structural proof only. Caller callback trust is a separate prerequisite."""
    require(auth['mode']=='normal_terminal' and not auth['ambiguous_delivery'],
            'Native interrupt/error/ambiguity remains pending')
    root=rows['root']['intent']['agent_path'];children={p:r for p,r in sources.items() if p!=root}
    provision={'run_id':config['run_id'],'configuration_sha256':registry.sha(config),
               'jobs':{job:row['provision'] for job,row in rows.items()}}
    proof=membership.reconcile_membership(config,state,rows['root']['intent'],
        {job:row['intent'] for job,row in rows.items() if job!='root'},parent,sources[root],children,
        provision,registry_folder)
    require(proof['provided_allocation_joins_complete'],'Every cumulative allocation join required')
    members={m['agent_path']:m for m in proof['members']}
    require(set(members)==set(sources),'Every cumulative actual member source required')
    require(registry.encoded({path:member['native_session_id'] for path,member in members.items()})
            ==registry.encoded(auth['member_native_ids']),
            'Original authenticated all-member native UUIDs changed')
    sidecar=auth['root_lifecycle_contract'];ends={}
    require(type(sidecar.get('worker_cap')) is int and sidecar['worker_cap']==config['worker_cap'],
            'Original strict registered cap required')
    for path,member in members.items():
        b=binding(member)
        if path==root:contract=sidecar;expected=sidecar.get('expected_turns');child=children
        else:
            events=inventory.core.parse(sources[path]);ids=[lifecycle.turn_id(e['payload']) for e in events if e['type']=='turn_context']
            contract={'schema_version':1,'binding':b,'job':member['job'],'expected_turns':1,
                      'turn_ids':ids,'native_sha256':inventory.core.digest(sources[path]),'worker_cap':0,'phase':'terminal'}
            expected=1;child={}
        _,turns=lifecycle.lifecycle(sources[path],b,expected,child,turn_contract=contract)
        ends[path]=turns[-1]['completed_at']
    current=inventory.completed_inventory(parent,proof['coordinator_native_id'],ends,
        auth['inventory_call_id'],auth['commitment'],sources[root],children,root_lifecycle_contract=sidecar)
    return {'membership':proof,'current_inventory':current,'completions':ends,
            'normal_terminal_failure_gate_pass':True,'software_pass':None,'usage':None,'cost':None,
            'cleanup_authorized':False,'native_qualified':False,'comparison_admitted':False}


def registry_snapshot_fingerprint(snapshot):
    json_part={key:value for key,value in snapshot.items() if type(value) is not bytes}
    raw_part={key:{'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()}
              for key,value in snapshot.items() if type(value) is bytes}
    return registry.encoded({'json':json_part,'raw':raw_part})


def question_closure_fence(folder, config, auth, dispatch_config, member_sources, coordinator_source):
    if config['case_id'] not in ('B03','B04'):
        return
    _,control,_=runtime._question_snapshot(folder,closing=True)
    reference=auth['control_pins'].get('no_more_delivery')
    require(type(reference) is dict and reference.get('path')==str(Path(folder)/'question/no-more-delivery.json'),
            'Original question no-more-delivery reference required')
    value=registry.strict.decoded(runtime.question_reference_bytes(reference))
    require(type(value.get('schema_version')) is int and value['schema_version']==1
            and value.get('no_more_delivery') is True
            and registry.encoded(value.get('binding'))==registry.encoded(control['binding'])
            and registry.encoded(value.get('original_deadline'))==registry.encoded(config['deadline']),
            'Question delivery fence identity changed')
    commitment=registry.strict.decoded(runtime.question_reference_bytes(value['commitment']))
    require(commitment.get('no_more_delivery') is True
            and commitment.get('coordinator_identity')==dispatch_config['coordinator_id']
            and registry.encoded(commitment.get('binding'))==registry.encoded(control['binding'])
            and control['binding']['root_native_uuid']==auth['member_native_ids'][dispatch_config['root_path']],
            'Original question coordinator/root commitment changed')
    entities=commitment.get('native_source_entities')
    require(type(entities) is dict,'Question closure native sources required')
    for locator in [coordinator_source,*member_sources.values()]:
        name=str(Path(locator))
        require(name in entities and registry.encoded(entities[name])==registry.encoded(runtime.question_file_entity(name)),
                'Question closure native source pin changed')


def remove_exact(folder, state, job, identity):
    require(type(identity) is str and re.fullmatch('[0-9a-f]{64}',identity)
            and state['jobs'][job]['container_id']==identity,'Exact original removal identity required')
    directory=Path(folder)/'engine-removals'/uuid.uuid4().hex;directory.mkdir(parents=True)
    intent={'schema_version':1,'job':job,'container_id':identity,'args':['rm',identity],
            'run_id':state['run_id'],'configuration_sha256':state['configuration_sha256'],
            'started_at':time.time(),'cleanup':True}
    atomic_json(directory/'intent.json',intent,exclusive=True)
    try:
        result=runtime.bounded_exec(directory,job,0,['rm',identity],30)
    except BaseException as error:
        atomic_json(directory/'failure.json',{'type':type(error).__name__,'message':str(error),
                    'finished_at':time.time()},exclusive=True)
        raise
    atomic_json(directory/'receipt.json',{'intent':intent,'result':result,'finished_at':time.time()},exclusive=True)
    require(result['output_complete'] is True and not result.get('transport_error'),
            'Removal transport uncertain; original raw output retained')
    for value in result['raw_output'].values():
        raw=Path(value['path']).read_bytes()
        require(len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256'],
                'Original removal raw output changed')
    require(type(result['exit_code']) is int and result['exit_code']==0,
            'Exact removal failed; original raw output retained')
    return runtime.question_reference(directory/'receipt.json')


def fenced_cleanup(folder, fence):
    """Necessary backend4 cleanup loop, with fences and stop-on-first-error.

    This private helper assumes close() established external terminal authority.
    Each composite snapshot is one existing backend preservation primitive.
    No mutable monkeypatch/state job filtering and no broad removal are used.
    """
    require(callable(fence),'Live source/authority fence required')
    folder=Path(folder);fence()
    with runtime.lock(folder):
        state=runtime.load(folder);state['phase']='closing';runtime.save(folder,state)
    errors=[];blocked=[];jobs=list(state['jobs'])
    immutable_jobs={job:{key:value for key,value in row.items() if key not in ('status','commands')}
                    for job,row in state['jobs'].items()}
    require(bool(immutable_jobs) and all(type(row.get('container_id')) is str
            and re.fullmatch('[0-9a-f]{64}',row['container_id']) for row in immutable_jobs.values()),
            'Original exact container IDs required; unknown identity needs separate authenticated recovery')
    original_fence=fence
    def checked_fence():
        original_fence()
        current=runtime.load(folder)
        observed={job:{key:value for key,value in row.items() if key not in ('status','commands')}
                  for job,row in current['jobs'].items()}
        require(registry.encoded(observed)==registry.encoded(immutable_jobs),
                'Original per-job container IDs/ownership changed during cleanup')
    fence=checked_fence
    for index,job in enumerate(jobs):
        try:
            fence()
            with runtime.lock(folder,job):
                current=runtime.load(folder);row=current['jobs'][job]
                if row['container_id'] is None:
                    fence();runtime.recover_created_identity(folder,current,job);fence()
                    current=runtime.load(folder);row=current['jobs'][job]
                if row['status']=='removed':
                    require(row['container_id'] is not None,'Previously removed identity unknown')
                    fence();absent=runtime.engine_inspect(folder,current,job,row['container_id'],cleanup=True,check=False);fence()
                    require(absent.returncode!=0 and 'No such object:' in absent.stderr,'Previously removed resource reappeared')
                    continue
                if row['container_id'] is None:
                    fence();found=runtime.engine_inspect(folder,current,job,row['container'],cleanup=True,check=False);fence()
                    if found.returncode:
                        require('No such object:' in found.stderr,'Creation absence unknown')
                        raise ValueError('Dispatched creation identity unresolved; name absence cannot prove removal')
                    values=runtime.strict.decoded(found.stdout)
                    require(type(values) is list and len(values)==1 and type(values[0]) is dict,
                            'One reconciled engine object required')
                    identity=values[0].get('Id')
                    require(type(identity) is str and re.fullmatch('[0-9a-f]{64}',identity),'Exact engine ID required')
                    fence()
                    with runtime.lock(folder):
                        current=runtime.load(folder);current['jobs'][job]['container_id']=identity;runtime.save(folder,current)
                    row=current['jobs'][job]
                identity=row['container_id']
                require(type(identity) is str and re.fullmatch('[0-9a-f]{64}',identity),'Exact engine ID required')
                # Authenticate owned labels/mounts before snapshot can stop anything.
                fence();runtime.inspect(folder,current,job,cleanup=True);fence()
                runtime.snapshot(folder,job,cleanup=True);fence()
                current=runtime.load(folder)
                require(current['jobs'][job]['container_id']==identity,'Cleanup identity changed')
                fence();runtime.inspect(folder,current,job,cleanup=True);fence()
                runtime.archive_tmp(folder,identity,job);fence()
                current=runtime.load(folder)
                require(current['jobs'][job]['container_id']==identity,'Cleanup identity changed before removal')
                fence();remove_exact(folder,current,job,identity);fence()
                absent=runtime.engine_inspect(folder,current,job,identity,cleanup=True,check=False);fence()
                require(absent.returncode!=0 and 'No such object:' in absent.stderr,'Exact removal unconfirmed')
                runtime.status(folder,job,'removed');fence()
                with runtime.lock(folder):runtime.event(folder,{'op':'removed','job':job,'container_id':identity})
        except BaseException as error:
            errors.append({'job':job,'type':type(error).__name__,'message':str(error)})
            blocked=jobs[index+1:];break
    with runtime.lock(folder):
        current=runtime.load(folder);current['cleanup_errors']=errors
        current['phase']='preservation_failed' if errors else 'closed_docker_only';runtime.save(folder,current)
    return {'state':current,'errors':errors,'blocked_jobs':blocked,
            'owned_cleanup_verified':not errors and bool(jobs) and all(r['status']=='removed' for r in current['jobs'].values())}


def close(folder, original_first_error, coordinator_source, member_sources, *,
          validated_authority, authority_callback_reference):
    """Capture original prefixes first. Pending branches retain every resource."""
    folder=Path(folder).resolve()
    require(folder.parent==ROOT/'runtime','Original owned runtime namespace required')
    error=first_error(original_first_error)
    capture.callback_reference(validated_authority,authority_callback_reference)
    output=folder/'failure-close-v3';output.mkdir();(output/'prefixes').mkdir()
    record={'status':'awaiting_terminal_authority','first_error':error,'software_pass':None,
            'usage':None,'cost':None,'owned_cleanup_verified':False,'cleanup_authorized':False,
            'native_qualified':False,'comparison_admitted':False,'retransmission_attempted':False,
            'authority_origin_authenticated_by_this_module':False,'started_at':time.time()}
    atomic_json(output/'intent.json',record,exclusive=True)
    try:
        snapshot=membership.reservation_prefix(folder/'registry');state=snapshot['state'];config=state['configuration']
        registry.validate_contract(config);runtime_state=runtime.load(folder)
        dispatch.runtime_identity(folder,config)
        expected_jobs={'root',*state['workers']}
        require(set(runtime_state['jobs'])==expected_jobs,'Runtime jobs differ from cumulative reserved members')
        if runtime_state['first_error'] is not None:
            require(registry.encoded(error)==registry.encoded(runtime_state['first_error']),'Original runtime first error cannot change')
        record.update(original_started_at=config['started_at'],original_deadline=config['deadline'])
        paths=[folder/'native-dispatch/configuration.json',folder/'configuration.json']
        directory=folder/'native-dispatch/intents';names=sorted(p.name for p in directory.iterdir())
        require(set(names)<=set(job+'.json' for job in ['root',*state['workers']]) and 'root.json' in names,
                'Unknown original dispatch intent')
        paths += [directory/name for name in names]
        originals={str(p):capture.native_capture(p) for p in paths}
        rows={p.stem:registry.strict.decoded(originals[str(p)][0]) for p in paths if p.parent==directory}
        dc=registry.strict.decoded(originals[str(paths[0])][0]);root=rows['root']['intent']['agent_path']
        require(dc['root_path']==root and dc['configuration_sha256']==registry.sha(config)
                and dc['runtime_configuration_sha256']==dispatch.runtime_identity(folder,config), 'Original dispatch binding changed')
        require(type(member_sources) is dict and root in member_sources,'Explicit original member locators required')
        captures={};capture_errors=[];parent=None;parent_entity=None
        record['captured_prefixes']={}
        for index,(path,locator) in enumerate([('coordinator',coordinator_source),*sorted(member_sources.items())]):
            name='coordinator.jsonl' if index==0 else f'member-{index-1}.jsonl'
            try:
                raw,entity=capture.native_capture(locator)
                with (output/'prefixes'/name).open('xb') as f:f.write(raw)
                record['captured_prefixes'][path]={'file':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
                if index==0:parent,parent_entity=raw,entity
                else:captures[path]=(raw,entity)
            except BaseException as caught:
                available=getattr(caught,'native_raw',None)
                if type(available) is bytes:
                    with (output/'prefixes'/name).open('xb') as f:f.write(available)
                    record['captured_prefixes'][path]={'file':name,'bytes':len(available),'sha256':hashlib.sha256(available).hexdigest(),'uncertain':True}
                capture_errors.append({'member':path,'type':type(caught).__name__,'message':str(caught)})
        record['native_capture_errors']=capture_errors
        atomic_json(output/'captured-prefixes.json',{'prefixes':record['captured_prefixes'],'errors':capture_errors},exclusive=True)
        require(not capture_errors,'Original source capture uncertain; available prefixes retained, cleanup forbidden')
        sources={path:value[0] for path,value in captures.items()}
        record['native_sources']={p:{**captures[p][1],'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for p,raw in sources.items()}
        observation={'configuration':copy.deepcopy(config),'registry_state':copy.deepcopy(state),'dispatch_rows':copy.deepcopy(rows),
                     'coordinator_raw':parent,'member_raw_by_path':sources,'first_error':copy.deepcopy(error)}
        auth=authority(validated_authority(observation),config,validated_authority,authority_callback_reference)
        atomic_json(output/'authority.json',auth,exclusive=True)
        if auth['mode']!='normal_terminal' or auth['ambiguous_delivery']:
            record.update(status='pending_native_terminal_authority',pending_reason='Genuine interrupt/error receipt decoder remains unqualified; no cleanup or retransmission')
        else:
            question_closure_fence(folder,config,auth,dc,member_sources,coordinator_source)
            proof=terminal_gate(config,state,rows,parent,sources,folder/'registry',auth)
            require(proof['membership']['coordinator_native_id']==dc['coordinator_id'],'Original coordinator UUID changed')
            atomic_json(output/'terminal-proof.json',proof,exclusive=True)
            def fence():
                capture.callback_reference(validated_authority,authority_callback_reference)
                require(registry_snapshot_fingerprint(membership.reservation_prefix(folder/'registry'))==registry_snapshot_fingerprint(snapshot),'Original registry source changed')
                dispatch.runtime_identity(folder,config)
                require(set(runtime.load(folder)['jobs'])==expected_jobs,'Runtime jobs changed before cleanup')
                question_closure_fence(folder,config,auth,dc,member_sources,coordinator_source)
                require(sorted(p.name for p in directory.iterdir())==names,'Original cumulative dispatch changed')
                for name,(raw,entity) in originals.items():
                    require(capture.native_capture(name,entity)[0]==raw,'Original dispatch/config source changed')
                require(capture.native_capture(coordinator_source,parent_entity)[0]==parent,'Original coordinator source changed after fence')
                for path,(raw,entity) in captures.items():
                    require(capture.native_capture(member_sources[path],entity)[0]==raw,'Original member source changed after fence')
                current=authority(validated_authority(observation),config,validated_authority,authority_callback_reference)
                require(registry.encoded(current)==registry.encoded(auth),'Original terminal/no-more-delivery authority changed')
            fence()
            with runtime.lock(folder):
                current=runtime.load(folder)
                require(current['first_error'] is None or registry.encoded(current['first_error'])==registry.encoded(error),'Original first error changed')
                if current['first_error'] is None:current['first_error']=error
                current['phase']='failed_preservation_required';runtime.save(folder,current)
            cleaned=fenced_cleanup(folder,fence);fence()
            record.update(owned_cleanup_verified=cleaned['owned_cleanup_verified'],cleanup_errors=cleaned['errors'],blocked_jobs=cleaned['blocked_jobs'],
                          status='preserved_completed_failure' if cleaned['owned_cleanup_verified'] else 'closure_incomplete')
    except BaseException as caught:
        record.update(status='closure_incomplete',closure_error={'type':type(caught).__name__,'message':str(caught)})
    record['finished_at']=time.time()
    atomic_json(output/'outcome.json',record,exclusive=True)
    return record
