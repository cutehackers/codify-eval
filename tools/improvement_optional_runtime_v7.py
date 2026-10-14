"""Trusted optional Docker lifecycle and contribution precursor, not native authority.

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

import improvement_optional_source_v2 as source
import improvement_optional_registry_v4 as registry
import improvement_optional_artifacts_v2 as artifacts
import improvement_optional_checkout_artifacts_v2 as checkout
from improvement_software_artifacts_v3 import atomic_json, encoded
from improvement_q04_runtime_v3 import IMAGE, docker
from improvement_q04_broker_v1 import archive_tmp

require=registry.require


def hashed(text):return hashlib.sha256(text.encode()).hexdigest()


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


def provision(folder,job,task):
    with lock(folder,job):
        return _provision(folder,job,task)


def _provision(folder,job,task):
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


def create(folder,starting,case,condition,task,editable_paths):
    started=time.time();folder=Path(folder).resolve();starting=Path(starting).resolve()
    require(not folder.exists() and folder!=starting and starting not in folder.parents,'Exclusive external runtime required')
    require(shutil.disk_usage(folder.parent).free>=3*1024**3,'Insufficient allocation disk')
    config={'case':case,'condition':condition,'image':IMAGE,'task':task,'editable_paths':editable_paths,
            'started_at':started,'deadline':started+1200,'model':'gpt-6.1-sol','effort':'medium'}
    folder.mkdir();(folder/'events').mkdir();(folder/'root').mkdir()
    atomic_json(folder/'configuration.json',config,exclusive=True)
    state={'run_id':uuid.uuid4().hex,'configuration_sha256':hashlib.sha256(encoded(config)).hexdigest(),
           'started_at':started,'deadline':started+1200,'phase':'preparing','editable_paths':editable_paths,
           'jobs':{},'events':0,'first_error':None,'native_qualified':False,'comparison_eligible':False}
    save(folder,state)
    try:
        initial=source.inventory(starting,state['deadline']);source.export(starting,initial,folder/'root/repo',state['deadline'])
        cap=provision(folder,'root',task)
        for text in ('git init -q','git -c user.name=Fixture -c user.email=fixture@localhost add .',
                     'git -c user.name=Fixture -c user.email=fixture@localhost commit -q -m baseline',
                     '/sdks/flutter/bin/flutter pub get --offline'):
            result=command(folder,'root',cap,text);require(result['exit_code']==0,'Fixed preparation failed: '+text)
        with lock(folder,'root'):
            receipt=snapshot(folder,'root')
            registry.create(folder/'registry',state['run_id'],case,condition,started,
                            receipt['inventory']['source_entities'],editable_paths)
            with lock(folder):
                state=load(folder);state['jobs']['root']['baseline']=receipt['inventory'];state['phase']='running';save(folder,state)
            start(folder,'root')
        return {'root_capability':cap,'folder':str(folder),'run_id':state['run_id']}
    except BaseException as error:
        failure(folder,error);raise


def worker(folder,root_cap,goal,scope,mode='write'):
    folder=Path(folder).resolve()
    with lock(folder,'root'):
        state=load(folder);require(secrets.compare_digest(hashed(root_cap),state['jobs']['root']['capability_sha256']),
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
    state=load(folder);row=state['jobs'].get(job)
    require(job in ('root','worker1','worker2') and isinstance(cap,str) and row is not None
            and secrets.compare_digest(hashed(cap),row['capability_sha256']), 'Wrong role capability')
    require(state['phase']=='running' and row['status']=='running','Closed role job')
    budget(state)
    return state


def seal(folder, job, cap, findings=''):
    folder=Path(folder).resolve();require(job in ('worker1','worker2'),'Only allocated worker may seal')
    with lock(folder,job), registry.locked(folder/'registry'):
        state=role(folder,job,cap);members=registry.read(folder/'registry')
        require('integration_release' not in members and job in members['workers'],'Closed or unallocated contribution')
        require(isinstance(findings,str) and len(findings.encode())<=1024*1024
                and (members['workers'][job]['mode']!='review' or findings.strip()), 'Invalid worker findings')
        receipt=snapshot(folder,job)
        info=inspect(folder,load(folder),job);require(not info['State']['Running'],'Sealing requires exact stopped container')
        reference=artifacts.seal(members,job,receipt['export'],folder/'contributions'/(job+'.json'),findings)
        require(source.inventory(folder/job/'repo',state['deadline'])==receipt['inventory'],'Worker checkout drift during seal')
        with lock(folder):
            current=load(folder);current['jobs'][job].update(status='sealed_stopped',sealed_artifact=reference,views=[]);save(folder,current)
            event(folder,{'op':'sealed_contribution','job':job,'artifact':reference,
                          'source_inventory_sha256':registry.sha(receipt['inventory']), 'native_qualified':False})
        return {'job':job,'artifact':reference,'native_qualified':False}


def sealed(folder, members, slot):
    require(slot in ('worker1','worker2') and slot in members['workers'],'Unallocated contribution slot')
    row=load(folder)['jobs'].get(slot)
    require(row is not None and row['status']=='sealed_stopped' and 'sealed_artifact' in row,'Original stopped contribution required')
    reference=row['sealed_artifact']
    require(reference['path']==str(Path(folder)/'contributions'/(slot+'.json'))
            and artifacts.pin(reference['path'])==reference,'Owned original contribution changed')
    return reference,row


def view(folder, root_cap, slot):
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
    folder=Path(folder).resolve()
    with contextlib.ExitStack() as stack:
        stack.enter_context(lock(folder,'root'));state=role(folder,'root',root_cap)
        members=registry.read(folder/'registry');require('integration_release' not in members,'No repeat final integration')
        for slot in members['workers']:
            stack.enter_context(lock(folder,slot));sealed(folder,members,slot)
            info=inspect(folder,load(folder),slot);require(not info['State']['Running'],'Worker source fence missing')
        decisions=[artifacts.pin(folder/'registry/decisions'/(slot+'.json')) for slot in members['workers']]
        before=snapshot(folder,'root');original_pins=[]
        def record_intent(reference):
            original_pins.append(reference)
            with lock(folder):event(folder,{'op':'raw_integration_intent','intent':reference,'native_qualified':False})
        try:
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
