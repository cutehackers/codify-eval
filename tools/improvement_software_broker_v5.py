"""Coordinator-owned synthetic broker. No comparative/superiority qualification.

Actors can call only job-scoped actions. Native accepted-trace auditing remains
mandatory; CLI possession is not native identity or a universal host sandbox.
"""
import argparse
import contextlib
import fcntl
import gzip
import os
import selectors
import shutil
import uuid
import hashlib
import json
from pathlib import Path
import re
import secrets
import shlex
import subprocess
import time

from collect import find_session
import improvement_software_runtime_v2 as runtime
import improvement_software_artifacts_v3 as artifacts
from improvement_software_broker_native_v5 import audit, binding, parse, runtime_completed

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'runtime/protocol-probes'
JOBS = ('root', 'label', 'quantity')
SOURCES = ('improvement_software_broker_v5.py', 'improvement_software_broker_native_v5.py',
           'improvement_software_runtime_v2.py', 'improvement_software_artifacts_v3.py',
           'improvement_software_native_binding_v2.py', 'improvement_usage_v4.py',
           'improvement_usage_v1.py', 'dialogue_schema.py', 'transport.py', 'collect.py')
VERIFY = 'python3 -m unittest discover -s tests -v'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def folder_for(name):
    if not isinstance(name, str) or not re.fullmatch('software-broker-v5-[a-z0-9-]{1,48}', name):
        raise ValueError('Unknown run namespace')
    return HOME / name


def config(folder):
    value = json.loads((folder / 'protocol.json').read_bytes())
    if value['run_name'] != folder.name:
        raise ValueError('Registration namespace changed')
    for name, expected in value['source_hashes'].items():
        if sha(ROOT / name) != expected:
            raise ValueError('Frozen source/request changed: ' + name)
    return value


@contextlib.contextmanager
def locked(folder):
    with (folder / 'protocol-lock').open('a+b') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield


def load(folder):
    return json.loads((folder / 'broker-state.json').read_bytes())


def save(folder, state):
    artifacts.atomic_json(folder / 'broker-state.json', state)


