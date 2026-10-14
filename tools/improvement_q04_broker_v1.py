"""Coordinator-owned Q04 Flutter broker draft. No comparative/superiority qualification.

Actors can call only job-scoped actions. Native accepted-trace auditing remains
mandatory; CLI possession is not native identity or a universal host sandbox.
"""
import argparse
import ast
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
import improvement_q04_runtime_v3 as runtime
import improvement_q04_artifacts_v1 as artifacts
from improvement_q04_native_v2 import audit, binding, parse, runtime_completed, strict_loads
from improvement_q04_verifier_v5 import verify as public_verify

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'runtime/protocol-probes'
JOBS = ('root', 'pricing', 'reservations')
SOURCES = ('improvement_q04_broker_v1.py', 'improvement_q04_native_v2.py',
           'improvement_q04_native_v1.py', 'improvement_q04_runtime_v3.py',
           'improvement_q04_artifacts_v1.py', 'improvement_q04_verifier_v5.py',
           'improvement_software_artifacts_v3.py', 'improvement_software_native_binding_v2.py',
           'improvement_usage_v4.py', 'improvement_usage_v1.py', 'dialogue_schema.py',
           'improvement_dialogue_native_v8.py', 'transport.py', 'collect.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def folder_for(name):
    if not isinstance(name, str) or not re.fullmatch('q04-broker-v1-[a-z0-9-]{1,48}', name):
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


def source_closure():
    pending=[ROOT/'tools'/name for name in SOURCES];found=set()
    while pending:
        path=pending.pop()
        if path in found:continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_bytes())):
            names=[alias.name for alias in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) else []
            for name in names:
                if name:
                    local=ROOT/'tools'/(name.split('.')[0]+'.py')
                    if local.is_file() and local not in found:pending.append(local)
    return found


