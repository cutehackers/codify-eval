"""Experimental root-owned question protocol; not a qualified comparison runner."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path

from prepare import ROOT, tree_hash
from improvement_boundary_v1 import inspect_repo
from improvement_usage_v4 import snapshot
from collect import find_session, SESSION_ROOT
from improvement_dialogue_native_v4 import READ, SCRIPT, audit, parse, reply_barrier

PROTOCOL = 'question-phases-v3'
HELPERS = ('tools/improvement_dialogue_phase_v4.py', 'tools/improvement_dialogue_io_v4.py',
           'tools/improvement_dialogue_native_v4.py', 'tools/dialogue_schema.py',
           'tools/dialogue_control.py', 'tools/transport.py', 'tools/prepare.py',
           'tools/improvement_boundary_v1.py', 'tools/improvement_usage_v4.py',
           'tools/improvement_usage_v1.py', 'tools/collect.py')


class NativePending(ValueError):
    pass


def bounded_run(args, **kwargs):
    kwargs.setdefault('timeout', 30)
    return subprocess.run(args, **kwargs)


def bounded_output(args, **kwargs):
    kwargs.setdefault('timeout', 30)
    return subprocess.check_output(args, **kwargs)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def directory(run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise ValueError('Invalid run identifier')
    folder = ROOT / 'runtime' / run_id
    if folder.is_symlink() or folder.resolve().parent != (ROOT / 'runtime').resolve():
        raise ValueError('Invalid owned runtime directory')
    return folder


@contextlib.contextmanager
def locked(folder):
    with (folder / 'broker.lock').open('a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def persist(folder, state):
    temporary = folder / 'state.pending'
    with temporary.open('w') as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2)
        stream.flush()
    temporary.replace(folder / 'state.json')


def verify(folder, state):
    config_bytes = (folder / 'configuration.json').read_bytes()
    if sha(config_bytes) != state['configuration_sha256']:
        raise ValueError('Frozen configuration changed')
    config = json.loads(config_bytes)
    if config['model'] != 'gpt-6.1-sol' or config['effort'] != 'medium':
        raise ValueError('Unqualified model')
    if not set(HELPERS).issubset(config['source_hashes']):
        raise ValueError('Missing protocol source pins')
    baseline_name = 'results/improvement-v1/C4-development-freeze-v1.json'
    if baseline_name not in config['source_hashes']:
        raise ValueError('Missing frozen dependency closure')
    baseline = read(ROOT / baseline_name)
    if any(config['source_hashes'].get(name) != digest for name, digest in baseline['source_hashes'].items()):
        raise ValueError('Incomplete or changed transitive dependency pins')
    for name, digest in config['source_hashes'].items():
        path = ROOT / name
        if (name not in baseline['source_hashes'] and not path.resolve().is_relative_to(ROOT)) or sha(path.read_bytes()) != digest:
            raise ValueError('Changed protocol source: ' + name)
    if config['image_id'] != read(ROOT / 'runtime/image.json')['image_id']:
        raise ValueError('Changed evaluation image')
    return config


def inspect_container(folder, state):
    identity = json.loads(bounded_output(['docker', 'inspect', state['container']], text=True))[0]
    if identity['Id'] != state['container_id'] or identity['Image'] != state['image_id'] or identity['HostConfig']['NetworkMode'] != 'none':
        raise ValueError('Container identity/image/network changed')
    labels = identity['Config'].get('Labels', {})
    if labels.get('codify.question.run_id') != state['run_id'] or labels.get('codify.question.configuration') != state['configuration_sha256']:
        raise ValueError('Container ownership labels changed')
    expected = {'/work/repo': (str(folder / 'repo'), state['phase'] == 'implementation'),
                '/eval-input': (str(folder / 'control-inputs'), False)}
    mounts = identity['Mounts']
    if len(mounts) != 2 or {m['Destination'] for m in mounts} != set(expected):
        raise ValueError('Unexpected container mounts')
    for mount in mounts:
        source, writable = expected[mount['Destination']]
        if mount['Type'] != 'bind' or mount['Source'] != source or mount['RW'] != writable:
            raise ValueError('Repository/control mount mismatch')
    return identity


def start_container(folder, state, phase):
    name = 'codify-' + state['run_id'].lower() + '-' + phase.replace('_', '-')
    repo = str(folder / 'repo') + ':/work/repo' + ('' if phase == 'implementation' else ':ro')
    existing = bounded_run(['docker', 'inspect', name], capture_output=True)
    if existing.returncode == 0:
        raise ValueError('Container name already exists; preserve unrelated or prior resource')
    state.setdefault('allocated_containers', []).append({'name': name, 'id': None, 'phase': phase, 'status': 'creation_intent'})
    persist(folder, state)
    bounded_run(['docker', 'run', '-d', '--name', name, '--network', 'none',
                    '--label', 'codify.question.run_id=' + state['run_id'],
                    '--label', 'codify.question.configuration=' + state['configuration_sha256'],
                    '-v', repo, '-v', str(folder / 'control-inputs') + ':/eval-input:ro',
                    '-w', '/work/repo', state['image_id'], 'sleep', 'infinity'], check=True, capture_output=True)
    identity = json.loads(bounded_output(['docker', 'inspect', name], text=True))[0]
    state.update(container=name, container_id=identity['Id'], phase=phase)
    inspect_container(folder, state)
    state['allocated_containers'][-1].update(id=identity['Id'], status='created')
    persist(folder, state)


def stop_container(folder, state):
    before = inspect_container(folder, state)
    if before['State']['Running']:
        bounded_run(['docker', 'stop', '-t', '2', state['container']], check=True, capture_output=True)
    after = inspect_container(folder, state)
    if after['State']['Running']:
        raise ValueError('Container still running')
    prefix = folder / ('container-' + state['phase'])
    save(str(prefix) + '-identity.json', {'before': before, 'after': after})
    with Path(str(prefix) + '-diff.txt').open('x') as stream:
        bounded_run(['docker', 'diff', state['container']], check=True, stdout=stream, text=True)
    # Preserve actual writable scratch diagnostics before disposing the phase.
    with Path(str(prefix) + '-tmp.tar').open('xb') as stream:
        bounded_run(['docker', 'cp', state['container'] + ':/tmp', '-'], check=True, stdout=stream, stderr=subprocess.PIPE)
    bounded_run(['docker', 'rm', state['container']], check=True, capture_output=True)


def _create(configuration):
    raw = Path(configuration).read_bytes()
    config = json.loads(raw)
    folder = directory(config['run_id'])
    folder.mkdir()
    (folder / 'configuration.json').write_bytes(raw)
    state = {'protocol': PROTOCOL, 'run_id': config['run_id'], 'image_id': config['image_id'],
             'configuration_sha256': sha(raw), 'phase': 'preparing', 'started_at': time.time(),
             'time_limit_seconds': config['time_limit_seconds'], 'agent_path': None, 'allocated_containers': []}
    persist(folder, state)
    config = verify(folder, state)
    source = ROOT / config['source_repo']
    inspect_repo(source)
    if tree_hash(source) != config['source_repo_sha256']:
        raise ValueError('Frozen starting repository changed')
    if not config['slots'] or len(set(config['slots'])) != len(config['slots']):
        raise ValueError('Missing or duplicate required decision slots')
    task = (ROOT / config['task_path']).read_bytes()
    reply = (ROOT / config['reply_path']).read_bytes()
    if sha(task) != config['task_sha256'] or sha(reply) != config['reply_sha256'] or not reply or b'\r' in reply:
        raise ValueError('Frozen task/reply changed or unsupported')
    shutil.copytree(source, folder / 'repo')
    (folder / 'control-inputs').mkdir()
    state['initial_repo_sha256'] = tree_hash(folder / 'repo')
    controls = f'''You own one isolated software task. All repository operations must use this container command interface through tools.exec_command:
python3 {ROOT}/tools/{SCRIPT} --run {state['run_id']} --cmd '<shell command inside the container>'
The working directory is /work/repo. Use only the supplied task/repository/skill resources. The sole initial request is the only permitted host read. Do not read host scripts, command-interface source, other runs or oracle/reference files. Do not use other tools/connectors or agents. Do not inspect the transport implementation. No commits. Network is disabled. Flutter, Dart, Python and git are installed. Resolve dependencies with flutter pub get --offline.
For a missing consequential product decision, ask the concrete question in your FINAL response and end the turn. Do not invent a policy or use messaging, request-input, sleep or wait tools. The evaluator supplies the fixed human answer in this same session. The repository remains read-only until that answer has been received through the prescribed file read. Writable scratch is available outside /work/repo. Implementation writes are allowed only after that read has an actual native receipt.
Use only a standalone text(await tools.exec_command(...)) call or the literal-template escaping form supported by this interface. If exec returns a session_id, poll only that exact session with one standalone text(await tools.write_stdin(...)) call, with empty or omitted chars. Keep the requested outcome and reply in Korean with actual verification evidence. Do not disclose private reasoning.
'''
    # The selected skill is provided by the frozen input repository, not evaluator metadata.
    if (folder / 'repo/.agents/skills/codify/SKILL.md').exists():
        controls += 'Use the provided /work/repo/.agents/skills/codify/SKILL.md and its relevant references.\n'
    request = controls + '\nUSER TASK\n' + task.decode('utf-8')
    (folder / 'request.txt').write_text(request)
    state['prompt_sha256'] = sha(request.encode())
    command = 'cat ' + shlex.quote(str(folder / 'request.txt'))
    state['bootstrap_code'] = 'text(await tools.exec_command(' + json.dumps({'cmd': command, 'max_output_tokens': 6500}) + '));'
    start_container(folder, state, 'question')
    return {'run_id': state['run_id'], 'bootstrap_code': state['bootstrap_code']}


def bind_actor(run_id, agent_path):
    folder = directory(run_id)
    with locked(folder):
        state = read(folder / 'state.json')
        verify(folder, state)
        if state['phase'] != 'question' or state['agent_path'] is not None:
            raise ValueError('Preserve first actor allocation')
        source = find_session(agent_path)
        raw = source.read_bytes()
        usage = snapshot(raw, agent_path, str(source))
        state.update(agent_path=agent_path, actor_native_id=usage['native_session_id'], actor_source=str(source))
        persist(folder, state)
        save(folder / 'actor-start-proof.json', usage)
        return usage


def _seal_question(run_id):
    folder = directory(run_id)
    with locked(folder):
        state = read(folder / 'state.json')
        verify(folder, state)
        if state['phase'] != 'question':
            raise ValueError('Question already sealed or wrong phase')
        raw = Path(state['actor_source']).read_bytes()
        events = parse(raw)
        cost = snapshot(raw, state['agent_path'], state['actor_source'])
        if cost['native_session_id'] != state['actor_native_id']:
            raise ValueError('Native actor identity changed')
        if not cost['native_completion_observed'] or len(cost['completions']) != 1 or len(cost['models']) != 1:
            raise NativePending('Observe same actor until actual first turn completes')
        if audit(events, state, str(ROOT)):
            raise ValueError('Question transport boundary violated')
        stop_container(folder, state)
        if tree_hash(folder / 'repo') != state['initial_repo_sha256']:
            raise ValueError('Repository changed before answer')
        finals = [e['payload'] for e in events if e.get('payload', {}).get('type') == 'message' and e['payload'].get('role') == 'assistant' and (e['payload'].get('channel') == 'final' or e['payload'].get('phase') == 'final_answer')]
        if len(finals) != 1:
            raise ValueError('Expected one native first final')
        question = '\n'.join(c.get('text', '') for c in finals[0].get('content', []) if c.get('type') == 'output_text')
        (folder / 'first-native.jsonl').write_bytes(raw)
        commands = (folder / 'commands.jsonl').read_bytes() if (folder / 'commands.jsonl').exists() else b''
        starts = (folder / 'command-starts.jsonl').read_bytes() if (folder / 'command-starts.jsonl').exists() else b''
        proof = {'first_native_bytes': len(raw), 'first_native_sha256': sha(raw), 'question': question,
                 'question_sha256': sha(question.encode()), 'usage': cost, 'repository_read_only': True}
        proof.update(commands_bytes=len(commands), commands_sha256=sha(commands), command_starts_bytes=len(starts), command_starts_sha256=sha(starts),
                     container_identity_sha256=sha((folder / 'container-question-identity.json').read_bytes()))
        save(folder / 'first-question.json', proof)
        state['phase'] = 'question_sealed'
        persist(folder, state)
        return proof


def _stage(run_id, semantic_review):
    folder = directory(run_id)
    with locked(folder):
        state = read(folder / 'state.json')
        config = verify(folder, state)
        first = read(folder / 'first-question.json')
        review_raw = Path(semantic_review).read_bytes()
        review = json.loads(review_raw)
        covered = review.get('covered_slot_ids')
        if not isinstance(covered, list) or any(not isinstance(slot, str) for slot in covered) or len(covered) != len(set(covered)):
            raise ValueError('Malformed independent slot coverage')
        if state['phase'] != 'question_sealed' or review.get('verdict') != 'pass' or review.get('question_sha256') != first['question_sha256'] or review.get('first_native_sha256') != first['first_native_sha256'] or set(review.get('covered_slot_ids', [])) != set(config['slots']):
            raise ValueError('All required human choices must be independently qualified')
        current = Path(state['actor_source']).read_bytes()
        if sha(current[:first['first_native_bytes']]) != first['first_native_sha256']:
            raise ValueError('Preserved first native prefix changed')
        observed = snapshot(current, state['agent_path'], state['actor_source'])
        if not observed['native_completion_observed'] or len(observed['models']) != 1 or len(observed['completions']) != 1:
            raise ValueError('Actor was continued before qualified staging')
        for filename, length, digest in [('commands.jsonl', first['commands_bytes'], first['commands_sha256']),
                                         ('command-starts.jsonl', first['command_starts_bytes'], first['command_starts_sha256'])]:
            content = (folder / filename).read_bytes() if (folder / filename).exists() else b''
            if len(content) != length or sha(content) != digest:
                raise ValueError('First-phase command journal changed before staging')
        if any((folder / 'control-inputs').iterdir()):
            raise ValueError('Control input was already exposed')
        reply = (ROOT / config['reply_path']).read_bytes()
        if sha(reply) != config['reply_sha256']:
            raise ValueError('Reply changed')
        path = folder / 'control-inputs/turn-2.txt'
        with path.open('xb') as stream:
            stream.write(reply)
        path.chmod(0o444)
        start_container(folder, state, 'reply_read')
        command = shlex.join(['python3', str(ROOT / 'tools' / SCRIPT), '--run', run_id, '--cmd', READ])
        followup = 'The next user request is in /eval-input/turn-2.txt. Read it through the exact permitted call below and follow its full contents in this same session. No new host read.\n'
        followup += 'text(await tools.exec_command(' + json.dumps({'cmd': command, 'max_output_tokens': 2000}) + '));'
        proof = {**{k: first[k] for k in ('first_native_bytes', 'first_native_sha256', 'question_sha256')},
                 'staged_at': time.time(), 'reply_utf8': reply.decode('utf-8'), 'reply_sha256': sha(reply),
                 'semantic_review_sha256': sha(review_raw), 'semantic_review_path': str(Path(semantic_review).resolve()),
                 'followup': followup, 'reply_container_id': state['container_id']}
        save(folder / 'reply-stage.json', proof)
        return followup


def _close(run_id):
    """Seal an actual terminal session and remove only owned phase containers."""
    folder = directory(run_id)
    with locked(folder):
        state = read(folder / 'state.json')
        verify(folder, state)
        if (folder / 'final-proof.json').exists():
            raise ValueError('Preserve first terminal collection')
        raw = Path(state['actor_source']).read_bytes()
        cost = snapshot(raw, state['agent_path'], state['actor_source'])
        if not cost['native_completion_observed']:
            raise NativePending('Observe same actual actor until terminal; do not restart')
        violations = audit(parse(raw), state, str(ROOT))
        try:
            if state['phase'] in {'question', 'reply_read', 'implementation'}:
                stop_container(folder, state)
            inspect_repo(folder / 'repo')
            proof = {'protocol': PROTOCOL, 'status': 'evaluation_error' if violations else 'collected_not_graded',
                     'transport_violations': violations, 'usage': cost, 'repo_sha256': tree_hash(folder / 'repo'),
                     'native_source_bytes': len(raw), 'native_source_sha256': sha(raw),
                     'complete_allocation_accounting': False, 'semantic_and_behavior_grading_complete': False}
            (folder / 'final-native.jsonl').write_bytes(raw)
            save(folder / 'final-proof.json', proof)
            state['phase'] = 'closed'
            persist(folder, state)
            return proof
        finally:
            cleanup_owned(folder, state)


def cleanup_owned(folder, state):
    receipts = []
    for row in state['allocated_containers']:
        result = bounded_run(['docker', 'inspect', row['name']], capture_output=True, text=True)
        if result.returncode != 0:
            listing = bounded_run(['docker', 'ps', '-a', '--format', '{{.Names}}'], check=True, capture_output=True, text=True)
            if row['name'] in listing.stdout.splitlines():
                raise ValueError('Present container cannot be inspected; cleanup unverified')
            receipts.append({'name': row['name'], 'absence_verified_by_healthy_inventory': True})
            continue
        identity = json.loads(result.stdout)[0]
        labels = identity['Config'].get('Labels', {})
        if labels.get('codify.question.run_id') != state['run_id'] or labels.get('codify.question.configuration') != state['configuration_sha256'] or row.get('id') not in {None, identity['Id']}:
            raise ValueError('Refuse cleanup of an unowned container')
        bounded_run(['docker', 'rm', '-f', row['name']], check=True, capture_output=True)
        receipts.append({'name': row['name'], 'id': identity['Id'], 'removed': True})
    path = folder / 'cleanup-receipt.json'
    if not path.exists():
        save(path, receipts)


def unlock(folder, state):
    staged = read(folder / 'reply-stage.json')
    if sha((folder / 'control-inputs/turn-2.txt').read_bytes()) != staged['reply_sha256']:
        raise ValueError('Controlled reply changed')
    actor = Path(state['actor_source']).read_bytes()
    header = parse(actor)[0]['payload']
    sources = list(SESSION_ROOT.rglob('*-' + header['parent_thread_id'] + '.jsonl'))
    if len(sources) != 1:
        raise ValueError('Ambiguous parent native source')
    parent = sources[0].read_bytes()
    records = [json.loads(line) for line in (folder / 'commands.jsonl').read_text().splitlines()]
    proof = reply_barrier(actor, parent, state, staged, records, str(ROOT))
    save(folder / 'reply-read-native-proof.json', proof)
    save(folder / 'implementation-transition-intent.json', {'from_container_id': state['container_id'],
                                                           'native_read_proof_sha256': sha((folder / 'reply-read-native-proof.json').read_bytes()),
                                                           'started_at': time.time()})
    stop_container(folder, state)
    start_container(folder, state, 'implementation')
    return proof



def abort_locked(folder, state, reason):
    """Stop owned filesystems even without normal model completion.

    The root must interrupt the same actor through the runtime and then resample.
    This function never invents actor termination or complete final token usage.
    """
    first = folder / 'first-failure.json'
    if not first.exists():
        save(first, {'reason': str(reason), 'observed_at': time.time(),
                     'phase': state['phase'], 'actor_agent_path': state.get('agent_path')})
    state['phase'] = 'aborted'
    state['actor_interrupt_pending'] = bool(state.get('agent_path'))
    persist(folder, state)
    receipt = {'reason': str(reason), 'actor_interrupt_pending': state['actor_interrupt_pending'],
               'usage': None, 'usage_unavailable': None, 'complete_final_cost': False,
               'containers': [], 'cleanup_verified': True}
    try:
        source = Path(state['actor_source'])
        raw = source.read_bytes()
        receipt['usage'] = snapshot(raw, state['agent_path'], str(source))
        # Normal completion can establish model idleness, never the absence of future followups.
        receipt['actor_interrupt_pending'] = not receipt['usage']['native_completion_observed']
        state['actor_interrupt_pending'] = receipt['actor_interrupt_pending']
    except (KeyError, ValueError, OSError) as error:
        receipt['usage_unavailable'] = str(error)
    for row in state['allocated_containers']:
        item = {'name': row['name']}
        try:
            result = bounded_run(['docker', 'inspect', row['name']], capture_output=True, text=True)
            if result.returncode != 0:
                listing = bounded_run(['docker', 'ps', '-a', '--format', '{{.Names}}'], check=True, capture_output=True, text=True)
                if row['name'] in listing.stdout.splitlines():
                    raise ValueError('Inspect failed for a present resource')
                item['absence_verified_by_healthy_inventory'] = True
                receipt['containers'].append(item)
                continue
            identity = json.loads(result.stdout)[0]
            labels = identity['Config'].get('Labels', {})
            if labels.get('codify.question.run_id') != state['run_id'] or labels.get('codify.question.configuration') != state['configuration_sha256'] or row.get('id') not in {None, identity['Id']}:
                raise ValueError('Refuse finalization of unowned resource')
            item['identity_before'] = identity
            bounded_run(['docker', 'stop', '-t', '2', row['name']], check=True, capture_output=True)
            stopped = json.loads(bounded_output(['docker', 'inspect', row['name']], text=True))[0]
            if stopped['State']['Running']:
                raise ValueError('Owned filesystem still running')
            item['identity_stopped'] = stopped
            try:
                item['docker_diff'] = bounded_output(['docker', 'diff', row['name']], text=True)
                archive = folder / ('abort-' + row['phase'] + '-tmp.tar')
                if not archive.exists():
                    with archive.open('xb') as stream:
                        bounded_run(['docker', 'cp', row['name'] + ':/tmp', '-'], check=True, stdout=stream, stderr=subprocess.PIPE)
                item['archive_path'] = str(archive)
                item['archive_sha256'] = sha(archive.read_bytes())
            except (OSError, subprocess.SubprocessError) as error:
                item['diagnostic_error'] = str(error)
            bounded_run(['docker', 'rm', row['name']], check=True, capture_output=True)
            item['removed'] = True
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            item['finalization_error'] = str(error)
            receipt['cleanup_verified'] = False
        receipt['containers'].append(item)
    persist(folder, state)
    samples = list(folder.glob('abort-sample-*.json'))
    save(folder / ('abort-sample-' + str(len(samples) + 1) + '.json'), receipt)
    return receipt


def abort(run_id, reason):
    folder = directory(run_id)
    with locked(folder):
        return abort_locked(folder, read(folder / 'state.json'), reason)


def create(configuration):
    config = read(configuration)
    folder = directory(config['run_id'])
    existed = folder.exists()
    try:
        return _create(configuration)
    except Exception as error:
        if not existed and (folder / 'state.json').exists():
            abort(config['run_id'], error)
        raise


def managed(run_id, action):
    try:
        return action()
    except NativePending:
        raise  # A pending observation never interrupts or restarts the actual actor.
    except Exception as error:
        abort(run_id, error)
        raise


def seal_question(run_id):
    return managed(run_id, lambda: _seal_question(run_id))


def stage(run_id, semantic_review):
    return managed(run_id, lambda: _stage(run_id, semantic_review))


def close(run_id):
    return managed(run_id, lambda: _close(run_id))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('create'); p.add_argument('configuration')
    p = sub.add_parser('bind'); p.add_argument('run'); p.add_argument('agent_path')
    p = sub.add_parser('seal-question'); p.add_argument('run')
    p = sub.add_parser('stage'); p.add_argument('run'); p.add_argument('review')
    p = sub.add_parser('close'); p.add_argument('run')
    p = sub.add_parser('abort'); p.add_argument('run'); p.add_argument('reason')
    args = parser.parse_args()
    result = create(args.configuration) if args.action == 'create' else bind_actor(args.run, args.agent_path) if args.action == 'bind' else seal_question(args.run) if args.action == 'seal-question' else stage(args.run, args.review) if args.action == 'stage' else close(args.run) if args.action == 'close' else abort(args.run, args.reason)
    print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))
