"""Continuous one-turn observation on the original clock. Never controls actors."""
import argparse
import json
from pathlib import Path
import time

from collect import find_session
import improvement_q01_dialogue_core_v1 as core

ROOT = Path(__file__).resolve().parents[1]


def observation(raw, binding, started, now):
    complete = raw.endswith(b'\n')
    prefix = raw if complete else raw.rsplit(b'\n', 1)[0] + b'\n'
    events = core.parse(prefix)
    headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
    core.require(len(headers) == 1 and headers[0].get('id') == binding['actor_native_id']
                 and headers[0].get('agent_path') == binding['agent_path']
                 and headers[0].get('parent_thread_id') == binding['parent_native_id'], 'Observer session changed')
    ends = [e for e in events if e.get('type') == 'event_msg' and e['payload'].get('type') == 'task_complete']
    ids = [core.turn_id(e['payload']) for e in ends]
    core.require(len(ends) <= 1 and len(set(ids)) == len(ids)
                 and all(isinstance(t, str) and bool(t) for t in ids), 'Unexpected completed turn count or identity')
    contexts = [e['payload'] for e in events if e.get('type') == 'turn_context']
    core.require(len(contexts) <= 1 and all(p.get('model') == 'gpt-6.1-sol' and p.get('effort') == 'medium'
                                          for p in contexts), 'Observer context/model mismatch')
    if len(ends) == 1:
        core.lifecycle(prefix, binding, 1)
    return {'observed_at': now, 'elapsed_seconds': now - started, 'completed_turns': len(ends),
            'completed_turn_ids': ids, 'waiting_for_reply_or_followup': False,
            'task_complete': len(ends) == 1, 'complete_prefix': complete,
            'native_session_id': binding['actor_native_id'], 'native_bytes': len(raw),
            'native_prefix_sha256': core.digest(raw), 'complete_native_bytes': len(prefix),
            'complete_native_sha256': core.digest(prefix), 'deadline_reached': now >= started + 1200,
            'calls': sum(e['payload'].get('type') in ('function_call', 'custom_tool_call') for e in events)}


def watch(run_id, agent_path):
    core.require(bool(run_id) and all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in run_id),
                 'Invalid run ID')
    out = ROOT / 'results' / run_id
    source = find_session(agent_path)
    with source.open('rb') as stream:
        header = core.decode(stream.readline())['payload']
    core.require(header.get('agent_path') == agent_path, 'Wrong observer actor')
    binding = {'actor_native_id': header['id'], 'agent_path': agent_path, 'parent_native_id': header['parent_thread_id']}
    started = core.decode((out / 'launch-intent.json').read_bytes())['started_at']
    core.require(type(started) in (int, float), 'Missing original allocation clock')
    # Exclusive log prevents silently continuing a prior observer's evidence.
    with (out / 'root-observation-J01-v1.jsonl').open('x') as stream:
        while True:
            now = time.time()
            raw = source.read_bytes()
            try:
                value = observation(raw, binding, started, now)
            except (ValueError, KeyError, TypeError) as error:
                value = {'observed_at': now, 'native_session_id': binding['actor_native_id'],
                         'native_prefix_sha256': core.digest(raw), 'observation_error': str(error)}
                stream.write(json.dumps(value) + '\n'); stream.flush()
                print(json.dumps(value), flush=True)
                raise
            stream.write(json.dumps(value) + '\n'); stream.flush()
            print(json.dumps(value), flush=True)
            if value['task_complete'] or value['deadline_reached']:
                return value
            time.sleep(min(10, max(.01, started + 1200 - time.time())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id'); parser.add_argument('agent_path')
    args = parser.parse_args()
    watch(args.run_id, args.agent_path)
