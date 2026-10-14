"""One-shot Q03 software grade after independently sealed same-session dialogue.

Protocol qualification and software outcomes remain separate. No native actor
is restarted and no original grade is overwritten.
"""
import argparse
import fnmatch
import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import improvement_dialogue_phase_v6 as phases
import improvement_software_broker_v7 as diagnostics
from improvement_boundary_v1 import inspect_repo
from improvement_qualify_v1 import digest_tree
from improvement_usage_v4 import snapshot
from prepare import tree_hash

ROOT = phases.ROOT
CASE = ROOT / 'improvement_cases/confirmatory/Q03'


def execute(args, timeout=30):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def grade(run_id):
    folder = phases.directory(run_id)
    state = phases.read(folder / 'state.json')
    config = phases.verify(folder, state)
    assert config['source_repo'] == str(CASE.relative_to(ROOT) / 'repo')
    assert state['phase'] == 'closed'
    proof = phases.read(folder / 'final-proof.json')
    assert proof['status'] == 'collected_not_graded' and not proof['transport_violations']
    raw = (folder / 'final-native.jsonl').read_bytes()
    assert phases.sha(raw) == proof['native_source_sha256'] and len(raw) == proof['native_source_bytes']
    usage = snapshot(raw, state['agent_path'], state['actor_source'])
    assert usage['native_completion_observed'] and len(usage['completions']) == 2
    assert usage['native_session_id'] == state['actor_native_id']
    first = phases.read(folder / 'first-question.json')
    staged = phases.read(folder / 'reply-stage.json')
    review_path = Path(staged['semantic_review_path'])
    review = phases.read(review_path)
    assert phases.sha(review_path.read_bytes()) == staged['semantic_review_sha256']
    assert review['verdict'] == 'pass' and set(review['covered_slot_ids']) == set(config['slots'])
    assert review['question_sha256'] == first['question_sha256']
    assert review['first_native_sha256'] == first['first_native_sha256']
    assert phases.sha((folder / 'control-inputs/turn-2.txt').read_bytes()) == config['reply_sha256'] == staged['reply_sha256']
    transition = phases.read(folder / 'implementation-transition-intent.json')
    assert transition['native_read_proof_sha256'] == phases.sha((folder / 'reply-read-native-proof.json').read_bytes())
    read_proof = phases.read(folder / 'reply-read-native-proof.json')
    assert phases.sha(raw[:first['first_native_bytes']]) == first['first_native_sha256']
    assert phases.sha(raw[:read_proof['actor_native_prefix_bytes']]) == read_proof['actor_native_prefix_sha256']
    header = phases.parse(raw)[0]['payload']
    parents = list(phases.SESSION_ROOT.rglob('*-' + header['parent_thread_id'] + '.jsonl'))
    assert len(parents) == 1
    parent = parents[0].read_bytes()[:read_proof['parent_native_prefix_bytes']]
    assert phases.sha(parent) == read_proof['parent_native_prefix_sha256']
    commands = [json.loads(line) for line in (folder / 'commands.jsonl').read_text().splitlines()]
    checked_barrier = phases.reply_barrier(raw, parent, state, staged, commands, str(ROOT))
    assert checked_barrier['read_receipt_call_id'] == read_proof['read_receipt_call_id']
    assert checked_barrier['followup_call_id'] == read_proof['followup_call_id']
    receipt_event = next(event for event in phases.parse(raw)
                         if event.get('payload', {}).get('call_id') == read_proof['read_receipt_call_id']
                         and event['payload'].get('type') in {'function_call_output', 'custom_tool_call_output'})
    import datetime
    received_at = datetime.datetime.fromisoformat(receipt_event['timestamp'].replace('Z', '+00:00')).timestamp()
    assert transition['started_at'] >= received_at
    starts = [json.loads(line) for line in (folder / 'command-starts.jsonl').read_text().splitlines()]
    for command in starts:
        if command['phase'] == 'implementation':
            assert datetime.datetime.fromisoformat(command['time']).timestamp() >= transition['started_at']
    inspect_repo(folder / 'repo')
    assert tree_hash(folder / 'repo') == proof['repo_sha256']
    actual, original = digest_tree(folder / 'repo'), digest_tree(CASE / 'repo')
    metadata = phases.read(CASE / 'metadata.json')
    changed = sorted(name for name in set(actual) | set(original) if actual.get(name) != original.get(name))
    invalid = [name for name in changed if not any(fnmatch.fnmatch(name, pattern) for pattern in metadata['allowed_paths'])]
    protected = [name for name in changed if any(fnmatch.fnmatch(name, pattern) for pattern in metadata['protected_paths'])]
    out = ROOT / 'results' / run_id
    out.mkdir(exist_ok=True)
    destination = ROOT / 'runtime/question-grading-v3' / run_id
    assert not destination.exists() and not (out / 'grade.json').exists(), 'Preserve original attempt'
    owner = uuid.uuid4().hex
    name = 'grade-question-' + owner
    receipt = {'run_id': run_id, 'status': 'running', 'behavior_pass': None, 'scope_pass': not invalid and not protected,
               'report_pass': None, 'overall_pass': None, 'changed': changed, 'out_of_scope': invalid,
               'protected_changes': protected, 'usage': usage, 'checks': [], 'owner': owner,
               'question_protocol_seal_sha256': phases.sha((folder / 'final-proof.json').read_bytes()),
               'grading_helper_sha256': phases.sha(Path(__file__).read_bytes()), 'superiority_proven': False,
               'complete_final_cost': False, 'primary_confirmation_reuse_allowed': False, 'lifecycle_errors': []}
    save = lambda: diagnostics.artifacts.atomic_json(out / 'grade.json', receipt)
    diagnostics.artifacts.atomic_json(out / 'grade.json', receipt, exclusive=True)
    try:
        assert shutil.disk_usage(ROOT).free >= 3 * 1024**3
        shutil.copytree(folder / 'repo', destination, ignore=shutil.ignore_patterns('.git', '.dart_tool', 'build', '__pycache__', '.agents'))
        shutil.copytree(CASE / 'oracle/test', destination / 'test', dirs_exist_ok=True)
        inspect_repo(destination)
        created = execute(['docker', 'create', '--name', name, '--network', 'none', '--label', 'codify.eval.owner=' + owner,
                          '-v', str(destination) + ':/work/repo', '-w', '/work/repo', config['image_id'], 'sleep', 'infinity'], 60)
        created.check_returncode()
        identity = json.loads(execute(['docker', 'inspect', name]).stdout)[0]
        assert identity['Image'] == config['image_id'] and identity['HostConfig']['NetworkMode'] == 'none'
        assert len(identity['Mounts']) == 1 and identity['Mounts'][0]['Source'] == str(destination)
        phases.save(out / 'grader-container-identity.json', identity)
        execute(['docker', 'start', name], 60).check_returncode()
        for command in ['flutter pub get --offline', 'flutter test --no-pub --machine', 'flutter analyze --no-pub']:
            started = time.monotonic()
            result = execute(['docker', 'exec', name, 'timeout', '--kill-after=5s', '180s', 'bash', '-lc', command], 190)
            receipt['checks'].append({'command': command, 'exit_code': result.returncode, 'output': result.stdout + result.stderr,
                                      'elapsed_seconds': time.monotonic() - started})
            save()
        receipt.update(status='review_pending', behavior_pass=all(check['exit_code'] == 0 for check in receipt['checks']))
    except Exception as error:
        receipt.update(status='evaluation_error', first_error={'type': type(error).__name__, 'message': str(error)})
    finally:
        try:
            found = execute(['docker', 'inspect', name])
            if found.returncode == 0:
                identity = json.loads(found.stdout)[0]
                assert identity['Config']['Labels'].get('codify.eval.owner') == owner and identity['Image'] == config['image_id']
                assert len(identity['Mounts']) == 1 and identity['Mounts'][0]['Source'] == str(destination)
                try:
                    stopped = execute(['docker', 'stop', '-t', '2', name], 10)
                    if stopped.returncode:
                        receipt['stop_error'] = {'exit_code': stopped.returncode, 'stderr': stopped.stderr}
                except subprocess.TimeoutExpired as error:
                    receipt['stop_error'] = {'type': type(error).__name__, 'message': str(error)}
                save()
                after = json.loads(execute(['docker', 'inspect', name]).stdout)[0]
                if after['State']['Running']:
                    execute(['docker', 'kill', name], 10).check_returncode()
                    after = json.loads(execute(['docker', 'inspect', name]).stdout)[0]
                assert not after['State']['Running']
                diagnostics.preserve_tmp(out, name, 'grader')
                execute(['docker', 'rm', name], 30).check_returncode()
                receipt['owned_grader_removed'] = True
            elif 'No such object' not in found.stderr:
                raise ValueError(found.stderr)
        except Exception as error:
            receipt['lifecycle_errors'].append({'type': type(error).__name__, 'message': str(error)})
            receipt['status'] = 'evaluation_error'
        try:
            assert digest_tree(folder / 'repo') == actual, 'Actor artifact changed during grading'
        except Exception as error:
            observed_error = {'type': type(error).__name__, 'message': str(error)}
            receipt.setdefault('first_error', observed_error)
            receipt['lifecycle_errors'].append(observed_error)
            receipt['status'] = 'evaluation_error'
        save()
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    result = grade(parser.parse_args().run_id)
    print(json.dumps({key: value for key, value in result.items() if key not in {'checks', 'usage'}}, ensure_ascii=False))
