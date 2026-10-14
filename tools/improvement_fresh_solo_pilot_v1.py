"""Fresh solo pilot adapter over the qualified native collection/lifecycle tools."""
import argparse
import ast
import json
import os
import stat
from pathlib import Path
import shutil
import subprocess
import time

import improvement_p03_pilot_v1 as legacy
import improvement_composed_quote_collect_v7 as collector
import improvement_fresh_pilot_qualification_v1 as qualification
from improvement_q04_verifier_v5 import COMMANDS, IMAGE, verify
from improvement_software_artifacts_v3 import atomic_json

ROOT = legacy.ROOT
PHASE = 'control-probe-fresh-solo-v1'
PLAN = ROOT / 'results/improvement-v1/fresh-solo-pilot-v1-allocation-plan-v1.json'
FREEZE = ROOT / 'results/improvement-v1/fresh-solo-pilot-v1-freeze-v1.json'
REVIEW = ROOT / 'results/improvement-v1/fresh-solo-pilot-v1-prelaunch-review-v2.json'
QUALITY = ROOT / 'results/improvement-v1/fresh-pilot-v2-semantic-review-v1.json'
SUMMARY = ROOT / 'results/improvement-v1/fresh-pilot-v2-qualification/summary-v1.json'


def protected_tree(repo):
    """Include owned entities and modes; omit only registered generated trees."""
    repo = Path(repo)
    ignored = {'.git', '.dart_tool', 'build', '__pycache__'}
    result = {'.': {'kind': 'directory', 'mode': stat.S_IMODE(repo.lstat().st_mode)}}
    assert stat.S_ISDIR(repo.lstat().st_mode)
    for parent, directories, files in os.walk(repo, followlinks=False):
        directories[:] = [name for name in directories if name not in ignored]
        for name in directories + files:
            path = Path(parent) / name
            mode = path.lstat().st_mode
            assert stat.S_ISDIR(mode) or stat.S_ISREG(mode), 'Nonregular protected entity'
            entry = {'kind': 'directory' if stat.S_ISDIR(mode) else 'file',
                     'mode': stat.S_IMODE(mode)}
            if stat.S_ISREG(mode):
                entry['sha256'] = legacy.sha(path)
            result[path.relative_to(repo).as_posix()] = entry
    return result


def scope_changes(original, actual, allowed):
    changed = sorted(n for n in set(original) | set(actual) if original.get(n) != actual.get(n))
    valid = all(n in allowed and n in original and n in actual
                and original[n]['kind'] == actual[n]['kind'] == 'file'
                and original[n]['mode'] == actual[n]['mode'] for n in changed)
    return changed, valid


def enforce_product_deadline(value):
    if value.get('time_limit_exceeded'):
        value.update(status='evaluation_error', comparison_eligible=False,
                     first_error={'type': 'OriginalAllocationDeadlineExceeded',
                                  'message': 'Product verification and cleanup exceeded original 1200 seconds'})


def collect(run, agent_path):
    adapt(run)
    result = legacy.collect(run, agent_path)
    folder, out = ROOT / 'runtime' / run, ROOT / 'results' / run
    metadata = legacy.read(folder / 'run.json')
    assert metadata['status'] == 'collected'
    assert not legacy.owned_identity(metadata)['State']['Running']
    atomic_json(out / 'protected-artifact-seal-v1.json', {
        'entities': protected_tree(folder / 'repo'),
        'native_artifact_seal_sha256': legacy.sha(out / 'artifact-seal.json')}, exclusive=True)
    return result


def case_directory(case):
    assert case in {'S01', 'S02', 'Q02'}
    return ROOT / 'improvement_cases/fresh-pilot-v2' / case


def closure():
    pending, found = [Path(__file__).resolve()], set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_bytes())):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                if name:
                    local = ROOT / 'tools' / (name.split('.')[0] + '.py')
                    if local.is_file() and local not in found:
                        pending.append(local)
    return found


