"""Owned Docker job lifecycle only; native acceptance/accounting remain external.

Actors receive job-scoped capabilities, never this coordinator API. Root mounts
are read-only. Integration requires a stopped root and the reviewed artifact core.
"""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import time
import uuid

from improvement_software_artifacts_v3 import atomic_json, freeze_base, tree

IMAGE = 'sha256:9751b1bbd374a218e0fe7dcd362e478f2b8bb5453dbed90658da8dd0b2be3638'
JOBS = ('root', 'label', 'quantity')

def hashed(value):
    return hashlib.sha256(value.encode()).hexdigest()

def docker(args, timeout=30, check=True):
    return subprocess.run(['docker'] + args, capture_output=True, text=True,
                          timeout=timeout, check=check)

def budget(state):
    remaining = state['deadline'] - time.time()
    if remaining < 1:
        raise ValueError('Trajectory deadline exhausted')
    return remaining

def within_budget(state, args, check=True):
    return docker(args, timeout=min(30, budget(state)), check=check)

def load(folder):
    return json.loads((Path(folder) / 'state.json').read_text())

@contextlib.contextmanager
def lock(folder):
    with (Path(folder) / 'lock').open('a+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield

def persist(folder, state):
    atomic_json(Path(folder) / 'state.json', state)

def event(folder, value):
    value = dict(value, time=time.time())
    with (Path(folder) / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps(value) + '\n')
        stream.flush()
        os.fsync(stream.fileno())

def inspect(folder, state, job):
    row = state['jobs'][job]
    info = json.loads(docker(['inspect', row['container']]).stdout)[0]
    labels = info['Config'].get('Labels', {})
    if (info['Id'] != row['container_id'] or info['Image'] != IMAGE
            or labels.get('codify.software.run') != state['run_id']
            or labels.get('codify.software.configuration') != state['configuration_sha256']
            or labels.get('codify.software.job') != job
            or info['HostConfig']['NetworkMode'] != 'none'):
        raise ValueError('Container identity/ownership/network changed')
    mounts = info['Mounts']
    expected = {'/work/repo': (str(Path(folder) / job / 'repo'), job != 'root'),
                '/eval-input': (str(Path(folder) / job / 'input'), False)}
    if len(mounts) != 2 or {m['Destination'] for m in mounts} != set(expected):
        raise ValueError('Unexpected mounts')
    for mount in mounts:
        source, writable = expected[mount['Destination']]
        if (mount['Type'] != 'bind' or mount['Source'] != source
                or mount['RW'] != writable):
            raise ValueError('Mount source/permission changed')
    return info

def create(folder, starting, tasks, seconds=300):
    started_at = time.time()
    folder, starting = Path(folder).resolve(), Path(starting).resolve()
    if folder == starting or starting in folder.parents:
        raise ValueError('Runtime directory must be outside starting repository')
    if folder.exists() or set(tasks) != set(JOBS) or not 1 <= seconds <= 1800:
        raise ValueError('Invalid/new namespace required')
    if shutil.disk_usage(folder.parent).free < 3 * 1024 ** 3:
        raise ValueError('Insufficient disk before allocation')
    base = freeze_base(starting, {'label': 'pkg/label.py', 'quantity': 'pkg/quantity.py'})
    config = {'base': base, 'image': IMAGE, 'tasks': tasks, 'seconds': seconds,
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    configuration = json.dumps(config, sort_keys=True)
    folder.mkdir()
    atomic_json(folder / 'configuration.json', config, exclusive=True)
    run_id = uuid.uuid4().hex
    caps = {job: secrets.token_hex(24) for job in JOBS}
    state = {'run_id': run_id, 'configuration_sha256': hashed(configuration),
        'started_at': started_at, 'deadline': started_at + seconds,
        'phase': 'provisioning', 'jobs': {}, 'first_error': None,
        'native_binding_qualified': False, 'superiority_proven': False}
    persist(folder, state)
    try:
        for job in JOBS:
            budget(state)
            clone = folder / job / 'repo'
            clone.parent.mkdir()
            shutil.copytree(starting, clone)
            if tree(clone) != base['files']:
                raise ValueError('Clone drift')
            controls = folder / job / 'input'
            controls.mkdir()
            (controls / 'task.md').write_text(tasks[job])
            name = 'codify-software-' + run_id + '-' + job
            if within_budget(state, ['inspect', name], check=False).returncode == 0:
                raise ValueError('Container name already allocated')
            state['jobs'][job] = {'container': name, 'container_id': None,
                'capability_sha256': hashed(caps[job]), 'status': 'creation_intent',
                'commands': 0}
            persist(folder, state)
            within_budget(state, ['create', '--name', name, '--network', 'none',
                '--label', 'codify.software.run=' + run_id,
                '--label', 'codify.software.configuration=' + state['configuration_sha256'],
                '--label', 'codify.software.job=' + job,
                '-v', str(clone) + ':/work/repo' + (':ro' if job == 'root' else ''),
                '-v', str(controls) + ':/eval-input:ro', '-w', '/work/repo',
                '-e', 'PYTHONDONTWRITEBYTECODE=1', IMAGE, 'sleep', 'infinity'])
            info = json.loads(within_budget(state, ['inspect', name]).stdout)[0]
            state['jobs'][job]['container_id'] = info['Id']
            persist(folder, state)
            inspect(folder, state, job)
            within_budget(state, ['start', name])
            state['jobs'][job]['status'] = 'running'
            persist(folder, state)
            event(folder, {'op': 'created', 'job': job, 'identity': inspect(folder, state, job)})
        budget(state)
        state['phase'] = 'running'
        persist(folder, state)
        return caps
    except BaseException as error:
        state['first_error'] = {'type': type(error).__name__, 'message': str(error)}
        persist(folder, state)
        try:
            cleanup(folder)
        except BaseException as cleanup_error:
            error.cleanup_error = str(cleanup_error)
        raise

def command(folder, job, capability, text, seconds=60):
    folder = Path(folder).resolve()
    with lock(folder):
        state = load(folder)
        row = state['jobs'].get(job)
        if row is None or not secrets.compare_digest(hashed(capability), row['capability_sha256']):
            event(folder, {'op': 'denied', 'job': job, 'before_subprocess': True})
            raise ValueError('Wrong job/capability')
        remaining = state['deadline'] - time.time()
        if (state['phase'] != 'running' or row['status'] != 'running'
                or remaining <= 0 or row['commands'] >= 20):
            event(folder, {'op': 'denied', 'job': job, 'before_subprocess': True})
            raise ValueError('Closed job/deadline/command limit')
        if not isinstance(text, str) or len(text.encode()) > 65536 or not 1 <= seconds <= 120:
            raise ValueError('Invalid command')
        info = inspect(folder, state, job)
        if not info['State']['Running']:
            raise ValueError('Container stopped')
        remaining = budget(state)
        duration = min(seconds, int(remaining))
        row['commands'] += 1
        persist(folder, state)
        event(folder, {'op': 'command_start', 'job': job, 'command': text,
                       'number': row['commands'], 'timeout': duration})
        begin = time.monotonic()
        # Persisting the start receipt can also consume the remaining budget.
        duration = min(duration, int(budget(state)))
        try:
            completed = docker(['exec', row['container'], 'timeout', '--signal=TERM',
                '--kill-after=2s', str(duration) + 's', 'bash', '-lc',
                'cd /work/repo && ' + text], timeout=duration + 5, check=False)
            result = {'exit_code': completed.returncode, 'stdout': completed.stdout,
                      'stderr': completed.stderr}
        except subprocess.TimeoutExpired as error:
            result = {'exit_code': 124, 'error': str(error)}
        result.update(op='command_result', job=job, number=row['commands'],
                      elapsed_seconds=time.monotonic() - begin)
        event(folder, result)
        inspect(folder, state, job)
        return result

def stop(folder, job):
    folder = Path(folder).resolve()
    with lock(folder):
        state = load(folder)
        info = inspect(folder, state, job)
        if info['State']['Running']:
            docker(['stop', '-t', '2', state['jobs'][job]['container']])
        info = inspect(folder, state, job)
        if info['State']['Running']:
            raise ValueError('Stop not confirmed')
        state['jobs'][job]['status'] = 'stopped'
        persist(folder, state)
        event(folder, {'op': 'stopped', 'job': job, 'identity': info})

def cleanup(folder):
    """Preserve first error and evidence, remove only verifiably owned resources."""
    folder = Path(folder).resolve()
    with lock(folder):
        state = load(folder)
        errors = []
        for job, row in state['jobs'].items():
            if row['status'] == 'removed':
                continue
            try:
                # Creation may have returned ambiguously. Recover only exact ownership.
                if row['container_id'] is None:
                    found = docker(['inspect', row['container']], check=False)
                    if found.returncode:
                        if 'No such object:' not in found.stderr:
                            raise ValueError('Container absence unverified')
                        row['status'] = 'removed'
                        persist(folder, state)
                        continue
                    row['container_id'] = json.loads(found.stdout)[0]['Id']
                info = inspect(folder, state, job)
                if info['State']['Running']:
                    try:
                        docker(['stop', '-t', '2', row['container']])
                    except BaseException as stop_error:
                        event(folder, {'op': 'stop_error', 'job': job,
                            'type': type(stop_error).__name__, 'message': str(stop_error)})
                        docker(['kill', row['container']])
                info = inspect(folder, state, job)
                if info['State']['Running']:
                    docker(['kill', row['container']])
                    info = inspect(folder, state, job)
                if info['State']['Running']:
                    raise ValueError('Filesystem not stopped')
                atomic_json(folder / (job + '-final-container.json'), info)
                diff = docker(['diff', row['container']]).stdout
                (folder / (job + '-container-diff.txt')).write_text(diff)
                docker(['rm', row['container']])
                absent = docker(['inspect', row['container']], check=False)
                if absent.returncode == 0 or 'No such object:' not in absent.stderr:
                    raise ValueError('Removal not confirmed')
                row['status'] = 'removed'
                persist(folder, state)
            except BaseException as error:
                errors.append({'job': job, 'type': type(error).__name__, 'message': str(error)})
        state['cleanup_errors'] = errors
        state['phase'] = 'cleanup_failed' if errors else 'closed_runtime_only'
        persist(folder, state)
        event(folder, {'op': 'cleanup', 'errors': errors,
                       'native_binding_qualified': False, 'complete_final_cost': False})
        if errors:
            raise ValueError('Owned cleanup unverified: ' + json.dumps(errors))
