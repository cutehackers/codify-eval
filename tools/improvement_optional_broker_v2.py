"""Public read/exec/lazy-worker transport precursor.

No native delivery authority or artifact acceptance is implemented here. This
version cannot qualify a comparison. Coordinator owns registration and cleanup.
Lock order: broker job -> runtime job -> registry -> brief runtime state lock.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import time

import improvement_optional_runtime_v6 as runtime
import improvement_optional_inventory_v3 as strict
from improvement_software_artifacts_v3 import atomic_json, encoded

require = runtime.require
JOBS = {'root', 'worker1', 'worker2'}
OPS = {'read', 'exec', 'worker'}
LIMIT = 40 * 1024 * 1024


def original(path):
    """Bounded immutable regular file, preserving original bytes."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= LIMIT, 'Bounded regular control required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(LIMIT + 1)
        after = os.fstat(fd)
        require(len(raw) == before.st_size and
                (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Control changed during read')
        return raw
    finally:
        os.close(fd)


@contextlib.contextmanager
def locked(folder, job):
    require(job in JOBS, 'Unknown broker job')
    with (Path(folder) / ('broker-' + job + '.lock')).open('a+b') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def register(folder, job, cap):
    """Coordinator-only registration after successful owned provisioning."""
    folder = Path(folder).resolve()
    require(job in JOBS and isinstance(cap, str) and re.fullmatch('[0-9a-f]{48}', cap), 'Invalid registration')
    with locked(folder, job):
        state = runtime.load(folder); row = state['jobs'].get(job)
        require(state['phase'] == 'running' and row is not None and row['status'] == 'running'
                and secrets.compare_digest(runtime.hashed(cap), row['capability_sha256']), 'Unprepared registration')
        runtime.budget(state)
        request = original(folder / job / 'input/request.txt')
        require(len(request) <= 2 * 1024 * 1024, 'Public request limit exceeded')
        request.decode('utf-8')
        control = {'job': job, 'run_id': state['run_id'],
                   'configuration_sha256': state['configuration_sha256'],
                   'capability_sha256': row['capability_sha256'],
                   'request_sha256': hashlib.sha256(request).hexdigest(), 'request_bytes': len(request),
                   'native_qualified': False, 'comparison_eligible': False}
        directory = folder / 'broker' / job
        directory.mkdir(parents=True, exist_ok=False)
        (directory / 'actions').mkdir()
        atomic_json(directory / 'control.json', control, exclusive=True)
        return control


def ledger(folder, job):
    """Derived list keeps unreceipted original intents pending, never retries."""
    require(job in JOBS, 'Unknown ledger job')
    folder = Path(folder); state = runtime.load(folder)
    directory = folder / 'broker' / job / 'actions'; rows = []; previous_finished = state['started_at']
    for path in sorted(directory.iterdir()):
        require(path.is_dir() and not path.is_symlink() and path.name == f'{len(rows):06d}', 'Unknown or skipped action entity')
        require(not rows or rows[-1]['status'] != 'pending', 'Action after unreconciled intent')
        row = strict.decoded(original(path / 'intent.json'))
        require(isinstance(row, dict) and set(row) == {'number', 'action_id', 'request', 'run_id', 'configuration_sha256', 'started_at'}, 'Exact intent fields required')
        require(type(row['number']) is int and row['number'] == len(rows)
                and type(row['action_id']) is int and row['action_id'] == row['number'] * 3 + sorted(JOBS).index(job), 'Action sequence drift')
        require(isinstance(row['request'], dict) and set(row['request']) == {'job', 'op', 'data'}
                and row['request']['job'] == job and isinstance(row['request']['op'], str)
                and isinstance(row['request']['data'], dict), 'Exact action request required')
        require(row['run_id'] == state['run_id'] and row['configuration_sha256'] == state['configuration_sha256'], 'Foreign intent configuration')
        require(type(row['started_at']) in (int, float) and math.isfinite(row['started_at'])
                and previous_finished <= row['started_at'] < state['deadline'], 'Intent outside original or serial clock')
        receipt = path / 'receipt.json'
        if receipt.exists():
            result = strict.decoded(original(receipt))
            require(isinstance(result, dict) and result.get('status') in ('completed', 'failed'), 'Unknown receipt status')
            require(set(result) == {'status', 'intent_sha256', 'finished_at', 'result' if result['status'] == 'completed' else 'error'}, 'Exact receipt fields required')
            require(result['intent_sha256'] == hashlib.sha256(original(path / 'intent.json')).hexdigest(), 'Receipt intent drift')
            require(type(result['finished_at']) in (int, float) and math.isfinite(result['finished_at'])
                    and result['finished_at'] >= row['started_at'], 'Invalid receipt clock')
            if result['status'] == 'completed':
                require(isinstance(result['result'], dict) and result['finished_at'] < state['deadline'], 'Unqualified completed result')
            else:
                error = result['error']
                require(isinstance(error, dict) and set(error) == {'type', 'message'}
                        and all(isinstance(v, str) for v in error.values()) and error['type'], 'Exact failed result required')
            row.update({k: result[k] for k in ('status', 'result', 'error') if k in result})
            previous_finished = result['finished_at']
        else:
            row['status'] = 'pending'
        rows.append(row)
    return rows


def dispatch(folder, job, cap, op, data):
    folder = Path(folder).resolve()
    require(job in JOBS and isinstance(cap, str) and re.fullmatch('[0-9a-f]{48}', cap), 'Invalid job capability')
    with locked(folder, job):
        control = strict.decoded(original(folder / 'broker' / job / 'control.json'))
        state = runtime.load(folder); row = state['jobs'].get(job)
        require(isinstance(control, dict) and set(control) == {'job', 'run_id', 'configuration_sha256',
                'capability_sha256', 'request_sha256', 'request_bytes', 'native_qualified', 'comparison_eligible'}
                and type(control['request_bytes']) is int and 0 <= control['request_bytes'] <= 2 * 1024 * 1024
                and isinstance(control['request_sha256'], str) and re.fullmatch('[0-9a-f]{64}', control['request_sha256'])
                and control['native_qualified'] is False and control['comparison_eligible'] is False, 'Invalid broker control schema')
        require(row is not None and control['job'] == job and control['run_id'] == state['run_id']
                and control['configuration_sha256'] == state['configuration_sha256']
                and secrets.compare_digest(runtime.hashed(cap), control['capability_sha256'])
                and control['capability_sha256'] == row['capability_sha256'], 'Wrong broker authority')
        require(state['phase'] == 'running' and row['status'] == 'running', 'Closed broker job')
        runtime.budget(state)
        require(isinstance(op, str) and isinstance(data, dict) and len(encoded(data)) <= 65536, 'Bounded operation object required')
        previous = ledger(folder, job)
        require(not any(a['status'] == 'pending' for a in previous), 'Unreconciled original action')
        number = len(previous); require(number < 1000000, 'Action sequence exhausted')
        action = folder / 'broker' / job / 'actions' / f'{number:06d}'; action.mkdir()
        intent = {'number': number, 'action_id': number * 3 + sorted(JOBS).index(job), 'request': {'job': job, 'op': op, 'data': data},
                  'run_id': state['run_id'], 'configuration_sha256': state['configuration_sha256'],
                  'started_at': time.time()}
        atomic_json(action / 'intent.json', intent, exclusive=True)
        try:
            require(op in OPS and (job == 'root' or op != 'worker'), 'Operation forbidden or not implemented')
            if op == 'read':
                require(not data and not previous, 'Public read must be first and unique')
                raw = original(folder / job / 'input/request.txt')
                require(len(raw) == control['request_bytes'] and hashlib.sha256(raw).hexdigest() == control['request_sha256'], 'Public request drift')
                value = {'text': raw.decode('utf-8')}
            else:
                require(previous and previous[0]['request']['op'] == 'read' and previous[0]['status'] == 'completed', 'Complete original public read required')
                if op == 'exec':
                    require(set(data) <= {'command', 'seconds'} and 'command' in data, 'Exact exec fields required')
                    value = runtime.command(folder, job, cap, data['command'], data.get('seconds', 120))
                else:
                    require(set(data) <= {'goal', 'scope', 'mode'} and {'goal', 'scope'} <= set(data), 'Exact worker fields required')
                    require(isinstance(data['goal'], str) and data['goal'].strip()
                            and isinstance(data['scope'], list) and all(isinstance(p, str) for p in data['scope'])
                            and len(set(data['scope'])) == len(data['scope'])
                            and set(data['scope']) <= set(state['editable_paths'])
                            and data.get('mode', 'write') in ('write', 'review')
                            and (bool(data['scope']) if data.get('mode', 'write') == 'write' else not data['scope']),
                            'Invalid worker goal/lease/mode')
                    value = runtime.worker(folder, cap, data['goal'], data['scope'], data.get('mode', 'write'))
                    try:
                        register(folder, value['job'], value['capability'])
                    except Exception as error:
                        runtime.failure(folder, error)
                        raise
                    value = dict(value, native_qualified=False, comparison_eligible=False)
            runtime.budget(runtime.load(folder))
            receipt = {'status': 'completed', 'result': value}
            output = {'status': 'ok', 'result': value}; code = 0
        except Exception as error:
            error_value = {'type': type(error).__name__, 'message': str(error)}
            receipt = {'status': 'failed', 'error': error_value}
            output = {'status': 'error', **error_value}; code = 1
        receipt.update(intent_sha256=hashlib.sha256(original(action / 'intent.json')).hexdigest(), finished_at=time.time())
        atomic_json(action / 'receipt.json', receipt, exclusive=True)
        return output, code


def main():
    parser = argparse.ArgumentParser()
    for name in ('run', 'job', 'cap', 'op', 'data'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    try:
        require(re.fullmatch('[A-Za-z0-9_-]{1,100}', args.run), 'Invalid runtime name')
        folder = Path(__file__).resolve().parent.parent / 'runtime' / args.run
        body, code = dispatch(folder, args.job, args.cap, args.op, strict.decoded(args.data))
    except Exception as error:
        body, code = {'status': 'error', 'type': type(error).__name__, 'message': str(error)}, 1
    print(json.dumps(body, ensure_ascii=False, allow_nan=False))
    raise SystemExit(code)


if __name__ == '__main__':
    main()
