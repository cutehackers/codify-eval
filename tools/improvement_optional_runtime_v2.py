"""Trusted actor-free Docker lifecycle precursor, not a public broker.

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

import improvement_optional_source_v2 as source
import improvement_optional_registry_v2 as registry
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


def inspect(folder,state,job,cleanup=False):
    row=state['jobs'][job];info=json.loads(call(state,['inspect',row['container']],cleanup).stdout)[0]
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
        try:call(state,['stop','-t','2',state['jobs'][job]['container']],cleanup,seconds=10)
        except (subprocess.TimeoutExpired,subprocess.CalledProcessError):
            call(state,['kill',state['jobs'][job]['container']],cleanup,seconds=10)
    require(not inspect(folder,state,job,cleanup)['State']['Running'],'Filesystem not stopped')
    status(folder,job,'stopped')


def start(folder,job):
    state=load(folder);require(state['phase'] in ('preparing','running'),'Runtime closing or failed')
    inspect(folder,state,job)
    call(state,['start',state['jobs'][job]['container']])
    require(inspect(folder,state,job)['State']['Running'],'Start unconfirmed');status(folder,job,'running')


def provision(folder,job,task):
    with lock(folder,job):
        return _provision(folder,job,task)


def _provision(folder,job,task):
    state=load(folder);cap=secrets.token_hex(24);name='codify-optional-'+state['run_id']+'-'+job
    controls=Path(folder)/job/'input';controls.mkdir();(controls/'request.txt').write_text(task)
    found=call(state,['inspect',name],check=False)
    require(found.returncode!=0 and 'No such object:' in found.stderr,'New owned namespace required')
    with lock(folder):
        state=load(folder);require(state['phase'] in ('preparing','running'),'Runtime closing or failed')
        require(job not in state['jobs'],'No job retry/replacement')
        state['jobs'][job]={'container':name,'container_id':None,'capability_sha256':hashed(cap),
                            'status':'creation_intent','commands':0};save(folder,state)
    call(state,['create','--name',name,'--network','none',
                '--label','codify.optional.run='+state['run_id'],
                '--label','codify.optional.configuration='+state['configuration_sha256'],
                '--label','codify.optional.job='+job,
                '-v',str(Path(folder)/job/'repo')+':/work/repo',
                '-v',str(controls)+':/eval-input:ro','-w','/work/repo',
                '-e','GIT_OPTIONAL_LOCKS=0','-e','PYTHONDONTWRITEBYTECODE=1',IMAGE,'sleep','infinity'])
    info=json.loads(call(state,['inspect',name]).stdout)[0]
    with lock(folder):
        state=load(folder);state['jobs'][job]['container_id']=info['Id'];save(folder,state)
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
        value=bounded_exec(folder,job,number,['exec',row['container'],'timeout','--signal=TERM','--kill-after=2s',
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


def failure(folder,error):
    with lock(folder):
        state=load(folder)
        if state['first_error'] is None:state['first_error']={'type':type(error).__name__,'message':str(error)}
        state['phase']='failed_preservation_required';save(folder,state)


def cleanup(folder):
    """Actor-free caller now; future caller must first prove native closure."""
    folder=Path(folder).resolve()
    with lock(folder):state=load(folder);state['phase']='closing';save(folder,state)
    errors=[]
    for job in list(state['jobs']):
        with lock(folder,job):
            try:
                current=load(folder);row=current['jobs'][job]
                if row['status']=='removed':
                    absent=call(current,['inspect',row['container_id'] or row['container']],cleanup=True,check=False)
                    require(absent.returncode!=0 and 'No such object:' in absent.stderr,'Previously removed resource reappeared')
                    continue
                if row['container_id'] is None:
                    found=call(current,['inspect',row['container']],cleanup=True,check=False)
                    if found.returncode:
                        require('No such object:' in found.stderr,'Creation absence unknown');status(folder,job,'removed');continue
                    with lock(folder):
                        current=load(folder);current['jobs'][job]['container_id']=json.loads(found.stdout)[0]['Id'];save(folder,current)
                snapshot(folder,job,cleanup=True)
                current=load(folder);inspect(folder,current,job,cleanup=True)
                archive_tmp(folder,current['jobs'][job]['container'],job)
                call(current,['rm',current['jobs'][job]['container']],cleanup=True)
                absent=call(current,['inspect',current['jobs'][job]['container_id']],cleanup=True,check=False)
                require(absent.returncode!=0 and 'No such object:' in absent.stderr,'Exact removal unconfirmed')
                status(folder,job,'removed')
                with lock(folder):event(folder,{'op':'removed','job':job,'container_id':current['jobs'][job]['container_id']})
            except BaseException as error:errors.append({'job':job,'type':type(error).__name__,'message':str(error)})
    with lock(folder):
        current=load(folder);current['cleanup_errors']=errors
        current['phase']='preservation_failed' if errors else 'closed_docker_only';save(folder,current)
    require(not errors,'Stopped owned resources retained for unpreserved diagnostics: '+str(errors))
    return current