def freeze():
    assert not FREEZE.exists()
    plan, review, quality = [legacy.read(p) for p in (PLAN, REVIEW, QUALITY)]
    assert review['verdict'] == quality['verdict'] == 'pass'
    assert not review['issues'] and not quality['issues']
    assert plan['trajectory_seconds'] == 1200 and plan['actor_retries'] == 0
    assert plan['model'] == 'gpt-6.1-sol' and plan['reasoning'] == 'medium'
    assert plan['qualification_review_sha256'] == legacy.sha(QUALITY)
    candidate_path = ROOT / 'results/improvement-v1/candidate-C14-freeze-v1.json'
    candidate = legacy.read(candidate_path)
    assert candidate['skill_tree_hash'] == legacy.prepare.tree_hash(ROOT / 'snapshots/C14')
    assert candidate['skill_hashes'] == legacy.digest_tree(ROOT / 'snapshots/C14')
    summary = legacy.read(SUMMARY)
    assert all(summary['cases'][c]['behavior_qualified'] for c in ('S01', 'S02', 'Q02'))
    registration = collector.verify()
    files = closure() | {PLAN, REVIEW, QUALITY, SUMMARY, candidate_path, ROOT / 'runtime/p02_native_watch_v3.py',
                         ROOT / 'AGENTS.md', ROOT / 'docs/improvement-spec-v1.md',
                         ROOT / 'runtime/image.json', collector.MANIFEST}
    for value in (review, quality, registration):
        for key in ('source_hashes', 'evidence_hashes'):
            for name, digest in value.get(key, {}).items():
                assert legacy.sha(ROOT / name) == digest, name
                files.add(ROOT / name)
    for case in ('S01', 'S02', 'Q02'):
        files.update(p for p in case_directory(case).rglob('*') if p.is_file())
    for condition in ('C0', 'C14'):
        files.update(p for p in (ROOT / 'snapshots' / condition).rglob('*') if p.is_file())
    value = {'status': 'frozen', 'model': 'gpt-6.1-sol', 'effort': 'medium',
             'image_id': IMAGE, 'trajectory_seconds': 1200, 'retries': 0,
             'conditions': ['A', 'C0', 'C14'], 'sequence': plan['sequence'],
             'source_hashes': {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p): legacy.sha(p)
                               for p in sorted(files)},
             'case_hashes': {c: legacy.prepare.tree_hash(case_directory(c)) for c in ('S01', 'S02', 'Q02')},
             'skill_hashes': {c: legacy.prepare.tree_hash(ROOT / 'snapshots' / c) for c in ('C0', 'C14')},
             'primary_confirmation_reuse_allowed': False, 'superiority_proven': False,
             'complete_final_cost': False, 'actor_cap': 1, 'concurrency': 1}
    atomic_json(FREEZE, value, exclusive=True)
    return value


def configure():
    legacy.prior.FREEZE = FREEZE
    legacy.prior.PHASE = PHASE
    legacy.prior.case_directory = case_directory
    legacy.prior.quiesce = legacy.quiesce
    value = legacy.prior.check()
    assert value['image_id'] == IMAGE and value['model'] == 'gpt-6.1-sol' and value['effort'] == 'medium'
    return value


def adapt(run):
    value = configure()
    row = next(r for r in value['sequence'] if r['run_id'] == run)
    legacy.FREEZE, legacy.PHASE = FREEZE, PHASE
    legacy.CASE, legacy.case_directory = case_directory(row['case_id']), case_directory
    legacy.configure = configure
    legacy.collector = collector
    legacy._launch = prepare_original_allocation
    return row