def prefix(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete native prefix; observe the same actor again')
    return raw


def bind_actor(folder, registration, state, job):
    row = registration['actors'][job]
    source = find_session(row['path'])
    raw = prefix(source)
    if job == 'root':
        parent_path = registration['coordinator_path']
        parent_source = registration['coordinator_source']
        parent_raw = prefix(parent_source)
        _, header = parse(parent_raw)
        if header['id'] != registration['coordinator_native_id']:
            raise ValueError('Coordinator source identity changed')
    else:
        root_raw, root_source = bind_actor(folder, registration, state, 'root')
        parent_path, parent_source, parent_raw = registration['actors']['root']['path'], root_source, root_raw
    proof = binding(parent_raw, raw, parent_path, row['path'])
    old = state['bindings'].get(job)
    if old and (old['child_native_id'] != proof['child_native_id'] or old['spawn_call_id'] != proof['spawn_call_id']):
        raise ValueError('Actor allocation changed')
    if not old:
        state['bindings'][job] = dict(proof, source=str(source), parent_source=str(parent_source))
        save(folder, state)
    return raw, str(source)


def registration_view(registration, state):
    value = dict(registration, actors={j: dict(row) for j, row in registration['actors'].items()})
    for job, proof in state['bindings'].items():
        value['actors'][job]['source'] = proof['source']
    return value


def create(name, fixture, root_path, coordinator_source, coordinator_native_id, seconds=1800):
    """Trusted coordinator API only. Source/path authority must be established outside."""
    folder, fixture = folder_for(name), Path(fixture).resolve()
    if not re.fullmatch('/root/[a-z0-9_]+', root_path):
        raise ValueError('Unique immediate product root path required')
    parent_raw = prefix(coordinator_source)
    _, header = parse(parent_raw)
    if header['id'] != coordinator_native_id or header.get('agent_path') not in {None, '/root'}:
        raise ValueError('Trusted coordinator locator mismatch')
    tasks = {job: (fixture / (job + '_task.md')).read_text() for job in JOBS}
    caps = runtime.create(folder, fixture / 'starting', tasks, seconds=seconds)
    try:
        actors = {job: {'path': root_path if job == 'root' else root_path + '/' + job} for job in JOBS}
        for job, row in actors.items():
            request = folder / ('request-' + job + '.txt')
            row['bootstrap_code'] = 'text(await tools.exec_command(' + json.dumps({'cmd': 'cat ' + str(request), 'max_output_tokens': 6500}) + '));'
            row['request_path'] = str(request)
        for job, row in actors.items():
            command = f'python3 {ROOT}/tools/improvement_software_broker_v5.py --run {name} --job {job} --cap {caps[job]} --op exec --data '
            example = command + shlex.quote(json.dumps({'command': 'cat /eval-input/task.md', 'seconds': 30}))
            body = ['You own one isolated synthetic coding job. Read the public task using the broker.',
                    'Only the first exact bootstrap host read is allowed. All repository operations use this broker.',
                    'No direct host, Docker, network, connectors, provider APIs or other files. Do not send messages or restart an actor.',
                    'Use only literal text(await tools.exec_command({...})); wrappers. cmd must be one literal JSON string. No JS variables, templates or additional tools.',
                    'Execution status is in broker JSON. For a returned outer session_id poll that exact handle via text(await tools.write_stdin({...})); with empty chars.',
                    'On a deadline or broker rejection, stop and report incomplete in final. Retain failures. Do not send a collaboration message.',
                    'Broker --op exec --data accepts a shell-quoted JSON object with command and seconds (1..120). Example exact wrapper:',
                    'text(await tools.exec_command(' + json.dumps({'cmd': example, 'max_output_tokens': 6500, 'yield_time_ms': 1000}) + '));']
            if job == 'root':
                body += ['You are the integration owner. Do not write worker modules yourself. Dispatch exactly two fresh native workers label and quantity, fork_turns none, model gpt-6.1-sol, reasoning_effort medium.',
                         'For each worker message, instruct the first tool to execute exactly its bootstrap below, then follow the request. Do not add requirements, code or other results.',
                         json.dumps({j: actors[j]['bootstrap_code'] for j in ('label', 'quantity')}),
                         'Allowed root native calls: those two spawn_agent calls; list_agents with path_prefix ' + root_path + '; wait_agent with timeout_ms 10000..60000. No followup/send_message or other native routes.',
                         'After both workers complete, list their actual runtime statuses. Use root broker --op seal --data {"job":"label"} and quantity, then --op view for each job to inspect its sealed code and receipts.',
                         'Use --op decide --data {"job":"label","decision":"accept","reason":"your concrete code/contract rationale"} for each. Rejection is retained and cannot be replaced.',
                         'Then --op integrate --data {} to copy only accepted files, and --op verify --data {} to directly run protected combined tests. Final report must describe actual results and limitations.',
                         'For every root action use the same literal wrapper prefix, replacing --op and its shell-quoted JSON data.']
            else:
                body += ['Only exec actions allowed. Own only pkg/' + job + '.py, preserve every other entity and mode. Do not delegate or call collaboration tools. Run focused public tests for your own module.']
            request = Path(row['request_path']); request.write_text('\n'.join(body) + '\n')
            row['request_sha256'] = sha(request)
        paths = [ROOT / 'tools' / source for source in SOURCES] + [Path(row['request_path']) for row in actors.values()]
        paths += list((fixture / 'starting').rglob('*')) + [fixture / (job + '_task.md') for job in JOBS]
        registration = {'run_name': name, 'actors': actors, 'capability_hashes': {j: runtime.hashed(c) for j,c in caps.items()},
            'coordinator_path': '/root', 'coordinator_source': str(coordinator_source), 'coordinator_native_id': coordinator_native_id,
            'image_id': runtime.IMAGE, 'source_hashes': {str(p.relative_to(ROOT)): sha(p) for p in paths if p.is_file()},
            'superiority_proven': False, 'complete_final_cost': False}
        artifacts.atomic_json(folder / 'protocol.json', registration, exclusive=True)
        save(folder, {'phase': 'prepared', 'bindings': {}, 'seals': {}, 'views': {}, 'decisions': {}, 'actions': [], 'first_error': None})
        return {'run_name': name, 'root_bootstrap_code': actors['root']['bootstrap_code'], 'configuration_sha256': sha(folder / 'protocol.json')}
    except BaseException:
        runtime.cleanup(folder)
        raise


def reconcile_requests(folder, registration, state, job, proof):
    starts = [a['request'] for a in state['actions'] if a['job'] == job]
    if proof['broker_requests'] != starts or any(a['status'] == 'started' for a in state['actions'] if a['job'] == job):
        raise ValueError('Native broker requests do not exactly match complete action ledger')


def action(name, job, cap, operation, data):
    folder = folder_for(name)
    with locked(folder):
        registration, state = config(folder), load(folder)
        if job not in JOBS or not secrets.compare_digest(runtime.hashed(cap), registration['capability_hashes'][job]):
            runtime.event(folder, {'op': 'broker_denied', 'job': job, 'before_subprocess': True})
            raise ValueError('Wrong job/capability')
        allowed = {'exec'} if job != 'root' else {'exec', 'seal', 'view', 'decide', 'integrate', 'verify'}
        if operation not in allowed or not isinstance(data, dict) or state['phase'] in {'closed_protocol_as_of_seal','abort_pending_native','aborted_runtime_only'} or (folder/'abort-intent.json').exists():
            raise ValueError('Forbidden operation or closed protocol')
        runtime.budget(runtime.load(folder))
        raw, source = bind_actor(folder, registration, state, job)
        request = {'job': job, 'op': operation, 'data': data}
        entry = {'job': job, 'request': request, 'status': 'started', 'started_at': time.time()}
        state['actions'].append(entry); save(folder, state)
        try:
            if operation == 'exec':
                if set(data) != {'command', 'seconds'} or type(data['seconds']) is not int:
                    raise ValueError('Invalid exec payload')
                result = runtime.command(folder, job, cap, data['command'], data['seconds'])
            elif operation in {'seal', 'view', 'decide'}:
                expected = {'job', 'decision', 'reason'} if operation == 'decide' else {'job'}
                worker = data.get('job')
                if set(data) != expected or worker not in {'label', 'quantity'}:
                    raise ValueError('Invalid worker action')
                if operation == 'seal':
                    if worker in state['seals']:
                        raise ValueError('Preserve original worker seal')
                    child_raw, child_source = bind_actor(folder, registration, state, worker)
                    view = registration_view(registration, state)
                    native = audit(child_raw, view, worker, ROOT)
                    reconcile_requests(folder, registration, state, worker, native)
                    runtime_status = runtime_completed(raw, {j: r['path'] for j,r in registration['actors'].items()},
                        max(c['completed_at'] for c in native['usage']['completions']), required={view['actors'][worker]['path']})
                    runtime.stop(folder, worker)
                    base = json.loads((folder / 'configuration.json').read_bytes())['base']
                    seal = artifacts.seal_worker(base, folder / worker / 'repo', worker, folder / 'artifacts' / (worker + '.json'))
                    seal.update(native=native, runtime_status=runtime_status, native_source=child_source)
                    state['seals'][worker] = seal; result = {k:v for k,v in seal.items() if k != 'native'}
                elif operation == 'view':
                    seal = state['seals'][worker]
                    if sha(seal['artifact']) != seal['artifact_sha256']:
                        raise ValueError('Sealed artifact changed')
                    artifact = json.loads(Path(seal['artifact']).read_bytes())
                    state['views'][worker] = seal['artifact_sha256']
                    result = {'artifact_sha256': seal['artifact_sha256'], 'path': artifact['path'],
                              'code': bytes.fromhex(artifact['payload_hex']).decode('utf-8'),
                              'worker_actions': [a for a in state['actions'] if a['job'] == worker]}
                else:
                    if worker in state['decisions'] or state['views'].get(worker) != state['seals'][worker]['artifact_sha256']:
                        raise ValueError('Decision requires prior exact code view; no replacement')
                    if data['decision'] not in {'accept','reject'} or not isinstance(data['reason'], str) or not data['reason'].strip():
                        raise ValueError('Explicit decision/rationale required')
                    state['decisions'][worker] = {**state['seals'][worker], 'decision': data['decision'], 'reason': data['reason']}
                    result = {'job': worker, 'decision': data['decision'], 'reason': data['reason']}
            elif operation == 'integrate':
                if data or state['phase'] != 'prepared' or set(state['decisions']) != {'label','quantity'}:
                    raise ValueError('Both original decisions required before single integration')
                runtime.stop(folder, 'root')
                base = json.loads((folder / 'configuration.json').read_bytes())['base']
                transaction = artifacts.integrate(folder / 'root/repo', base, state['decisions'], folder / 'integration')
                state['transaction'] = str(transaction); state['phase'] = 'integrated'
                save(folder, state)
                rstate = runtime.load(folder); runtime.budget(rstate)
                info = runtime.inspect(folder, rstate, 'root')
                if info['State']['Running']:
                    raise ValueError('Root filesystem not stopped before restart')
                if (folder/'abort-intent.json').exists():
                    raise ValueError('Coordinator abort requested; root restart denied')
                runtime.within_budget(rstate, ['start', rstate['jobs']['root']['container']])
                rstate['jobs']['root']['status'] = 'running'; runtime.persist(folder, rstate)
                result = {'status': 'integrated_pending_root_verification', 'transaction_sha256': sha(transaction)}
            else:
                if data or state['phase'] != 'integrated':
                    raise ValueError('Root verification requires completed integration')
                result = fresh_verify(folder, registration)
                text = result.get('stdout','') + result.get('stderr','')
                if result['exit_code'] != 0 or not re.search(r'Ran 10 tests in [\d.]+s\s+OK\s*$', text):
                    raise ValueError('Protected combined tests did not all pass normally')
                intent = json.loads(Path(state['transaction']).read_bytes())
                if artifacts.tree(folder / 'root/repo') != intent['expected_after']:
                    raise ValueError('Root verification changed protected tree')
                state['phase'] = 'verified'
            entry.update(status='completed', result=result, completed_at=time.time())
        except BaseException as error:
            entry.update(status='failed', error={'type': type(error).__name__, 'message': str(error)}, completed_at=time.time())
            if state['first_error'] is None: state['first_error'] = entry['error']
            save(folder, state)
            raise
        save(folder, state)
        return result


def archive_tmp(folder, container, job, limit=64*1024**2):
    """Bound total stdout/stderr bytes and elapsed time; preserve complete raw tar.

    No compression or duplicate archive allocation during the lifecycle. On any
    failure retain partial raw/stderr plus the stopped container for resumption.
    """
    available=shutil.disk_usage(folder).free-3*1024**3-65536
    limit=min(limit,available)
    if limit<=0:raise ValueError('No archive space above required disk floor')
    raw=folder/(job+'-tmp-'+uuid.uuid4().hex+'.tar')
    errors=raw.with_suffix('.stderr')
    process=None
    with raw.open('xb') as out, errors.open('xb') as err:
        selector=selectors.DefaultSelector()
        try:
            process=subprocess.Popen(['docker','cp',container+':/tmp','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            selector.register(process.stdout,selectors.EVENT_READ,out)
            selector.register(process.stderr,selectors.EVENT_READ,err)
            started=time.monotonic();wall_started=time.time();observed=0
            while selector.get_map():
                remaining=min(30-(time.monotonic()-started),30-(time.time()-wall_started))
                if remaining<=0:raise TimeoutError('Diagnostic archive deadline; partial files retained')
                for key,_ in selector.select(timeout=min(remaining,0.2)):
                    data=os.read(key.fileobj.fileno(),65536)
                    if not data:
                        selector.unregister(key.fileobj);continue
                    if observed+len(data)>limit:
                        raise ValueError('Diagnostic archive byte budget; partial files retained')
                    key.data.write(data);observed+=len(data)
            remaining=min(30-(time.monotonic()-started),30-(time.time()-wall_started))
            if remaining<=0:raise TimeoutError('Diagnostic process deadline')
            if process.wait(timeout=remaining):
                raise ValueError('Diagnostic archive command failed; partial files retained')
            out.flush();err.flush();os.fsync(out.fileno());os.fsync(err.fileno())
        finally:
            if process is not None:
                if process.poll() is None:process.kill()
                process.wait(timeout=5)
                process.stdout.close();process.stderr.close()
            selector.close()


def verifier_identity(folder, registration, name, identity=None):
    info = json.loads(runtime.docker(['inspect',name]).stdout)[0]
    labels = info['Config'].get('Labels',{})
    mounts = info['Mounts']
    if (identity is not None and info['Id'] != identity or info['Image'] != registration['image_id']
            or labels.get('codify.software.verifier') != registration['run_name']
            or info['HostConfig']['NetworkMode'] != 'none' or not info['HostConfig']['ReadonlyRootfs']
            or len(mounts) != 1 or mounts[0]['Type'] != 'bind' or mounts[0]['RW']
            or mounts[0]['Source'] != str(folder/'root/repo') or mounts[0]['Destination'] != '/work/repo'):
        raise ValueError('Fresh verifier identity/isolation mismatch')
    return info


def fresh_verify(folder, registration):
    """Pristine image avoids an actor-modified shell, PATH or Python interpreter."""
    state = runtime.load(folder)
    runtime.budget(state)
    name = 'codify-verifier-' + uuid.uuid4().hex
    receipt = folder / (name + '.json')
    value = {'name':name,'status':'creation_intent','first_error':None,'cleanup_error':None}
    artifacts.atomic_json(receipt,value,exclusive=True)
    identity = None
    try:
        runtime.within_budget(state, ['create','--name',name,'--network','none','--read-only',
            '--label','codify.software.verifier='+registration['run_name'],
            '--tmpfs','/tmp:rw,noexec,nosuid,size=64m','-e','PYTHONDONTWRITEBYTECODE=1',
            '-v',str(folder/'root/repo')+':/work/repo:ro','-w','/work/repo',
            registration['image_id'],'/usr/bin/python3','-I','-B','-m','unittest','discover','-s','tests','-t','.','-v'])
        info = verifier_identity(folder,registration,name); identity = info['Id']
        value.update(container_id=identity,status='created',identity=info)
        artifacts.atomic_json(receipt,value)
        duration = min(120, runtime.budget(state))
        completed = runtime.docker(['start','-a',name],timeout=duration,check=False)
        info = verifier_identity(folder,registration,name,identity)
        if info['State']['Running']:
            raise ValueError('Verifier execution did not terminate')
        result={'exit_code':info['State']['ExitCode'],'stdout':completed.stdout,'stderr':completed.stderr,
                'docker_start_exit_code':completed.returncode,'verifier_receipt':str(receipt)}
        value.update(status='completed',result=result,identity_after=info)
        artifacts.atomic_json(receipt,value)
        return result
    except BaseException as error:
        value.update(status='failed',first_error={'type':type(error).__name__,'message':str(error)})
        if isinstance(error, subprocess.TimeoutExpired):
            value['partial_stdout'] = error.stdout.decode(errors='replace') if isinstance(error.stdout,bytes) else error.stdout
            value['partial_stderr'] = error.stderr.decode(errors='replace') if isinstance(error.stderr,bytes) else error.stderr
        artifacts.atomic_json(receipt,value)
        raise
    finally:
        try:
            found = runtime.docker(['inspect',name],check=False)
            if found.returncode:
                if 'No such object:' not in found.stderr:
                    raise ValueError('Verifier absence unobservable')
            else:
                info = verifier_identity(folder,registration,name,identity)
                if info['State']['Running']:
                    try: runtime.docker(['stop','-t','2',name])
                    except Exception: runtime.docker(['kill',name])
                info = verifier_identity(folder,registration,name,identity)
                if info['State']['Running']:
                    raise ValueError('Verifier stop unconfirmed')
                runtime.docker(['rm',name])
                absent = runtime.docker(['inspect',name],check=False)
                if absent.returncode == 0 or 'No such object:' not in absent.stderr:
                    raise ValueError('Verifier removal unconfirmed')
            value['removed']=True
        except BaseException as cleanup_error:
            value['cleanup_error']={'type':type(cleanup_error).__name__,'message':str(cleanup_error)}
            # Preserve original execution error if cleanup also fails.
            if value['first_error'] is None:
                raise
        finally:
            artifacts.atomic_json(receipt,value)


def abort(name, reason):
    """Trusted coordinator failure cleanup; native interruption is an external step.

    The caller must inspect actual runtime handles and interrupt those same actors.
    This receipt never claims native termination/full cost from stopped Docker jobs.
    """
    folder = folder_for(name)
    registration = config(folder)
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('Concrete original failure reason required')
    intent = folder/'abort-intent.json'
    with gate(folder):
        if load(folder)['phase'] == 'closed_protocol_as_of_seal':
            raise ValueError('Already closed protocol; preserve prior closure')
        if not intent.exists():
            artifacts.atomic_json(intent, {'requested_at':time.time(),'original_reason':reason,
                'registered_actor_paths':{j:r['path'] for j,r in registration['actors'].items()}},exclusive=True)
    # Stop filesystems before waiting for the in-flight bounded broker action lock.
    early_errors = []
    rstate = runtime.load(folder)
    for job,row in rstate['jobs'].items():
        if row['status'] == 'removed': continue
        try:
            info = runtime.inspect(folder,rstate,job)
            if info['State']['Running']: runtime.docker(['kill',row['container']])
        except Exception as error:
            early_errors.append({'job':job,'error':type(error).__name__+': '+str(error)})
    with locked(folder):
        state = load(folder)
        if state['phase'] == 'closed_protocol_as_of_seal':
            raise ValueError('Already closed protocol; preserve prior closure')
        if state['first_error'] is None:
            state['first_error']={'type':'CoordinatorAbort','message':json.loads(intent.read_bytes())['original_reason']}
        state['phase']='abort_pending_native'
        state['early_stop_errors']=early_errors
        save(folder,state)
        snapshots={}
        for job,row in registration['actors'].items():
            try:
                source=find_session(row['path']);raw=prefix(source)
                from improvement_usage_v4 import snapshot
                value=snapshot(raw,row['path'],source)
                value['actual_parent_binding_qualified']=False
                snapshots[job]=value
            except Exception as error:
                snapshots[job]={'usage':None,'qualification_error':type(error).__name__+': '+str(error),
                                'native_completion_observed':False}
        state['abort_observed_native_prefixes']=snapshots
        errors=[]
        rstate=runtime.load(folder)
        for job,row in rstate['jobs'].items():
            if row['status']=='removed':continue
            try:
                runtime.stop(folder,job)
                preserve_tmp(folder,row['container'],job)
            except Exception as error:
                errors.append({'job':job,'error':type(error).__name__+': '+str(error)})
        state['abort_preservation_errors']=errors
        if errors:
            state['retained_resources_are_required_for_unpreserved_diagnostics']=True
            state['resumption']='Resolve recorded diagnostic transport/storage failure, then call abort with the same run and original reason; same stopped resources only, no actor restart.'
        if not errors:
            try:
                runtime.cleanup(folder)
                state['phase']='aborted_runtime_only'
            except Exception as cleanup_error:
                state['abort_cleanup_error']=type(cleanup_error).__name__+': '+str(cleanup_error)
        state['actual_native_interrupt_and_terminal_qualification']=False
        state['complete_final_cost']=False
        state['superiority_proven']=False
        save(folder,state)
        return {'phase':state['phase'],'first_error':state['first_error'],
                'registered_paths_to_reconcile_via_actual_runtime_handles':{j:r['path'] for j,r in registration['actors'].items()},
                'native_termination_qualified':False,'complete_final_cost':False}


@contextlib.contextmanager
def gate(folder):
    """Serialize abort-intent creation with final acceptance, not long Docker work."""
    with (folder/'protocol-gate-lock').open('a+b') as f:
        fcntl.flock(f.fileno(),fcntl.LOCK_EX)
        yield


def preserve_tmp(folder, container, job):
    try:
        archive_tmp(folder,container,job)
    except Exception as first:
        available = max(0,shutil.disk_usage(folder).free-3*1024**3)
        fallback = min(available,2*1024**3)
        runtime.event(folder,{'op':'archive_failed','job':job,'first_error':type(first).__name__+': '+str(first),
                              'fallback_limit':fallback,'partial_archive_retained':True})
        if fallback <= 64*1024**2:
            raise
        # Same stopped container, larger disk-safe bound; no actor/behavior retry.
        archive_tmp(folder,container,job,limit=fallback)


def close(name):
    """Each closure attempt is durable before cleanup; late evidence revokes acceptance."""
    folder = folder_for(name)
    with locked(folder):
        registration,state=config(folder),load(folder)
        allowed={'verified','closure_pending','closure_invalidated','closure_cleanup_failed'}
        if state['phase'] not in allowed:
            raise ValueError('Cannot close unverified/aborted/already closed software run')
        attempts=folder/'closure-attempts';attempts.mkdir(exist_ok=True)
        target=attempts/(uuid.uuid4().hex+'.json')
        attempt={'state':'intent','started_at':time.time(),'first_error':None,'stages':[],
                 'full_native_cost_qualified':False,'complete_final_cost':False,'superiority_proven':False}
        artifacts.atomic_json(target,attempt,exclusive=True)
        state.setdefault('closure_attempts',[]).append(str(target));state['phase']='closure_pending';save(folder,state)
        def checkpoint(stage):
            attempt['stages'].append({'stage':stage,'time':time.time()})
            artifacts.atomic_json(target,attempt)
        def abort_check():
            if (folder/'abort-intent.json').exists():
                raise ValueError('Coordinator abort intent prevents successful closure')
        try:
            abort_check()
            proofs,originals={},{}
            for job in JOBS:
                raw,source=bind_actor(folder,registration,state,job)
                originals[job]=(raw,source)
                proof=audit(raw,registration_view(registration,state),job,ROOT)
                reconcile_requests(folder,registration,state,job,proof);proofs[job]=proof
            ends=[c['completed_at'] for p in proofs.values() for c in p['usage']['completions']]
            status=runtime_completed(prefix(registration['coordinator_source']),{j:r['path'] for j,r in registration['actors'].items()},max(ends))
            records=[p['usage'] for p in proofs.values()]
            if len({r['native_session_id'] for r in records}) != 3:
                raise ValueError('Duplicate product session')
            tokens={k:sum(r['usage'][k] for r in records) if all(isinstance(r['usage'],dict) and type(r['usage'].get(k)) is int and r['usage'][k]>=0 for r in records) else None for k in ('input_tokens','cached_input_tokens','output_tokens','total_tokens')}
            intent=json.loads(Path(state['transaction']).read_bytes())
            if artifacts.tree(folder/'root/repo') != intent['expected_after']:
                raise ValueError('Integrated root tree drift after direct verification')
            attempt.update(native=proofs,runtime_status=status,product_tokens_as_of_attempt=tokens,
                           root_tree_sha256=artifacts.digest(artifacts.encoded(intent['expected_after'])))
            checkpoint('native_cost_and_root_tree_preserved_before_cleanup')
            rstate=runtime.load(folder)
            for job in JOBS:
                abort_check()
                if rstate['jobs'][job]['status']=='removed':continue
                runtime.stop(folder,job)
                preserve_tmp(folder,rstate['jobs'][job]['container'],job)
                checkpoint(job+'_diagnostics_preserved')
            abort_check()
            runtime.cleanup(folder)
            checkpoint('owned_runtime_cleanup_completed')
            for raw,source in originals.values():
                if prefix(source)!=raw:
                    raise ValueError('Late native append revokes closure; re-observe the same actual sources')
            with gate(folder):
                abort_check()
                finished=time.time();wall=finished-rstate['started_at']
                if wall<0:raise ValueError('Backward wall clock; no qualified elapsed measure')
                attempt.update(state='closed_protocol_as_of_seal',sealed_at=finished,wall_seconds=wall)
                checkpoint('stable_source_recheck_and_no_abort')
                state.update(phase='closed_protocol_as_of_seal',sealed_at=finished,native=proofs,runtime_status=status,
                             wall_seconds=wall,product_tokens_as_of_seal=tokens,
                             metrics_unavailable=[k for k,v in tokens.items() if v is None],
                             complete_final_cost=False,superiority_proven=False)
                save(folder,state)
            return state
        except BaseException as error:
            attempt.update(state='failed',first_error={'type':type(error).__name__,'message':str(error)})
            artifacts.atomic_json(target,attempt)
            state['phase']='closure_invalidated'
            if state['first_error'] is None:state['first_error']=attempt['first_error']
            state['last_closure_error']=attempt['first_error'];save(folder,state)
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for field in ('run','job','cap','op','data'): parser.add_argument('--'+field,required=True)
    args = parser.parse_args()
    try:
        result = action(args.run,args.job,args.cap,args.op,json.loads(args.data))
        print(json.dumps({'status':'ok','result':result}))
    except Exception as error:
        print(json.dumps({'status':'error','type':type(error).__name__,'message':str(error)}))
        raise SystemExit(1)
