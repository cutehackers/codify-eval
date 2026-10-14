"""Read-only optional root/member native observation on the original clock.

The coordinator starts this process before native root allocation. Registry
reservations remain cumulative, including unknown/failed native dispatches.
This service cannot terminate actors, close deliveries, authorize cleanup,
compute final costs or qualify a comparison. Final native joins are separate.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import re
import time

from collect import find_session
import improvement_optional_registry_v4 as registry
import improvement_optional_inventory_v3 as strict
import improvement_q01_dialogue_core_v1 as core
from improvement_software_artifacts_v3 import atomic_json

LIMIT = 256 * 1024 * 1024
ROOT = Path(__file__).resolve().parents[1]
require = core.require


def native_bytes(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size <= LIMIT,
                'Bounded original native regular file required')
        raw = os.read(fd, before.st_size + 1)
        # A growing source is normal. Only retain the bytes actually read, not
        # a fabricated complete prefix or a replacement inode/truncated source.
        after = os.fstat(fd)
        require(before.st_ino == after.st_ino and after.st_size >= len(raw)
                and len(raw) <= LIMIT, 'Native source replaced or truncated')
        return raw
    finally:
        os.close(fd)


def sample(raw, path, parent_id, previous=b'', expected_turns=1):
    require(isinstance(raw, bytes) and isinstance(previous, bytes) and raw.startswith(previous),
            'Native source is not append-consistent')
    require(type(expected_turns) is int and expected_turns == 1,
            'This optional control observer supports exactly one approved turn')
    require(isinstance(path, str) and re.fullmatch('/root/[A-Za-z0-9_]+(?:/worker[12])?',path) and isinstance(parent_id,str) and parent_id,
            'Registered path and original parent identity required')
    newline = raw.rfind(b'\n'); require(newline >= 0, 'Native header not complete yet')
    prefix = raw[:newline + 1]
    events = core.parse(prefix); strict.finite(events)
    headers = [e['payload'] for e in events if e['type'] == 'session_meta']
    require(len(headers) == 1 and events[0]['type'] == 'session_meta', 'Ambiguous native header')
    header = headers[0]; spawn = header.get('source',{}).get('subagent',{}).get('thread_spawn',{})
    require(isinstance(header.get('id'),str) and header['id'] and header.get('agent_path') == path
            and header.get('parent_thread_id') == parent_id and spawn.get('parent_thread_id') == parent_id
            and spawn.get('agent_path') == path, 'Native source path/parent changed')
    contexts = [e['payload'] for e in events if e['type'] == 'turn_context']
    require(len(contexts) <= expected_turns, 'Unapproved extra native turn')
    for context in contexts:
        require(context.get('model') == 'gpt-6.1-sol' and context.get('effort') == 'medium',
                'Actual model or reasoning changed')
        settings = context.get('collaboration_mode',{}).get('settings')
        require(settings is None or settings.get('model') == 'gpt-6.1-sol'
                and settings.get('reasoning_effort') == 'medium', 'Actual collaboration settings changed')
    ends = [e for e in events if e['type'] == 'event_msg' and e['payload'].get('type') == 'task_complete']
    require(len(ends) <= expected_turns, 'Repeated or extra native completion')
    complete = prefix == raw
    terminal = bool(ends) and complete
    if ends:
        # Validate incoming turn, final response and original completion, even
        # when an incomplete trailing append keeps terminality unproven.
        core.lifecycle(prefix, {'actor_native_id':header['id'], 'agent_path':path,
                                'parent_native_id':parent_id}, expected_turns)
    return {'agent_path':path,'native_session_id':header['id'],'parent_native_id':parent_id,
            'raw_bytes':len(raw),'raw_sha256':core.digest(raw),'complete_native_bytes':len(prefix),
            'complete_native_sha256':core.digest(prefix),'raw_prefix_complete':complete,
            'first_timestamp':events[0]['timestamp'],'last_timestamp':events[-1]['timestamp'],
            'contexts':len(contexts),'completed_turns':len(ends),'normal_completion_observed':terminal,
            'completion_at':ends[-1]['timestamp'] if ends else None,
            'native_qualified':False,'cleanup_authorized':False}


def supervise(folder, root_path, parent_id):
    folder = Path(folder).resolve(); require(folder.parent == ROOT/'runtime','Owned runtime namespace required')
    require(isinstance(root_path,str) and re.fullmatch('/root/[A-Za-z0-9_]+',root_path),'Immediate root actor path required')
    config = strict.decoded((folder/'registry/configuration.json').read_bytes())
    original = config['started_at']; deadline = config['deadline']; now = time.time()
    require(type(original) in (int,float) and math.isfinite(original) and deadline == original+1200
            and original <= now < deadline,'Original observer clock required')
    out = folder/'native-observer'; out.mkdir()
    atomic_json(out/'ready.json',{'started_at':now,'original_started_at':original,'deadline':deadline,
        'root_path':root_path,'parent_id':parent_id,'observer_restarts':0,'actor_control':False},exclusive=True)
    sources = {}; previous = {}; last_completed = now; root_identity = None
    with (out/'samples.jsonl').open('x') as stream:
        while True:
            began = time.time(); require(0 <= began-last_completed <= 30,'Observer cadence exceeded30s')
            state = registry.read(folder/'registry')
            require(registry.encoded(state['configuration']) == registry.encoded(config),'Observer configuration changed')
            jobs = ['root']+list(state['workers']); members = []; pending = []
            for job in jobs:
                path = root_path if job == 'root' else root_path+'/'+job
                if path not in sources:
                    try: sources[path] = find_session(path)
                    except ValueError as error:
                        if not str(error).endswith('found 0'): raise
                        pending.append(job); continue
                raw = native_bytes(sources[path])
                expected_parent = parent_id if job == 'root' else root_identity
                require(expected_parent is not None,'Worker source before original root identity')
                value = sample(raw,path,expected_parent,previous.get(path,b''))
                previous[path] = raw; members.append(value)
                if job == 'root':root_identity = value['native_session_id']
            finished = time.time(); require(began <= finished and 0 <= finished-last_completed <= 30,
                                           'Observer completed sample cadence exceeded30s')
            require(len({m['native_session_id'] for m in members}) == len(members),'Native UUID reused across actors')
            require(all(original <= core.instant(m['first_timestamp']).timestamp()
                        <= core.instant(m['last_timestamp']).timestamp() <= finished for m in members),
                    'Native sample outside original observed clock')
            value = {'started_at':began,'completed_at':finished,'registry_head_sha256':state['head_sha256'],
                'reserved_jobs':jobs,'members':members,'pending_native_jobs':pending,
                'all_registered_normal_completions_observed':not pending and all(m['normal_completion_observed'] for m in members),
                'deadline_reached':finished >= deadline,'native_qualified':False,'cleanup_authorized':False}
            stream.write(json.dumps(value,allow_nan=False)+'\n');stream.flush()
            print(json.dumps({'sample_completed_at':finished,'reserved':len(jobs),'pending':pending,
                'normal_completions':sum(m['normal_completion_observed'] for m in members)}),flush=True)
            last_completed = finished
            # Normal completion does not stop observation: preserve all sources
            # through coordinator-controlled closure or the original deadline.
            closure = out/'stop.json'
            if closure.exists():
                stop = strict.decoded(closure.read_bytes())
                require(stop == {'reason':'coordinator_stop','root_path':root_path,'parent_id':parent_id},
                        'Exact coordinator stop intent required')
                atomic_json(out/'terminal.json',{'reason':'coordinator_stop','finished_at':finished,
                    'last_sample_sha256':registry.sha(value),'normal_completions_observed':value['all_registered_normal_completions_observed'],
                    'native_qualified':False,'cleanup_authorized':False},exclusive=True)
                return value
            if finished >= deadline:
                atomic_json(out/'terminal.json',{'reason':'original_deadline','finished_at':finished,
                    'last_sample_sha256':registry.sha(value),'native_qualified':False,'cleanup_authorized':False},exclusive=True)
                return value
            time.sleep(min(5,max(.01,deadline-time.time())))


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run');parser.add_argument('root_path');parser.add_argument('parent_id')
    args=parser.parse_args();supervise(ROOT/'runtime'/args.run,args.root_path,args.parent_id)