def prepare_original_allocation(run):
    value = configure()
    row = legacy.next_allocation(value)
    assert row['run_id'] == run, 'Only next preregistered original allocation'
    assert not subprocess.check_output(['docker', 'ps', '-q', '--filter', 'name=codify-'], text=True, timeout=30).strip()
    folder, out = ROOT / 'runtime' / run, ROOT / 'results' / run
    assert not folder.exists()
    name = 'codify-' + run.lower()
    absent = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=30)
    assert absent.returncode != 0 and 'No such object' in absent.stderr
    out.mkdir()
    started = time.time()
    atomic_json(out / 'launch-intent.json', {'run_id': run, 'started_at': started, 'actor_retries': 0}, exclusive=True)
    legacy.prepare.case_directory = case_directory
    legacy.prepare.prepare(row['case_id'], row['condition'], row['repeat'], PHASE)
    metadata = legacy.read(folder / 'run.json')
    assert metadata['run_id'] == run
    identity = json.loads(subprocess.check_output(['docker', 'inspect', metadata['container']], text=True, timeout=30))[0]
    metadata.update(evaluation_core={'path': str(FREEZE), 'sha256': legacy.sha(FREEZE)},
                    time_limit_seconds=1200, user_turn_limit=1, started_at=started, container_id=identity['Id'])
    atomic_json(folder / 'run.json', metadata)
    legacy.prior.bind(run, value)
    legacy.owned_identity(metadata)
    legacy.inspect_repo(folder / 'repo')
    prompt = legacy.dispatch.dispatch(run)
    metadata = legacy.read(folder / 'run.json')
    metadata.update(native_dispatch_started_at=metadata['agent_started_at'], agent_started_at=started)
    atomic_json(folder / 'run.json', metadata)
    atomic_json(out / 'bootstrap-input-intent.json', {
        'run_id': run, 'created_at': time.time(), 'bootstrap_sha256': legacy.sha(folder / 'bootstrap.txt'),
        'request_sha256': legacy.sha(folder / 'request.txt'), 'model': 'gpt-6.1-sol', 'effort': 'medium',
        'fork_turns': 'none', 'owner': 'root', 'native_plaintext_equality_required_when_available': True}, exclusive=True)
    atomic_json(out / 'dispatched.json', {'run_id': run, 'dispatched_at': time.time(),
                'prompt_sha256': legacy.sha(folder / 'request.txt')}, exclusive=True)
    return prompt


def launch(run):
    adapt(run)
    original_dispatch = legacy.dispatch.dispatch

    def dispatch_with_dependencies(run_id):
        folder, out = ROOT / 'runtime' / run_id, ROOT / 'results' / run_id
        metadata = legacy.read(folder / 'run.json')
        deadline = legacy.read(out / 'launch-intent.json')['started_at'] + 1200
        seconds = min(120, int(deadline - time.time()) - 6)
        assert seconds > 0
        argv = ['docker', 'exec', metadata['container'], '/usr/bin/timeout', '--kill-after=5s',
                str(seconds) + 's', *COMMANDS[0]]
        started = time.time()
        result = subprocess.run(argv, capture_output=True, text=True, timeout=seconds + 6)
        atomic_json(out / 'root-dependency-preparation-v1.json', {
            'argv': argv, 'exit_code': result.returncode, 'stdout': result.stdout,
            'stderr': result.stderr, 'started_at': started, 'finished_at': time.time(),
            'included_in_original_allocation_clock': True, 'model_command': False}, exclusive=True)
        result.check_returncode()
        atomic_json(out / 'prepared-base-v1.json', {
            'files': legacy.digest_tree(folder / 'repo'),
            'entities': protected_tree(folder / 'repo'),
            'known_generated_dependency_state': True}, exclusive=True)
        return original_dispatch(run_id)

    legacy.dispatch.dispatch = dispatch_with_dependencies
    try:
        return legacy.launch(run)
    finally:
        legacy.dispatch.dispatch = original_dispatch


def complete_observation(execution, count):
    checks, machine = execution.get('checks', []), execution.get('machine', {})
    return (execution.get('status') == 'completed' and execution.get('removed') is True
            and execution.get('source_unchanged') is True and machine.get('well_formed') is True
            and machine.get('test_count') == count and type(machine.get('pass')) is bool
            and len(checks) == 3
            and all(c.get('inner_argv') == command and type(c.get('exit_code')) is int
                    and c['exit_code'] not in {124, 137, 143} for c, command in zip(checks, COMMANDS))
            and checks[0]['exit_code'] == 0)


