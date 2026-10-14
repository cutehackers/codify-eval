"""File isolation/sealing/integration core for the planned software broker.

The coordinator owns base/scopes/decisions and the external journal directory.
This module does NOT authenticate model identity, native tool routes, permissions,
runtime completion or accounting. Those remain mandatory broker prerequisites.
"""
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import time
import uuid

LIMIT = 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def path_name(name):
    assert isinstance(name, str) and name and '\\' not in name and '\x00' not in name
    path = Path(name)
    assert not path.is_absolute() and path.as_posix() == name
    assert path.parts and all(part not in {'.', '..'} for part in path.parts)
    return name


def tree(repo):
    repo = Path(repo)
    assert stat.S_ISDIR(repo.lstat().st_mode), 'Repository root must be a real directory'
    result = {'.': {'kind': 'directory', 'mode': stat.S_IMODE(repo.lstat().st_mode)}}
    for path in sorted(repo.rglob('*')):
        mode = path.lstat().st_mode
        assert stat.S_ISREG(mode) or stat.S_ISDIR(mode), 'Symlink/nonregular entity rejected'
        if stat.S_ISREG(mode):
            assert path.stat().st_size <= LIMIT, 'Artifact file size limit'
            result[path_name(path.relative_to(repo).as_posix())] = {'kind': 'file', 'mode': stat.S_IMODE(mode), 'sha256': digest(path.read_bytes())}
        else:
            result[path_name(path.relative_to(repo).as_posix())] = {'kind': 'directory', 'mode': stat.S_IMODE(mode)}
    return result


def freeze_base(repo, scopes):
    files = tree(repo)
    assert set(scopes) == {'label', 'quantity'}, 'This prototype has exactly two fixed workers'
    paths = [path_name(scopes[job]) for job in sorted(scopes)]
    assert len(set(paths)) == 2 and all(name in files and files[name]['kind'] == 'file' for name in paths)
    value = {'files': files, 'scopes': scopes, 'tree_sha256': digest(encoded(files))}
    return value