def check_launch_freeze(path,starting,seconds):
    frozen=json.loads(Path(path).read_bytes())
    if (frozen.get('status')!='frozen' or frozen.get('prelaunch_review_verdict')!='pass'
            or seconds!=1200 or frozen.get('model')!='gpt-6.1-sol' or frozen.get('effort')!='medium'
            or frozen.get('image_id')!=runtime.IMAGE or frozen.get('condition') not in {'A','C0','C14'}):
        raise ValueError('Reviewed fixed-model1200second prospective freeze required')
    review_path=ROOT/frozen['prelaunch_review_path']
    if not review_path.is_relative_to(ROOT/'results/improvement-v1') or sha(review_path)!=frozen['prelaunch_review_sha256']:
        raise ValueError('Independent prelaunch receipt absent or changed')
    review=json.loads(review_path.read_bytes())
    if review.get('verdict')!='pass' or review.get('issues'):raise ValueError('Independent prelaunch review not passing')
    required=source_closure()|{ROOT/'AGENTS.md',ROOT/'docs/improvement-spec-v1.md',ROOT/'runtime/image.json'}
    fixture=ROOT/'improvement_cases/confirmatory/Q04'
    required|={p for parent in [fixture/'repo'] for p in parent.rglob('*') if p.is_file()}
    required|={fixture/'task.md',fixture/'metadata.json',ROOT/'results/improvement-v1/Q04-behavior-qualification-review-v1.json'}
    condition=frozen['condition'];actual=artifacts.tree(starting);expected=artifacts.tree(fixture/'repo')
    if condition!='A':
        skill=ROOT/'snapshots'/condition
        skill_tree=artifacts.tree(skill)
        expected.update({'.agents':{'kind':'directory','mode':0o755},'.agents/skills':{'kind':'directory','mode':0o755}})
        expected.update({'.agents/skills/codify'+('' if n=='.' else '/'+n):v for n,v in skill_tree.items()})
        required|={p for p in skill.rglob('*') if p.is_file()}
        if condition=='C14':required.add(ROOT/'results/improvement-v1/candidate-C14-freeze-v1.json')
    if actual!=expected or frozen.get('starting_tree')!=expected:raise ValueError('Starting public case/skill drift')
    names={str(p.relative_to(ROOT)) for p in required}
    if not names<=set(frozen['source_hashes']) or not names<=set(review['source_hashes']):
        raise ValueError('Complete independently reviewed local closure/publiccase/skill/image pins required')
    for name,digest in frozen['source_hashes'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Prelaunch source changed: '+name)
    for name in names:
        if frozen['source_hashes'][name]!=review['source_hashes'][name]:raise ValueError('Prelaunch reviewed bytes differ')
    return frozen


def create(name, starting, root_path, coordinator_source, coordinator_native_id, launch_freeze, seconds=1200):
    """Trusted coordinator API only. Source/path authority must be established outside."""
    folder, starting = folder_for(name), Path(starting).resolve()
    fixture = ROOT/'improvement_cases/confirmatory/Q04'
    frozen=check_launch_freeze(launch_freeze,starting,seconds)
    if not re.fullmatch('/root/[a-z0-9_]+', root_path):
        raise ValueError('Unique immediate product root path required')
    parent_raw = prefix(coordinator_source)
    _, header = parse(parent_raw)
    if header['id'] != coordinator_native_id or header.get('agent_path') not in {None, '/root'}:
        raise ValueError('Trusted coordinator locator mismatch')
    public = (fixture/'task.md').read_text()
    tasks = {job: public+'\nJob: '+job+'\n'+(
        'Integrate and verify both independently owned modules.' if job=='root' else
        'Edit only lib/'+job+'.dart. Preserve all other startup entities and permissions.\n'
        'Remove only generated validation outputs before finishing; do not change protected startup files.')
        for job in JOBS}
    caps = runtime.create(folder, starting, tasks, seconds=seconds)
    try:
        actors = {job: {'path': root_path if job == 'root' else root_path + '/' + job} for job in JOBS}
        for job, row in actors.items():
            request = folder / ('request-' + job + '.txt')
            row['bootstrap_code'] = 'text(await tools.exec_command(' + json.dumps({'cmd': 'cat ' + str(request), 'max_output_tokens': 6500}) + '));'
            row['request_path'] = str(request)
        for job, row in actors.items():
            command = f'python3 {ROOT}/tools/improvement_q04_broker_v1.py --run {name} --job {job} --cap {caps[job]} --op exec --data '
            example = command + shlex.quote(json.dumps({'command': 'cat /eval-input/task.md', 'seconds': 30}))
            body = ['You own one isolated Q04 coding job. Read the public task using the broker.',
                    'Only the first exact bootstrap host read is allowed. All repository operations use this broker.',
                    'No direct host, Docker, network, connectors, provider APIs or other files. Do not send messages or restart an actor.',
                    'Use only literal text(await tools.exec_command({...})); wrappers. cmd must be one literal JSON string. No JS variables, templates or additional tools.',
                    'Execution status is in broker JSON. For a returned outer session_id poll that exact handle via text(await tools.write_stdin({...})); with empty chars.',
                    'If /work/repo/.agents/skills/codify/SKILL.md exists, read it through exec and use $codify for this job.\nOn a deadline or broker rejection, stop and report incomplete in final. Retain failures. Do not send a collaboration message.',
                    'Broker --op exec --data accepts a shell-quoted JSON object with command and seconds (1..120). Example exact wrapper:',
                    'text(await tools.exec_command(' + json.dumps({'cmd': example, 'max_output_tokens': 6500, 'yield_time_ms': 1000}) + '));']
            if job == 'root':
                body += ['You are the integration owner. Do not write worker modules yourself. Dispatch exactly two fresh native workers pricing and reservations, fork_turns none, model gpt-6.1-sol, reasoning_effort medium.',
                         'For each worker message, instruct the first tool to execute exactly its bootstrap below, then follow the request. Do not add requirements, code or other results.',
                         json.dumps({j: actors[j]['bootstrap_code'] for j in ('pricing', 'reservations')}),
                         'Allowed root native calls: those two spawn_agent calls; list_agents with path_prefix ' + root_path + '; wait_agent with timeout_ms 10000..60000. No followup/send_message or other native routes.',
                         'After both workers complete, list their actual runtime statuses. Use root broker --op seal --data {"job":"pricing"} and reservations, then --op view for each job to inspect its sealed code and receipts.',
                         'Use --op decide --data {"job":"pricing","decision":"accept","reason":"your concrete code/contract rationale"} for each. Rejection is retained and cannot be replaced.',
                         'Then --op integrate --data {} to copy only accepted files, and --op verify --data {} to directly run protected combined tests. Final report must describe actual results and limitations. Cite the exact checks[].argv returned by verification and the corresponding exit codes. Views expose base_tree_sha256, changed_paths and protected_entities_unchanged; inspect those facts before acceptance.',
                         'For every root action use the same literal wrapper prefix, replacing --op and its shell-quoted JSON data.']
            else:
                body += ['Only exec actions allowed. Own only lib/' + job + '.dart, preserve every other entity and mode. Do not delegate or call collaboration tools. Run focused public tests for your own module. After you complete, root seals your contribution through its seal operation. Report your actual implementation and tests; worker-owned sealing is not available.']
            request = Path(row['request_path']); request.write_text('\n'.join(body) + '\n')
            row['request_sha256'] = sha(request)
        paths = [ROOT / 'tools' / source for source in SOURCES] + [Path(row['request_path']) for row in actors.values()]
        paths += list(starting.rglob('*')) + [fixture/'task.md', Path(launch_freeze)]
        paths += [ROOT/n for n in frozen['source_hashes']]
        registration = {'run_name': name, 'actors': actors, 'capability_hashes': {j: runtime.hashed(c) for j,c in caps.items()},
            'coordinator_path': '/root', 'coordinator_source': str(coordinator_source), 'coordinator_native_id': coordinator_native_id,
            'image_id': runtime.IMAGE, 'source_hashes': {str(p.relative_to(ROOT)): sha(p) for p in paths if p.is_file()},
            'superiority_proven': False, 'complete_final_cost': False,
            'launch_freeze_sha256': sha(launch_freeze), 'forced_three_actor_pilot': True,
            'initial_plaintext_native_verification': False}
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
    entries=[a for a in state['actions'] if a['job']==job]
    receipts=proof['broker_receipts']
    if len(entries)!=len(receipts):raise ValueError('Missing native broker result receipts')
    for entry, receipt in zip(entries,receipts):
        if entry['status']=='completed':
            expected={'status':'ok','result':entry['result']};code=0
        elif entry['status']=='failed':
            expected={'status':'error',**entry['error']};code=1
        else:raise ValueError('Unclosed action')
        actual=strict_loads(receipt['stdout'])
        if receipt['request']!=entry['request'] or receipt['exit_code']!=code or actual!=expected:
            raise ValueError('Native broker result differs from exact ledger outcome')


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
                if set(data) != expected or worker not in {'pricing', 'reservations'}:
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
                    stop_owned(folder, worker)
                    base = json.loads((folder / 'configuration.json').read_bytes())['base']
                    seal = artifacts.seal_worker(base, folder / worker / 'repo', worker, folder / 'artifacts' / (worker + '.json'))
                    seal.update(native=native, runtime_status=runtime_status, native_source=child_source)
                    state['seals'][worker] = seal; result = {k:v for k,v in seal.items() if k != 'native'}
                elif operation == 'view':
                    seal = state['seals'][worker]
                    if sha(seal['artifact']) != seal['artifact_sha256']:
                        raise ValueError('Sealed artifact changed')
                    result = sealed_view(folder, state, worker)
                    state['views'][worker] = seal['artifact_sha256']
                else:
                    if worker in state['decisions'] or state['views'].get(worker) != state['seals'][worker]['artifact_sha256']:
                        raise ValueError('Decision requires prior exact code view; no replacement')
                    if data['decision'] not in {'accept','reject'} or not isinstance(data['reason'], str) or not data['reason'].strip():
                        raise ValueError('Explicit decision/rationale required')
                    state['decisions'][worker] = {**state['seals'][worker], 'decision': data['decision'], 'reason': data['reason']}
                    result = {'job': worker, 'decision': data['decision'], 'reason': data['reason']}
            elif operation == 'integrate':
                if data or state['phase'] != 'prepared' or set(state['decisions']) != {'pricing','reservations'}:
                    raise ValueError('Both original decisions required before single integration')
                stop_owned(folder, 'root')
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
                result = verification_view(fresh_verify(folder, registration))
                if result['status'] != 'completed' or not result['pass'] or not result['removed'] or not result['source_unchanged']:
                    raise ValueError('Protected public Flutter checks did not pass and close normally')
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



def sealed_view(folder, state, worker):
    """Expose validated origin, exact delta and protected entities to acceptance owner."""
    seal = state['seals'][worker]
    if sha(seal['artifact']) != seal['artifact_sha256']:
        raise ValueError('Sealed artifact changed')
    artifact = json.loads(Path(seal['artifact']).read_bytes())
    base = json.loads((folder/'configuration.json').read_bytes())['base']
    current = artifacts.tree(folder/worker/'repo')
    delta = sorted(name for name in set(base['files'])|set(current)
                   if base['files'].get(name) != current.get(name))
    if (artifact['base_tree_sha256'] != base['tree_sha256']
        or artifact['path'] != base['scopes'][worker]
        or delta != [artifact['path']]
        or current[artifact['path']]['sha256'] != artifact['payload_sha256']):
        raise ValueError('Sealed origin, scope or protected entities changed')
    return {'artifact_sha256': seal['artifact_sha256'], 'path': artifact['path'],
            'base_tree_sha256': artifact['base_tree_sha256'], 'changed_paths': delta,
            'protected_entities_unchanged': True, 'payload_sha256': artifact['payload_sha256'],
            'worker_native_id': seal['native']['usage']['native_session_id'],
            'code': bytes.fromhex(artifact['payload_hex']).decode('utf-8'),
            'worker_actions': [a for a in state['actions'] if a['job'] == worker]}


def verification_view(result):
    """Return actual check argv/results, fixed environment and typed machine closure."""
    return {key: result.get(key) for key in ('status','pass','removed','source_unchanged',
        'checks','machine','identity','container_id','image_id','first_error','cleanup_errors',
        'create_argv','source_before','source_path','expected_nonloading_tests')}



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


def fresh_verify(folder, registration):
    state=runtime.load(folder)
    runtime.budget(state)
    return public_verify(folder/'root/repo',folder/('public-verifier-'+uuid.uuid4().hex),state['deadline'],expected_tests=1)


def stop_owned(folder, job, cleanup=False):
    """Budget-bound normal fence; cleanup fence remains usable after deadline."""
    with runtime.lock(folder):
        state=runtime.load(folder)
        info=runtime.inspect(folder,state,job,cleanup=cleanup)
        name=state['jobs'][job]['container']
        if info['State']['Running']:
            try: runtime.docker(['stop','-t','2',name],timeout=10 if cleanup else min(10,runtime.budget(state)))
            except (subprocess.TimeoutExpired,subprocess.CalledProcessError):
                runtime.docker(['kill',name],timeout=10 if cleanup else min(10,runtime.budget(state)))
        info=runtime.inspect(folder,state,job,cleanup=cleanup)
        if info['State']['Running']:raise ValueError('Filesystem fence unproven')
        state['jobs'][job]['status']='stopped';runtime.persist(folder,state)
        runtime.event(folder,{'op':'broker_stopped','job':job,'identity':info,'cleanup_mode':cleanup})



def abort(name, reason):
    """Trusted coordinator failure cleanup; native interruption is an external step.

    The caller must inspect actual runtime handles and interrupt those same actors.
    This receipt never claims native termination/full cost from stopped Docker jobs.
    """
    folder = folder_for(name)
    try:
        registration=config(folder);configuration_error=None
    except Exception as drift:
        registration=json.loads((folder/'protocol.json').read_bytes())
        if registration.get('run_name')!=name or set(registration.get('actors',{}))!=set(JOBS):
            raise ValueError('Emergency ownership registration unavailable') from drift
        configuration_error={'type':type(drift).__name__,'message':str(drift)}
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('Concrete original failure reason required')
    intent = folder/'abort-intent.json'
    with gate(folder):
        if load(folder)['phase'] == 'closed_protocol_as_of_seal':
            raise ValueError('Already closed protocol; preserve prior closure')
        if not intent.exists():
            artifacts.atomic_json(intent, {'requested_at':time.time(),'original_reason':reason,
                'registered_actor_paths':{j:r['path'] for j,r in registration['actors'].items()},
                'acceptance_configuration_error':configuration_error},exclusive=True)
    # Stop filesystems before waiting for the in-flight bounded broker action lock.
    early_errors = []
    rstate = runtime.load(folder)
    for job,row in rstate['jobs'].items():
        if row['status'] == 'removed': continue
        try:
            info = runtime.inspect(folder,rstate,job,cleanup=True)
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
        state['acceptance_configuration_error']=configuration_error
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
                stop_owned(folder,job,cleanup=True)
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
            deadline_state=runtime.load(folder);runtime.budget(deadline_state)
            proofs,originals={},{}
            for job in JOBS:
                raw,source=bind_actor(folder,registration,state,job)
                originals[job]=(raw,source)
                proof=audit(raw,registration_view(registration,state),job,ROOT)
                reconcile_requests(folder,registration,state,job,proof);proofs[job]=proof
            ends=[c['completed_at'] for p in proofs.values() for c in p['usage']['completions']]
            if not ends or any(type(t) not in {int,float} or not deadline_state['started_at']<=t<=deadline_state['deadline'] for t in ends):
                raise ValueError('Actual participant completion outside original trajectory')
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
                stop_owned(folder,job,cleanup=True)
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
                runtime.budget(deadline_state)
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
        result = action(args.run,args.job,args.cap,args.op,strict_loads(args.data))
        print(json.dumps({'status':'ok','result':result}))
    except Exception as error:
        print(json.dumps({'status':'error','type':type(error).__name__,'message':str(error)}))
        raise SystemExit(1)