def grade(run):
    row = adapt(run)
    _, metadata = legacy.bound(run)
    folder, out = ROOT / 'runtime' / run, ROOT / 'results' / run
    assert not (out / 'grade.json').exists()
    assert metadata['status'] == 'collected' and len(metadata['turns']) == 1
    assert not legacy.owned_identity(metadata)['State']['Running']
    actual = legacy.digest_tree(folder / 'repo')
    assert actual == legacy.read(out / 'artifact-seal.json')['files']
    entities = protected_tree(folder / 'repo')
    seal = legacy.read(out / 'protected-artifact-seal-v1.json')
    assert entities == seal['entities']
    assert seal['native_artifact_seal_sha256'] == legacy.sha(out / 'artifact-seal.json')
    original = legacy.read(out / 'prepared-base-v1.json')['entities']
    allowed = legacy.read(case_directory(row['case_id']) / 'metadata.json')['scope']['allowed_files']
    changes, scope_pass = scope_changes(original, entities, allowed)
    case = case_directory(row['case_id'])
    case_meta = legacy.read(case / 'metadata.json')
    value = {'run_id': run, 'status': 'grading', 'actor_allocated': True, 'actor_retried': False,
             'started_at': metadata['started_at'], 'scope_pass': scope_pass,
             'changed': changes, 'transport_violations': metadata['tool_audit'],
             'behavior_pass': None, 'software_pass': None, 'report_pass': None, 'overall_pass': None,
             'complete_final_cost': False, 'superiority_proven': False,
             'primary_confirmation_reuse_allowed': False, 'lifecycle_errors': [],
             'usage': legacy.read(out / 'native-usage-v4.json'),
             'product_timing': legacy.read(out / 'product-timing.json')}
    atomic_json(out / 'grade.json', value, exclusive=True)
    try:
        assert not metadata['tool_audit'], 'Transport violation; no eligible software grading'
        source = ROOT / 'runtime/fresh-solo-v1-grading' / run / 'source'
        shutil.copytree(folder / 'repo', source, ignore=shutil.ignore_patterns('.git', '.dart_tool', 'build', '__pycache__'))
        public_count = case_meta['expected_total_test_count'] - case_meta['expected_private_test_count']
        public = verify(source, source.parent / 'public', metadata['started_at'] + 1200, expected_tests=public_count)
        value['public_verification'] = public
        if public.get('removed') is not True:
            value['lifecycle_errors'].append({'type': 'PublicVerifierCleanupUnproven'})
        assert complete_observation(public, public_count), 'Incomplete public observation'
    except Exception as error:
        value.update(status='evaluation_error', first_error={'type': type(error).__name__, 'message': str(error)})
    finally:
        try:
            value['product_cleanup'] = legacy.remove_owned(metadata)
            value['allocation_through_product_cleanup_seconds'] = time.time() - metadata['started_at']
            value['time_limit_exceeded'] = value['allocation_through_product_cleanup_seconds'] > 1200
            enforce_product_deadline(value)
        except Exception as error:
            value['lifecycle_errors'].append({'type': type(error).__name__, 'message': str(error)})
            value['status'] = 'evaluation_error'
        value['finished_at'] = time.time()
        atomic_json(out / 'grade.json', value)
    if value['status'] == 'grading':
        try:
            public_source = ROOT / 'runtime/fresh-solo-v1-grading' / run / 'source'
            source = public_source.parent / 'private-source'
            shutil.copytree(public_source, source)
            target = source / 'test/acceptance_test.dart'
            assert not target.exists()
            shutil.copyfile(case / 'oracle/test/acceptance_test.dart', target)
            value['private_grading_started_at'] = time.time()
            execution = verify(source, source.parent / 'private', time.time() + 600,
                               expected_tests=case_meta['expected_total_test_count'])
            value['verification_receipt'] = execution
            value['owned_grader_removed'] = execution.get('removed')
            assert complete_observation(execution, case_meta['expected_total_test_count']), 'Incomplete private observation is not software pass/fail'
            value.update(status='review_pending', behavior_pass=execution['machine']['pass'],
                         software_pass=execution['pass'] and value['public_verification']['pass'])
        except Exception as error:
            value.update(status='evaluation_error', first_error={'type': type(error).__name__, 'message': str(error)})
        finally:
            value['finished_at'] = time.time()
            value['allocation_through_grade_seconds'] = value['finished_at'] - metadata['started_at']
            atomic_json(out / 'grade.json', value)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['freeze', 'prepare', 'bind', 'collect', 'grade', 'abort'])
    parser.add_argument('run', nargs='?')
    parser.add_argument('agent_path', nargs='?')
    args = parser.parse_args()
    if args.action == 'freeze':
        result = freeze()
    elif args.action == 'prepare':
        result = launch(args.run)
    elif args.action == 'grade':
        result = grade(args.run)
    else:
        adapt(args.run)
        action = {'bind': legacy.bind_actor, 'collect': collect, 'abort': legacy.abort_deadline}[args.action]
        result = action(args.run, args.agent_path)
    print(result if isinstance(result, str) else json.dumps({k: v for k, v in result.items()
          if k not in {'source_hashes', 'checks', 'usage', 'machine', 'verification_receipt', 'public_verification'}}, ensure_ascii=False))
