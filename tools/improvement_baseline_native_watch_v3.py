"""Prospective read-only baseline question observer on the original clock.

The coordinator supplies a separately frozen trusted authority callback. This
observer cannot authenticate that callback's native/semantic provenance, launch
or interrupt actors, close delivery, authorize cleanup/retries, or qualify cost.
Partial sources and awaiting semantic review never establish normal completion.
"""
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import re
import stat
import time

from collect import find_session
import improvement_baseline_registry_v1 as registry
import improvement_baseline_runtime_v4 as runtime
import improvement_baseline_membership_v1 as membership
import improvement_optional_inventory_v3 as strict
import improvement_q01_dialogue_core_v1 as core
import improvement_baseline_question_lifecycle_v3 as lifecycle
from improvement_software_artifacts_v3 import atomic_json

ROOT=Path(__file__).resolve().parents[1]
LIMIT=256*1024*1024
require=core.require
AUTHORITY_KEYS={'schema_version','root_path','parent_id','root_native_id','expected_turns',
                'phase','turn_ids','worker_cap','original_started_at','original_deadline','control_pins'}


def native_capture(path, previous_entity=None):
    """Preserve original pathname/device/inode, even across append samples."""
    path=Path(path)
    require(path.is_absolute() and path==path.resolve(strict=True), 'Canonical original native path required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size<=LIMIT, 'Bounded native regular file required')
        chunks=[];remaining=before.st_size
        while remaining:
            raw=os.read(fd,min(1024**2,remaining))
            require(bool(raw),'Original native source truncated during read')
            chunks.append(raw);remaining-=len(raw)
        raw=b''.join(chunks);after=os.fstat(fd);current=path.lstat()
        require((before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)==(current.st_dev,current.st_ino)
                and stat.S_ISREG(current.st_mode) and after.st_size>=before.st_size and current.st_size>=before.st_size,
                'Native pathname replaced/truncated during read')
        entity={'path':str(path),'device':before.st_dev,'inode':before.st_ino}
        if previous_entity is not None and entity!=previous_entity:
            error=ValueError('Original native pathname/device/inode changed')
            error.native_raw=raw;error.native_entity=entity
            raise error
        return raw,entity
    finally:os.close(fd)


def native_bytes(path):return native_capture(path)[0]


def authority_snapshot(value, root_path, parent_id, config, previous=None):
    require(type(value) is dict and set(value)==AUTHORITY_KEYS and type(value['schema_version']) is int
            and value['schema_version']==1,'Exact callback authority schema required')
    require(value['root_path']==root_path and value['parent_id']==parent_id
            and (value['root_native_id'] is None or type(value['root_native_id']) is str and bool(value['root_native_id'])),
            'Original authority path/parent/root identity required')
    require(type(value['worker_cap']) is int and value['worker_cap']==config['worker_cap']
            and value['worker_cap'] in (0,2) and type(value['expected_turns']) is int
            and value['expected_turns'] in (1,2) and value['phase'] in ('awaiting_semantic_review','first_seal','terminal'),
            'Typed original cap/approved turns/phase required')
    require(value['expected_turns']!=2 or value['phase'] in ('first_seal','terminal'),
            'Second turn cannot be approved while semantic review is pending')
    require(value['expected_turns']!=2 and value['phase']!='terminal' or value['root_native_id'] is not None,
            'Approved continuation/terminal authority requires known original root UUID')
    require(type(value['turn_ids']) is list and len(value['turn_ids'])<=value['expected_turns']
            and all(type(x) is str and bool(x) for x in value['turn_ids'])
            and len(set(value['turn_ids']))==len(value['turn_ids']), 'Distinct approved turn IDs required')
    require(value['phase']!='terminal' or len(value['turn_ids'])==value['expected_turns'],
            'Terminal authority requires every approved exact turn ID')
    require(registry.encoded(value['original_started_at'])==registry.encoded(config['started_at'])
            and registry.encoded(value['original_deadline'])==registry.encoded(config['deadline']), 'Authority original clock changed')
    require(type(value['control_pins']) is dict and (value['phase']=='awaiting_semantic_review' or bool(value['control_pins'])),
            'Current immutable authority control pins required')
    for key,reference in value['control_pins'].items():
        require(type(key) is str and bool(key),'Explicit control pin name required')
        runtime.question_verify_reference(reference)
    if previous is not None:
        require(previous['root_native_id'] is None or value['root_native_id']==previous['root_native_id'], 'Authority root UUID changed')
        require(value['expected_turns']>=previous['expected_turns'] and value['turn_ids'][:len(previous['turn_ids'])]==previous['turn_ids'],
                'Approved original turn prefix/count changed')
        order={'awaiting_semantic_review':0,'first_seal':1,'terminal':2}
        require(order[value['phase']]>=order[previous['phase']], 'Authority phase moved backward')
        require(all(key in value['control_pins'] and registry.encoded(value['control_pins'][key])==registry.encoded(reference)
                    for key,reference in previous['control_pins'].items()), 'Original immutable authority pins changed')
        require(previous['phase']!='terminal' or registry.encoded(previous)==registry.encoded(value), 'Terminal authority cannot reopen')
    return strict.decoded(registry.encoded(value))


def partial_source(raw, path, parent_id, previous=b'', previous_id=None, max_turns=1, approved_ids=None):
    require(type(raw) is bytes and type(previous) is bytes and raw.startswith(previous),'Native source is not append-consistent')
    require(type(path) is str and re.fullmatch('/root/[A-Za-z0-9_]+(?:/worker[12])?',path)
            and type(parent_id) is str and bool(parent_id),'Registered source path/parent required')
    newline=raw.rfind(b'\n');prefix=raw[:newline+1] if newline>=0 else b''
    base={'agent_path':path,'parent_native_id':parent_id,'raw_bytes':len(raw),'raw_sha256':core.digest(raw),
          'complete_native_bytes':len(prefix),'complete_native_sha256':core.digest(prefix),'raw_prefix_complete':prefix==raw,
          'native_session_id':None,'first_timestamp':None,'last_timestamp':None,'contexts':0,'completed_turns':0,
          'normal_completion_observed':False,'completion_at':None,'pending_reason':'incomplete_header',
          'failure_diagnostic':None,'usage':None,'cost':None,'native_qualified':False,'cleanup_authorized':False}
    if not prefix:return base,[],prefix
    events=core.parse(prefix);strict.finite(events)
    headers=[e['payload'] for e in events if e['type']=='session_meta']
    require(len(headers)==1 and events[0]['type']=='session_meta','Ambiguous original native header')
    header=headers[0];nested=header.get('source',{}).get('subagent',{}).get('thread_spawn',{})
    identity=header.get('id')
    require(type(identity) is str and bool(identity) and header.get('agent_path')==path
            and header.get('parent_thread_id')==parent_id and nested.get('parent_thread_id')==parent_id
            and nested.get('agent_path')==path,'Original source UUID/path/parent provenance changed')
    require(previous_id is None or identity==previous_id,'Original native UUID changed')
    contexts=[e['payload'] for e in events if e['type']=='turn_context']
    ends=[e for e in events if e['type']=='event_msg' and e['payload'].get('type')=='task_complete']
    require(len(contexts)<=max_turns and len(ends)<=max_turns,'Unapproved extra root/worker turn or completion')
    ids=[]
    for context in contexts:
        require(context.get('model')=='gpt-6.1-sol' and context.get('effort')=='medium','Actual native model/effort changed')
        settings=context.get('collaboration_mode',{}).get('settings')
        require(settings is None or settings.get('model')=='gpt-6.1-sol' and settings.get('reasoning_effort')=='medium','Conflicting actual model settings')
        identity_turn=lifecycle.turn_id(context);require(identity_turn is not None,'Actual context turn ID required');ids.append(identity_turn)
    require(len(set(ids))==len(ids),'Observed native context turn IDs must be distinct')
    authenticated=True
    if approved_ids is not None:
        require(ids[:len(approved_ids)]==approved_ids[:len(ids)],
                'Observed known native turn ID differs from authenticated prefix')
        authenticated=len(ids)<=len(approved_ids)
    failure=[e for e in ends if e['payload'].get('error') is not None or e['payload'].get('status') not in (None,'completed','success')
             or any(e['payload'].get(k) is not None and e['payload'].get(k) is not False for k in ('interrupted','cancelled'))]
    base.update(native_session_id=identity,first_timestamp=events[0]['timestamp'],last_timestamp=events[-1]['timestamp'],
                contexts=len(contexts),completed_turns=len(ends),completion_at=ends[-1]['timestamp'] if ends else None,
                pending_reason='partial_lifecycle',failure_diagnostic=[{'timestamp':e['timestamp'],'payload':e['payload']} for e in failure] or None)
    base['turn_ids_authenticated']=authenticated
    if not authenticated:base['pending_reason']='awaiting_turn_identity_authentication'
    return base,events,prefix


def lifecycle_sidecar(prefix, binding, expected, phase, cap, ids):
    return {'schema_version':1,'binding':binding,'job':'root' if binding['agent_path'].count('/')==2 else binding['agent_path'].rsplit('/',1)[-1],
            'expected_turns':expected,'turn_ids':ids,'native_sha256':core.digest(prefix),'worker_cap':cap,'phase':phase}


def sample(raw, path, parent_id, previous=b'', *, authority, child_sources=None, previous_id=None, registered_paths=None):
    """Incomplete valid bytes remain pending. Invalid complete claims must fail."""
    root=path.count('/')==2
    value,events,prefix=partial_source(raw,path,parent_id,previous,previous_id,
            authority['expected_turns'] if root else 1,authority['turn_ids'] if root else None)
    if root and events:
        observed_paths={path+'/'+op[2].get('task_name','') for op in membership.operations(events)}
        require(registered_paths is None or observed_paths<=set(registered_paths),'Unregistered native child allocation')
        require(len(observed_paths)<=authority['worker_cap'],'Observed original worker cap exceeded')
    require(not root or value['native_session_id'] is None or authority['root_native_id'] in (None,value['native_session_id']),
            'Observed root UUID disagrees with original callback identity')
    if root and value.get('turn_ids_authenticated') is False:return value
    if value['native_session_id'] is None or value['failure_diagnostic'] or not value['completed_turns']:
        return value
    require(not root or authority['root_native_id'] in (None,value['native_session_id']),'Observed root identity disagrees with callback')
    binding={'agent_path':path,'actor_native_id':value['native_session_id'],'parent_native_id':parent_id}
    children={} if child_sources is None else child_sources
    if not root:
        if not value['raw_prefix_complete']:return value
        ids=[lifecycle.turn_id(e['payload']) for e in events if e['type']=='turn_context']
        sidecar=lifecycle_sidecar(prefix,binding,1,'terminal',0,ids)
        lifecycle.lifecycle(prefix,binding,1,{},turn_contract=sidecar)
        value.update(normal_completion_observed=True,pending_reason=None);return value
    actual_ops=membership.operations(events)
    observed_paths={path+'/'+op[2].get('task_name','') for op in actual_ops}
    require(registered_paths is None or observed_paths<=set(registered_paths),'Unregistered native child allocation')
    require(len(observed_paths)<=authority['worker_cap'],'Observed original worker cap exceeded')
    completed=value['completed_turns']
    # Child source completeness is necessary before any complete-root decoder.
    # Missing/partial/unreceipted children remain pending, never a normal pass.
    for child in observed_paths:
        if child not in children:
            value['pending_reason']='pending_child_source';return value
        childvalue,_,_=partial_source(children[child],child,value['native_session_id'])
        if not childvalue['raw_prefix_complete'] or not childvalue['completed_turns'] or childvalue['failure_diagnostic']:
            value['pending_reason']='pending_child_lifecycle';return value
    delivered={e['payload'].get('author') for e in events if e['type']=='response_item'
               and e['payload'].get('type')=='agent_message' and e['payload'].get('author') in observed_paths}
    if delivered!=observed_paths:
        value['pending_reason']='pending_child_delivery';return value
    normal_count=completed
    selected=prefix
    if completed==1 and (authority['expected_turns']==2 or authority['phase']!='terminal'):
        # Root turn2 can be only partially received. Decode the first completed
        # prefix, retaining non-triggering child packets in the pause.
        starts=[i for i,e in enumerate(events) if e['type']=='event_msg' and e['payload'].get('type')=='task_started']
        if len(starts)>1:selected=b''.join(rawline for rawline in prefix.splitlines(keepends=True)[:starts[1]])
        selected_ops=membership.operations(core.parse(selected))
        selected_children={path+'/'+op[2]['task_name']:children[path+'/'+op[2]['task_name']] for op in selected_ops}
        selected_events=core.parse(selected)
        delivered_first={e['payload'].get('author') for e in selected_events if e['type']=='response_item'
                         and e['payload'].get('type')=='agent_message' and e['payload'].get('author') in selected_children}
        if delivered_first!=set(selected_children):
            value['pending_reason']='pending_first_prefix_child_delivery';return value
        sidecar=lifecycle_sidecar(selected,binding,1,'first_seal',authority['worker_cap'],authority['turn_ids'][:1])
        lifecycle.lifecycle(selected,binding,1,selected_children,turn_contract=sidecar)
        value.update(first_completion_validated=True,pending_reason='awaiting_semantic_review' if authority['expected_turns']==1 else 'awaiting_turn2')
        return value
    if completed<authority['expected_turns'] or not value['raw_prefix_complete']:
        value['pending_reason']='awaiting_approved_complete_turn';return value
    require(completed==authority['expected_turns'],'Complete native count differs from approved authority')
    if authority['phase']!='terminal':
        value['pending_reason']='awaiting_terminal_authority';return value
    sidecar=lifecycle_sidecar(prefix,binding,normal_count,'terminal',authority['worker_cap'],authority['turn_ids'])
    lifecycle.lifecycle(prefix,binding,normal_count,{p:children[p] for p in observed_paths},turn_contract=sidecar)
    value.update(normal_completion_observed=True,pending_reason=None);return value


def callback_reference(callback, reference):
    require(callable(callback),'Trusted validated_authority callback required; JSON approval is not callable authority')
    path=runtime.question_verify_reference(reference)
    source=inspect.getsourcefile(callback)
    require(source is not None and Path(source).resolve()==path,'Callback implementation differs from frozen source reference')
    return reference


def supervise(folder, root_path, parent_id, *, validated_authority, authority_callback_reference,
              source_finder=find_session, sample_interval=5):
    folder=Path(folder).resolve();require(folder.parent==ROOT/'runtime','Owned runtime namespace required')
    require(type(root_path) is str and re.fullmatch('/root/[A-Za-z0-9_]+',root_path)
            and type(parent_id) is str and bool(parent_id),'Original root path/parent required before spawn')
    require(type(sample_interval) in (int,float) and 0<sample_interval<=5,'Bounded sample interval required')
    callback_reference(validated_authority,authority_callback_reference)
    config=registry.read(folder/'registry')['configuration'];original=config['started_at'];deadline=config['deadline'];now=time.time()
    require(original<=now<deadline,'Original observer clock required')
    out=folder/'native-observer';out.mkdir();(out/'prefixes').mkdir()
    atomic_json(out/'ready.json',{'started_at':now,'original_started_at':original,'deadline':deadline,
        'root_path':root_path,'parent_id':parent_id,'root_native_id':None,'observer_restarts':0,'actor_control':False,
        'authority_callback_reference':authority_callback_reference,'native_qualified':False},exclusive=True)
    sources={};entities={};previous={};ids={};last_completed=now;root_identity=None;authority=None;number=0
    with (out/'samples.jsonl').open('x') as stream:
        while True:
            snapshots={};began=time.time()
            try:
                require(0<=began-last_completed<=30,'Observer started cadence exceeded30s')
                callback_reference(validated_authority,authority_callback_reference)
                with registry.locked(folder/'registry'):state=registry.read(folder/'registry')
                require(registry.encoded(state['configuration'])==registry.encoded(config),'Observer configuration/original clock changed')
                jobs=['root']+list(state['workers']);require(len(jobs)<=1+config['worker_cap'],'Cumulative registry worker cap changed')
                pending=[]
                for job in jobs:
                    path=root_path if job=='root' else root_path+'/'+job
                    if path not in sources:
                        try:sources[path]=Path(source_finder(path)).resolve(strict=True)
                        except ValueError as error:
                            if not str(error).endswith('found 0'):raise
                            pending.append(job);continue
                    raw,entity=native_capture(sources[path],entities.get(path));entities[path]=entity
                    snapshots[path]=raw
                    destination=out/'prefixes'/f'{number:06d}'/job;destination.parent.mkdir(exist_ok=True)
                    with destination.open('xb') as proof:proof.write(raw)
                    require(raw.startswith(previous.get(path,b'')),'Original native byte prefix mutated/truncated')
                value=validated_authority({'root_path':root_path,'parent_id':parent_id,'configuration':config,
                    'registry_state':state,'raw_sources':snapshots,'observed_root_native_id':root_identity})
                authority=authority_snapshot(value,root_path,parent_id,config,authority)
                members=[]
                if root_path in snapshots:
                    initial,_,_=partial_source(snapshots[root_path],root_path,parent_id,previous.get(root_path,b''),ids.get(root_path),authority['expected_turns'],authority['turn_ids'])
                    if initial['native_session_id'] is not None:
                        require(root_identity is None or root_identity==initial['native_session_id'],'Original root UUID replaced')
                        root_identity=initial['native_session_id']
                        require(authority['root_native_id'] in (None,root_identity),'Callback root UUID disagrees with observed source')
                for job in jobs:
                    path=root_path if job=='root' else root_path+'/'+job
                    if path not in snapshots:continue
                    if job!='root' and root_identity is None:
                        pending.append(job);previous[path]=snapshots[path];continue
                    parent=parent_id if job=='root' else root_identity
                    children={p:r for p,r in snapshots.items() if p!=root_path}
                    member=sample(snapshots[path],path,parent,previous.get(path,b''),authority=authority,
                                  child_sources=children,previous_id=ids.get(path),registered_paths={root_path+'/'+w for w in state['workers']})
                    previous[path]=snapshots[path]
                    if member['native_session_id'] is not None:ids[path]=member['native_session_id']
                    if member['pending_reason'] is not None:pending.append(job)
                    members.append(member)
                observed=[m['native_session_id'] for m in members if m['native_session_id'] is not None]
                require(len(set(observed))==len(observed),'Native UUID reused across registered members')
                finished=time.time();require(began<=finished and 0<=finished-last_completed<=30,'Observer completed cadence exceeded30s')
                require(number>0 or finished-now<=30,'Original first sample not completed within30s of readiness')
                require(all(m['first_timestamp'] is None or original<=core.instant(m['first_timestamp']).timestamp()
                            <=core.instant(m['last_timestamp']).timestamp()<=finished for m in members),'Native timestamps outside original clock')
                require(all(m['agent_path']!=root_path or m['first_timestamp'] is None
                            or core.instant(m['first_timestamp']).timestamp()>=now for m in members),
                        'Original root source predates exclusive observer readiness')
                failures=[m for m in members if m['failure_diagnostic']]
                row={'sample_number':number,'started_at':began,'completed_at':finished,'registry_head_sha256':state['head_sha256'],
                     'reserved_jobs':jobs,'members':members,'pending_native_jobs':sorted(set(pending)),
                     'authority':authority,'source_file_identities':entities,'root_native_id':root_identity,
                     'all_registered_normal_completions_observed':not pending and not failures and len(members)==len(jobs)
                         and authority['phase']=='terminal' and all(m['normal_completion_observed'] for m in members),
                     'failure_diagnostics':failures,'deadline_reached':finished>=deadline,
                     'usage':None,'cost':None,'authority_authenticated_by_observer':False,'native_qualified':False,'cleanup_authorized':False}
                stream.write(json.dumps(row,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno());last_completed=finished;number+=1
                if failures:
                    atomic_json(out/'terminal.json',{'reason':'native_error_diagnostic','last_sample':row,'native_qualified':False,'cleanup_authorized':False},exclusive=True)
                    return row
                closure=out/'stop.json'
                if closure.exists():
                    require(strict.decoded(closure.read_bytes())=={'reason':'coordinator_stop','root_path':root_path,'parent_id':parent_id},'Exact observer-only stop intent required')
                    atomic_json(out/'terminal.json',{'reason':'coordinator_stop','finished_at':finished,'last_sample_sha256':registry.sha(row),
                        'normal_completions_observed':row['all_registered_normal_completions_observed'],'native_qualified':False,'cleanup_authorized':False},exclusive=True)
                    return row
                if finished>=deadline:
                    atomic_json(out/'terminal.json',{'reason':'original_deadline','finished_at':finished,'last_sample_sha256':registry.sha(row),
                        'native_qualified':False,'cleanup_authorized':False},exclusive=True);return row
                time.sleep(min(sample_interval,max(.01,deadline-time.time())))
            except BaseException as error:
                if hasattr(error,'native_raw'):
                    snapshots[path]=error.native_raw
                    diagnostic_prefix=out/'prefixes'/f'{number:06d}'/'failed-source'
                    diagnostic_prefix.parent.mkdir(exist_ok=True)
                    with diagnostic_prefix.open('xb') as proof:proof.write(error.native_raw)
                diagnostic={'reason':'observer_failure','sample_number':number,'started_at':began,'observed_at':time.time(),
                    'error':{'type':type(error).__name__,'message':str(error)},'root_native_id':root_identity,
                    'preserved_prefixes':{p:{'bytes':len(r),'sha256':core.digest(r)} for p,r in snapshots.items()},
                    'source_file_identities':entities,'failed_source_entity':getattr(error,'native_entity',None),
                    'authority':authority,'usage':None,'cost':None,
                    'all_registered_normal_completions_observed':False,'native_qualified':False,'cleanup_authorized':False}
                atomic_json(out/'failure.json',diagnostic,exclusive=True);atomic_json(out/'terminal.json',diagnostic,exclusive=True)
                return diagnostic
