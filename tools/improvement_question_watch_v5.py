"""Observe one native source through adaptive branch and owned product cleanup."""
import argparse
import json
import math
import time

from collect import find_session
import improvement_q01_native_watch_v1 as prior_watch
import improvement_question_pilot_v5 as pilot

core, ROOT = pilot.core, pilot.ROOT


def observation(raw, binding, started, now, authority):
    value = prior_watch.observation(raw, binding, started, now)
    events = core.parse(raw if raw.endswith(b'\n') else raw.rsplit(b'\n', 1)[0] + b'\n')
    contexts = sum(e.get('type') == 'turn_context' for e in events)
    count = value['completed_turns']
    if authority is None:
        core.require(contexts <= 1 and count <= 1, 'Second turn before validated branch authority')
        value.update(expected_turns=None, awaiting_semantic_review=count == 1,
                     task_complete=False, branch=None)
    else:
        core.require(authority['actor_native_id'] == binding['actor_native_id']
                     and authority['parent_native_id'] == binding['parent_native_id']
                     and authority['agent_path'] == binding['agent_path']
                     and authority['original_started_at'] == started,
                     'Observer branch identity or original clock changed')
        expected = authority['expected_turns']
        core.require(type(expected) is int and expected in {1, 2}, 'Invalid branch turn count')
        core.require(contexts <= expected and count <= expected, 'Extra branch turn')
        if count == expected:
            core.lifecycle(raw if raw.endswith(b'\n') else raw.rsplit(b'\n', 1)[0] + b'\n', binding, expected)
        value.update(expected_turns=expected, awaiting_semantic_review=False,
                     task_complete=count == expected, branch=authority['branch'])
    return value


def supervise(run, agent_path):
    core.require(bool(run) and all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in run), 'Invalid run ID')
    out = ROOT / 'results' / run
    started = core.decode((out / 'launch-intent.json').read_bytes())['started_at']
    core.require(type(started) in (int, float) and math.isfinite(started), 'Invalid allocation clock')
    deadline = started + 1200
    supervisor_start = time.time()
    core.require(started <= supervisor_start < deadline, 'Supervisor outside original clock')
    with (out / 'observer-supervisor-v5.json').open('x') as stream:
        json.dump({'started_at': supervisor_start, 'allocation_started_at': started,
                   'agent_path': agent_path, 'actor_control': False, 'observer_restarts': 0}, stream)
    source = None
    while time.time() < deadline:
        try:
            source = find_session(agent_path)
            break
        except ValueError as error:
            if not str(error).endswith('found 0'):
                raise
        time.sleep(min(1, max(.01, deadline - time.time())))
    core.require(source is not None, 'No owned native source before original deadline')
    with source.open('rb') as stream:
        header = core.decode(stream.readline())['payload']
    binding = {'actor_native_id': header['id'], 'agent_path': agent_path,
               'parent_native_id': header['parent_thread_id']}
    previous_raw, previous_at, authority_sha = b'', started, None
    with (out / 'root-observation-natural-question-v5.jsonl').open('x') as stream:
        while True:
            now = time.time()
            raw = source.read_bytes()
            try:
                core.require(0 <= now - previous_at <= 30, 'Observer startup or continuous gap exceeds30s')
                core.require(raw.startswith(previous_raw), 'Observed native source is not append-consistent')
                authority_path = out / 'branch-authority-v1.json'
                authority = None
                if authority_path.exists():
                    current_sha = pilot.legacy.sha(authority_path)
                    core.require(authority_sha is None or authority_sha == current_sha, 'Branch authority replaced')
                    authority_sha = current_sha
                    authority = pilot.validated_authority(run)
                elif authority_sha is not None:
                    raise ValueError('Previously observed authority removed')
                value = observation(raw, binding, started, now, authority)
                grade_path = out / 'grade.json'
                if grade_path.exists():
                    grade = core.decode(grade_path.read_bytes())
                    usage_path = out / 'native-usage-v5.json'
                    if usage_path.exists():
                        usage = core.decode(usage_path.read_bytes())
                        value['root_terminal_outcome'] = grade['status']
                        value['controller_closed'] = (
                            grade['status'] in {'fail', 'evaluation_error', 'infra_error', 'pass', 'review_pending', 'public_verified', 'grading_private'}
                            and usage.get('native_completion_observed') is True
                            and usage['source_sha256'] == core.digest(raw)
                            and grade.get('product_cleanup', {}).get('removed') is True
                            and (value['task_complete'] or grade.get('deadline_aborted') is True
                                 or grade['status'] == 'evaluation_error'))
            except Exception as error:
                value = {'observed_at': now, 'native_session_id': binding['actor_native_id'],
                         'native_prefix_sha256': core.digest(raw), 'observation_error': str(error)}
                stream.write(json.dumps(value) + '\n'); stream.flush()
                print(json.dumps(value), flush=True)
                raise
            value['authority_sha256'] = authority_sha
            stream.write(json.dumps(value) + '\n'); stream.flush()
            print(json.dumps(value), flush=True)
            if value.get('controller_closed') or value['deadline_reached']:
                return value
            previous_raw, previous_at = raw, now
            time.sleep(min(10, max(.01, deadline - time.time())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('run'); parser.add_argument('agent_path')
    args = parser.parse_args(); supervise(args.run, args.agent_path)
