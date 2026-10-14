"""Public optional implementation and contribution transport precursor.

Native delivery/current inventory/full accounting remain coordinator authority.
This version cannot qualify a comparison. Coordinator owns registration/cleanup.
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

import improvement_baseline_runtime_v4 as runtime
import improvement_baseline_native_dispatch_v4 as native_dispatch
import improvement_optional_inventory_v3 as strict
from improvement_software_artifacts_v3 import atomic_json, encoded

require = runtime.require
JOBS = {'root', 'worker1', 'worker2'}
ROOT_OPS = {'read_reply', 'read', 'exec', 'worker', 'view', 'decide', 'integrate', 'verify'}
WORKER_OPS = {'read', 'exec', 'seal'}
# Fixed verify aggregates two independently16MiB raw command results. JSON
# escapes can expand their combined32MiB to192MiB; allow bounded256MiB with
# metadata overhead. Serialize/size-check before any completed broker receipt.
LIMIT = 256 * 1024 * 1024


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
    runtime.role(folder,job,cap)
    runtime.question_validate(folder)
    if job!='root':runtime.guard_question_operation(folder,job,cap,'register')
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
    require(op != 'read_reply' or job == 'root' and type(data) is dict and not data,
            'Root-only empty reply read required before action intent')
    # Read-only authentication precedes any broker lock/action or worker effect.
    state = runtime.role(folder, job, cap)
    if job == 'root':
        state, members = runtime.declared_runtime(folder, cap)
        require(op != 'worker' or state['worker_cap'] == 2,
                'Solo cap0 denies worker before broker action intent')
    else:
        members = runtime.registry.read(folder / 'registry')
        require(type(state.get('worker_cap')) is int and state['worker_cap'] == 2
                and members['configuration']['worker_cap'] == 2 and job in members['workers'],
                'Only reserved voluntary workers may use the broker')
    runtime.guard_question_operation(folder, job, cap, op)
    with locked(folder, job), runtime.question_operation_lock(folder):
        runtime.guard_question_operation(folder, job, cap, op)
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
        returned_value_received = False
        try:
            require(op in (ROOT_OPS if job == 'root' else WORKER_OPS), 'Operation forbidden or not implemented')
            if op == 'read':
                require(not data and not previous, 'Public read must be first and unique')
                raw = original(folder / job / 'input/request.txt')
                require(len(raw) == control['request_bytes'] and hashlib.sha256(raw).hexdigest() == control['request_sha256'], 'Public request drift')
                value = {'text': raw.decode('utf-8')}
            elif op == 'read_reply':
                require(job == 'root' and not data, 'Root-only empty reply read required')
                value = runtime.read_question_reply(folder, cap, action / 'intent.json')
            else:
                require(previous and previous[0]['request']['op'] == 'read' and previous[0]['status'] == 'completed', 'Complete original public read required')
                if op == 'exec':
                    require(set(data) <= {'command', 'seconds'} and 'command' in data, 'Exact exec fields required')
                    value = runtime.command(folder, job, cap, data['command'], data.get('seconds', 120))
                elif op == 'worker':
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
                        bootstrap_row = native_dispatch.prepare(folder,value['job'],value['capability'])
                    except Exception as error:
                        runtime.failure(folder, error)
                        raise
                    value = dict(value, native_bootstrap=bootstrap_row['native_bootstrap'], native_qualified=False, comparison_eligible=False)
                elif op == 'seal':
                    require(set(data) <= {'findings'}, 'Exact seal fields required')
                    value = runtime.seal(folder, job, cap, data.get('findings', ''))
                elif op == 'view':
                    require(set(data) == {'slot'}, 'Exact contribution slot required')
                    value = runtime.view(folder, cap, data['slot'])
                elif op == 'decide':
                    require(set(data) == {'slot', 'view', 'decision', 'reason'}, 'Exact decision fields required')
                    value = runtime.decide(folder, cap, data['slot'], data['view'], data['decision'], data['reason'])
                elif op == 'integrate':
                    require(not data, 'Empty final integration request required')
                    value = runtime.integrate(folder, cap)
                elif op == 'verify':
                    require(not data, 'Empty fixed public verification request required')
                    value = runtime.verify(folder, cap)
            returned_value_received = True
            runtime.question_validate(folder)
            require(isinstance(value, dict), 'Callback result must be an object')
            serialized = json.dumps({'status': 'completed', 'result': value}, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()
            require(len(serialized) + 1024 <= LIMIT, 'Callback result exceeds bounded receipt allowance')
            runtime.budget(runtime.load(folder))
            completed_at = time.time()
            require(type(completed_at) in (int, float) and math.isfinite(completed_at)
                    and intent['started_at'] <= completed_at < state['deadline'], 'Final callback receipt outside original clock')
            receipt = {'status': 'completed', 'result': value, 'finished_at': completed_at}
            output = {'status': 'ok', 'result': value}; code = 0
        except Exception as error:
            if returned_value_received and op != 'read':
                runtime.failure(folder, error)
            error_value = {'type': type(error).__name__, 'message': str(error)}
            receipt = {'status': 'failed', 'error': error_value, 'finished_at': time.time()}
            output = {'status': 'error', **error_value}; code = 1
        receipt.update(intent_sha256=hashlib.sha256(original(action / 'intent.json')).hexdigest())
        atomic_json(action / 'receipt.json', receipt, exclusive=True)
        if op == 'read_reply' and code == 0:
            try:
                runtime.complete_question_reply_read(folder, cap, action / 'receipt.json')
            except Exception as error:
                runtime.failure(folder, error)
                output, code = {'status':'error','type':type(error).__name__,'message':str(error)}, 1
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
