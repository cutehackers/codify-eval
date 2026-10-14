"""Coordinator-owned synthetic broker. No comparative/superiority qualification.

Actors can call only job-scoped actions. Native accepted-trace auditing remains
mandatory; CLI possession is not native identity or a universal host sandbox.
"""
import argparse
import contextlib
import fcntl
import gzip
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
from improvement_software_broker_native_v1 import audit, binding, parse, runtime_completed

ROOT = Path(__file__).resolve().parents[1]
HOME = ROOT / 'runtime/protocol-probes'
JOBS = ('root', 'label', 'quantity')
SOURCES = ('improvement_software_broker_v1.py', 'improvement_software_broker_native_v1.py',
           'improvement_software_runtime_v2.py', 'improvement_software_artifacts_v3.py',
           'improvement_software_native_binding_v2.py', 'improvement_usage_v4.py',
           'improvement_usage_v1.py', 'dialogue_schema.py', 'transport.py', 'collect.py')
VERIFY = 'python3 -m unittest discover -s tests -v'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def folder_for(name):
    if not isinstance(name, str) or not re.fullmatch('software-broker-v1-[a-z0-9-]{1,48}', name):
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
            command = f'python3 {ROOT}/tools/improvement_software_broker_v1.py --run {name} --job {job} --cap {caps[job]} --op exec --data '
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
        if operation not in allowed or not isinstance(data, dict) or state['phase'] == 'closed_protocol_as_of_seal':
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
                runtime.within_budget(rstate, ['start', rstate['jobs']['root']['container']])
                rstate['jobs']['root']['status'] = 'running'; runtime.persist(folder, rstate)
                result = {'status': 'integrated_pending_root_verification', 'transaction_sha256': sha(transaction)}
            else:
                if data or state['phase'] != 'integrated':
                    raise ValueError('Root verification requires completed integration')
                result = runtime.command(folder, 'root', cap, VERIFY, 120)
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


def close(name):
    """Trusted coordinator only, after actual terminal runtime status observation."""
    folder = folder_for(name)
    with locked(folder):
        registration, state = config(folder), load(folder)
        if state['phase'] != 'verified':
            raise ValueError('Cannot close an unverified software run')
        proofs, originals = {}, {}
        for job in JOBS:
            raw, source = bind_actor(folder, registration, state, job)
            originals[job] = (raw, source)
            proof = audit(raw, registration_view(registration, state), job, ROOT)
            reconcile_requests(folder, registration, state, job, proof)
            proofs[job] = proof
        ends = [c['completed_at'] for p in proofs.values() for c in p['usage']['completions']]
        status = runtime_completed(prefix(registration['coordinator_source']),
                   {j: r['path'] for j,r in registration['actors'].items()}, max(ends))
        rstate = runtime.load(folder)
        # Archive non-mounted temp diagnostics before owned resources are removed.
        for job in JOBS:
            runtime.stop(folder, job)
            name = rstate['jobs'][job]['container']
            with (folder / (job + '-tmp.tar.gz')).open('xb') as out:
                proc = subprocess.Popen(['docker','cp',name+':/tmp','-'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                with gzip.GzipFile(fileobj=out,mode='wb') as zipped:
                    for chunk in iter(lambda: proc.stdout.read(65536), b''): zipped.write(chunk)
                err = proc.stderr.read()
                if proc.wait() != 0: raise ValueError('Temp diagnostics archive failed: ' + err.decode())
        runtime.cleanup(folder)
        for raw, source in originals.values():
            if prefix(source) != raw:
                raise ValueError('Late native append revokes closure; preserve old and re-observe')
        state.update(phase='closed_protocol_as_of_seal', sealed_at=time.time(), native=proofs, runtime_status=status,
                     wall_seconds=time.time()-rstate['started_at'], complete_final_cost=False, superiority_proven=False)
        records = [p['usage'] for p in proofs.values()]
        if len({r['native_session_id'] for r in records}) != 3:
            raise ValueError('Duplicate product session')
        state['product_tokens_as_of_seal'] = {k: sum(r['usage'][k] for r in records) for k in
            ('input_tokens','cached_input_tokens','output_tokens','total_tokens')}
        save(folder, state)
        return state


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
