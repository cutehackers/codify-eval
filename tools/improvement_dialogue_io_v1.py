"""Serialized container broker with a native reply-read barrier before writes."""
import argparse
import datetime as dt
import json
import subprocess
import time

from improvement_dialogue_native_v1 import READ
from improvement_dialogue_phase_v1 import directory, inspect_container, locked, read, unlock, verify


def run_command(run_id, command, timeout=180):
    folder = directory(run_id)
    with locked(folder):
        state = read(folder / 'state.json')
        verify(folder, state)
        remaining = state['started_at'] + state['time_limit_seconds'] - time.time()
        if remaining <= 0:
            raise TimeoutError('Full trajectory budget exhausted; preserve first failure')
        identity = inspect_container(folder, state)
        if not identity['State']['Running']:
            raise ValueError('Container is stopped')
        if state['phase'] == 'reply_read' and command != READ:
            # No implementation subprocess exists until actual read stdout is in native evidence.
            try:
                unlock(folder, state)
            except ValueError as error:
                entry = {'run_id': run_id, 'phase': state['phase'], 'container_id': state['container_id'],
                         'command': command, 'exit_code': 126, 'output': str(error),
                         'denied_before_subprocess': True, 'time': dt.datetime.now(dt.timezone.utc).isoformat()}
                with (folder / 'commands.jsonl').open('a') as stream:
                    stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
                return entry
            identity = inspect_container(folder, state)
        if state['phase'] not in {'question', 'reply_read', 'implementation'}:
            raise ValueError('No commands allowed in this phase')
        timeout = min(timeout, 600, max(1, int(remaining)))
        start = time.monotonic()
        entry = {'run_id': run_id, 'phase': state['phase'], 'command': command,
                 'container': state['container'], 'container_id': state['container_id'],
                 'timeout': timeout, 'time': dt.datetime.now(dt.timezone.utc).isoformat(),
                 'repository_writable': state['phase'] == 'implementation'}
        with (folder / 'command-starts.jsonl').open('a') as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
        try:
            completed = subprocess.run(['docker', 'exec', state['container'], 'timeout', '--signal=TERM',
                '--kill-after=5s', str(timeout) + 's', 'bash', '-lc', 'cd /work/repo && ' + command],
                capture_output=True, text=True, timeout=timeout + 10)
            entry.update(exit_code=completed.returncode, output=completed.stdout + completed.stderr)
        except subprocess.TimeoutExpired as error:
            entry.update(exit_code=124, output=str(error), timed_out=True)
        entry['elapsed_seconds'] = time.monotonic() - start
        after = inspect_container(folder, state)
        if after['Id'] != identity['Id']:
            raise ValueError('Command container changed')
        with (folder / 'commands.jsonl').open('a') as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
        return entry


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--cmd', required=True)
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    print(json.dumps(run_command(args.run, args.cmd, args.timeout), ensure_ascii=False))
