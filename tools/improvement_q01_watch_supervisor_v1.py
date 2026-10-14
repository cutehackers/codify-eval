"""Prestart observer before dispatch; never replaces or controls evaluated actors."""
import argparse
import json
from pathlib import Path
import time

import improvement_q01_native_watch_v1 as watcher
import improvement_q01_dialogue_core_v1 as core
from collect import find_session


def supervise(run, agent_path):
    core.require(bool(run) and all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in run), 'Invalid run ID')
    out = watcher.ROOT / 'results' / run
    started = core.decode((out / 'launch-intent.json').read_bytes())['started_at']
    deadline = started + 1200
    with (out / 'observer-supervisor-v1.json').open('x') as stream:
        json.dump({'started_at': time.time(), 'allocation_started_at': started, 'agent_path': agent_path,
                   'actor_control': False, 'observer_restarts': 0}, stream)
    source = None
    while time.time() < deadline:
        try:
            source = find_session(agent_path)
            break
        except ValueError as error:
            if not str(error).endswith('found 0'):
                raise
        time.sleep(min(1, max(.01, deadline - time.time())))
    core.require(source is not None, 'No owned actor native source before original deadline')
    with source.open('rb') as stream:
        header = core.decode(stream.readline())['payload']
    binding = {'actor_native_id': header['id'], 'agent_path': agent_path, 'parent_native_id': header['parent_thread_id']}
    with (out / 'root-observation-q01-v1.jsonl').open('x') as stream:
        while True:
            now = time.time()
            raw = source.read_bytes()
            value = watcher.observation(raw, binding, started, now)
            grade = out / 'grade.json'
            if grade.exists():
                outcome = core.decode(grade.read_bytes())
                if outcome.get('status') in ('fail', 'evaluation_error', 'infra_error', 'pass', 'review_pending'):
                    usage_path = out / 'native-usage-v4.json'
                    if usage_path.exists():
                        usage = core.decode(usage_path.read_bytes())
                        value['root_terminal_outcome'] = outcome['status']
                        value['root_terminal_native_sha256'] = usage['source_sha256']
                        # A question failure ends after one genuine completed turn.
                        # Never infer completion from a lock/status file alone.
                        value['controller_closed'] = (usage.get('native_completion_observed') is True
                            and usage['source_sha256'] == core.digest(raw)
                            and outcome.get('product_cleanup', {}).get('removed') is True)
            stream.write(json.dumps(value) + '\n'); stream.flush()
            print(json.dumps(value), flush=True)
            if value['task_complete'] or value['deadline_reached'] or value.get('controller_closed'):
                return value
            time.sleep(min(10, max(.01, deadline - time.time())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('run'); parser.add_argument('agent_path')
    args = parser.parse_args(); supervise(args.run, args.agent_path)