def atomic_json(path, value, exclusive=False):
    path = Path(path)
    if exclusive:
        # Initial manifests/intents cannot overwrite an earlier attempt.
        with path.open('xb') as stream:
            stream.write(encoded(value) + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
    else:
        descriptor, temporary = tempfile.mkstemp(prefix='.journal-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(encoded(value) + b'\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def seal_worker(base, worker_repo, job, destination):
    assert job in base['scopes']
    assert base['tree_sha256'] == digest(encoded(base['files']))
    current = tree(worker_repo)
    changed = {name for name in set(base['files']) | set(current) if base['files'].get(name) != current.get(name)}
    name = base['scopes'][job]
    assert changed == {name} and name in current, 'Missing contribution or out-of-scope mutation'
    payload = (Path(worker_repo) / name).read_bytes()
    assert digest(payload) == current[name]['sha256']
    assert current[name]['mode'] == base['files'][name]['mode'], 'Contribution permission change rejected'
    artifact = {'job': job, 'path': name, 'base_tree_sha256': base['tree_sha256'],
                'payload_hex': payload.hex(), 'payload_sha256': digest(payload),
                'status': 'files_sealed_pending_native_acceptance',
                'native_binding_qualified': False, 'runtime_qualified': False}
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(destination, artifact, exclusive=True)
    return {'job': job, 'artifact': str(destination), 'artifact_sha256': digest(destination.read_bytes())}


@contextlib.contextmanager
def locked(repo, journal):
    repo, journal = Path(repo).resolve(), Path(journal).resolve()
    assert repo != journal and repo not in journal.parents, 'Journal must be external to repository'
    journal.mkdir(parents=True, exist_ok=True)
    with (journal / 'lock').open('a+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def contributions(base, decisions):
    assert set(decisions) == set(base['scopes']), 'Both worker decisions required'
    result = {}
    for job, decision in decisions.items():
        assert decision['decision'] == 'accept' and isinstance(decision['reason'], str) and decision['reason'].strip()
        artifact_path = Path(decision['artifact'])
        assert stat.S_ISREG(artifact_path.lstat().st_mode), 'Artifact must be a regular file'
        raw = artifact_path.read_bytes()
        assert len(raw) <= 3 * LIMIT and digest(raw) == decision['artifact_sha256'], 'Artifact tampered'
        artifact = json.loads(raw)
        assert artifact['job'] == job and artifact['base_tree_sha256'] == base['tree_sha256']
        name = path_name(artifact['path'])
        assert name == base['scopes'][job] and name not in result, 'Path ownership or overlap violation'
        payload = bytes.fromhex(artifact['payload_hex'])
        assert len(payload) <= LIMIT and digest(payload) == artifact['payload_sha256']
        result[name] = payload
    return result


def apply_files(repo, payloads, after_each=None):
    for index, (name, payload) in enumerate(sorted(payloads.items())):
        target = Path(repo) / name
        descriptor, temporary = tempfile.mkstemp(prefix='.integration-', dir=target.parent)
        os.fchmod(descriptor, stat.S_IMODE(target.lstat().st_mode))
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            directory = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        if after_each:
            after_each(index, name)  # Coordinator-only fault injection for qualification.


def integrate(repo, base, decisions, journal, after_each=None):
    with locked(repo, journal):
        assert base['tree_sha256'] == digest(encoded(base['files']))
        assert tree(repo) == base['files'], 'Root/base drift; reject before writing'
        payloads = contributions(base, decisions)
        expected = {**base['files'], **{name: {'kind': 'file', 'mode': base['files'][name]['mode'], 'sha256': digest(data)} for name, data in payloads.items()}}
        transaction = Path(journal) / (uuid.uuid4().hex + '.json')
        intent = {'state': 'intent', 'root': str(Path(repo).resolve()), 'base': base,
                  'decisions': decisions, 'expected_after': expected, 'created': time.time(),
                  'native_binding_qualified': False, 'runtime_qualified': False,
                  'root_verification_qualified': False, 'complete_final_cost': False,
                  'superiority_proven': False}
        atomic_json(transaction, intent, exclusive=True)
        try:
            apply_files(repo, payloads, after_each)
            assert tree(repo) == expected, 'Integrated tree differs from expected bytes'
            intent['state'] = 'files_integrated_pending_native_and_runtime_qualification'
        except Exception as error:
            intent.update(state='partial_integration', first_error={'type': type(error).__name__, 'message': str(error)})
            atomic_json(transaction, intent)
            raise
        atomic_json(transaction, intent)
        return transaction


def recover(repo, transaction):
    transaction = Path(transaction)
    with locked(repo, transaction.parent):
        intent = json.loads(transaction.read_bytes())
        assert intent['state'] in {'intent', 'partial_integration'} and intent['root'] == str(Path(repo).resolve())
        base = intent['base']
        assert base['tree_sha256'] == digest(encoded(base['files']))
        payloads = contributions(base, intent['decisions'])
        expected = {**base['files'], **{name: {'kind': 'file', 'mode': base['files'][name]['mode'], 'sha256': digest(data)} for name, data in payloads.items()}}
        assert expected == intent['expected_after']
        current = tree(repo)
        assert set(current) == set(base['files'])
        assert all((current[name] == base['files'][name] or current[name] == expected[name]) for name in current), 'Unexpected root bytes; recovery rejected'
        attempt = {'started': time.time(), 'prior_state': intent['state']}
        if intent['state'] == 'intent':
            intent['interrupted_intent_observed'] = True
        intent.setdefault('recovery_attempts', []).append(attempt)
        atomic_json(transaction, intent)
        try:
            apply_files(repo, payloads)
            assert tree(repo) == expected
            intent['state'] = 'files_integrated_pending_native_and_runtime_qualification'
            attempt['status'] = 'files_recovered'
        except Exception as error:
            attempt.update(status='failed', error={'type': type(error).__name__, 'message': str(error)})
            raise
        finally:
            atomic_json(transaction, intent)
        return transaction
