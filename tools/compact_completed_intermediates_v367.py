"""Relocate completed evaluation intermediates into a verified lossless archive."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time

from prepare import ROOT
from collect import find_session


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_new(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)


def source_inventory(repo):
    return {str(p.relative_to(repo)): sha(p) for p in repo.rglob('*')
            if p.is_file() and not p.is_symlink()
            and not any(x in {'.git', '.dart_tool', 'build', '__pycache__', '.agents'}
                        for x in p.relative_to(repo).parts)}


def confined(path):
    path = Path(path)
    if path.resolve() != path.absolute() or not path.is_relative_to(ROOT):
        raise ValueError('Path escapes root or traverses a symlink')
    return path


def path_evidence(path):
    info = Path(path).lstat()
    value = {'mode': stat.S_IMODE(info.st_mode), 'type': stat.S_IFMT(info.st_mode)}
    if stat.S_ISLNK(info.st_mode):
        value.update(target=os.readlink(path), links=info.st_nlink)
    elif stat.S_ISREG(info.st_mode):
        value.update(bytes=info.st_size, sha256=sha(path), links=info.st_nlink)
    elif not stat.S_ISDIR(info.st_mode):
        raise ValueError('Unsupported special path in completed evidence')
    return value


def independent_reviewer(grade, result):
    reviewer = grade.get('reviewer', {})
    expected = {'model': 'gpt-6.1-sol', 'effort': 'medium'}
    if (not isinstance(reviewer, dict) or not reviewer.get('agent_path')
            or reviewer.get('models') != [expected] or not reviewer.get('review_sha256')):
        raise ValueError('Qualified independent reviewer unavailable')
    session = find_session(reviewer['agent_path'])
    events = [json.loads(line) for line in session.read_text().splitlines()]
    models = [{'model': e['payload'].get('model'), 'effort': e['payload'].get('effort')}
              for e in events if e['type'] == 'turn_context']
    completed = [e for e in events if e.get('payload', {}).get('type') == 'task_complete']
    if models != [expected] or len(completed) != 1 or session.name != reviewer.get('session'):
        raise ValueError('Reviewer native context/completion mismatch')
    meta = events[0]['payload']
    parent_id = meta.get('parent_thread_id')
    parents = list(session.parent.glob('*' + str(parent_id) + '.jsonl'))
    if len(parents) != 1:
        raise ValueError('Reviewer parent provenance unavailable')
    parent_events = [json.loads(line) for line in parents[0].read_text().splitlines()]
    task_name = reviewer['agent_path'].rsplit('/', 1)[1]
    calls = []
    for e in parent_events:
        p = e.get('payload', {})
        if p.get('type') == 'function_call' and p.get('name') == 'spawn_agent':
            a = json.loads(p['arguments'])
            if a.get('task_name') == task_name:
                calls.append((p, a))
    if len(calls) != 1 or any(calls[0][1].get(k) != v for k, v in
                            [('fork_turns', 'none'), ('model', 'gpt-6.1-sol'), ('reasoning_effort', 'medium')]):
        raise ValueError('Fresh independent reviewer spawn unproven')
    outputs = [e['payload'] for e in parent_events
               if e.get('payload', {}).get('type') == 'function_call_output'
               and e['payload'].get('call_id') == calls[0][0]['call_id']]
    if len(outputs) != 1 or reviewer['agent_path'] not in str(outputs[0]):
        raise ValueError('Reviewer normal spawn return unproven')
    mapping = json.loads(confined(result / 'review-bundle-map.json').read_text())
    blind = ROOT / 'runtime/blind-reviews' / mapping['alias']
    if not blind.exists():
        blind = ROOT / 'runtime/revisions/w02-public-scope-v3.6.4/blind-reviews' / mapping['alias']
    confined(blind)
    if (sha(blind / 'review.json') != reviewer['review_sha256']
            or sha(blind / 'evidence.json') != mapping['bundle_sha256']
            or sha(result / 'grade-before-report.json') != mapping['source_grade_sha256']
            or sha(result / 'turns.json') != mapping['source_turns_sha256']
            or grade.get('report_review') != mapping['alias']
            or json.loads((result / 'report-review.json').read_text()) !=
               json.loads((blind / 'review.json').read_text())):
        raise ValueError('Independent review artifacts changed')
    return {'native_sha256': sha(session), 'review_sha256': reviewer['review_sha256'],
            'fresh_context': True, 'completed_turns': 1}


def compact(run_ids):
    """Only finalized runs, stopped containers and narrowly selected .dill files."""
    candidates = set()
    protected = {}
    run_proofs = []
    for run_id in run_ids:
        if not re.fullmatch(r'software-W\w+-(?:A|B|C0)-[123]', run_id):
            raise ValueError('Invalid software run ID')
        live = ROOT / 'runtime' / run_id
        historical = ROOT / 'runtime/revisions/w02-public-scope-v3.6.4' / run_id
        runtime = live if live.exists() else historical
        result = ROOT / 'results' / run_id
        if not result.exists():
            result = ROOT / 'results/revisions/w02-public-scope-v3.6.4' / run_id
        confined(runtime)
        confined(result)
        metadata = json.loads((runtime / 'run.json').read_text())
        grade = json.loads((result / 'grade.json').read_text())
        if grade.get('status') not in {'pass', 'fail'}:
            raise ValueError('Run is not independently finalized: ' + run_id)
        reviewer_proof = independent_reviewer(grade, result)
        inspected = json.loads(subprocess.check_output(['docker', 'inspect', metadata['container']]))[0]
        if inspected['State']['Running']:
            raise ValueError('Container must be stopped: ' + run_id)
        turns = json.loads((result / 'turns.json').read_text())
        if not turns or not all(isinstance(x.get('file_hashes'), dict) and x['file_hashes'] for x in turns):
            raise ValueError('Nonempty final source snapshots required')
        recorded = {name for turn in turns for name in turn['file_hashes']}
        repo = runtime / 'repo'
        confined(repo)
        before = source_inventory(repo)
        for turn in turns[-1:]:
            if before != turn['file_hashes']:
                raise ValueError('Final source snapshot differs: ' + run_id)
        actor_candidates = list(repo.glob('.dart_tool/flutter_build/*/app.dill'))
        actor_candidates += list(repo.glob('build/test_cache/**/*.dill'))
        if any(str(p.relative_to(repo)) in recorded for p in actor_candidates):
            raise ValueError('Intermediate appears in a scored snapshot')
        candidates.update(actor_candidates)
        grading = ROOT / 'runtime/software-grading' / run_id
        if not grading.exists():
            grading = ROOT / 'runtime/revisions/w02-public-scope-v3.6.4/software-grading' / run_id
        confined(grading)
        candidates.update(grading.glob('work/build/test_cache/**/*.dill'))
        candidates.update(grading.glob('work/.dart_tool/flutter_build/*/app.dill'))
        # Retain all original run evidence and every source/bundle byte at live paths.
        for base in (runtime, result, grading):
            if base.exists():
                protected[str(base.relative_to(ROOT))] = path_evidence(base)
                for p in base.rglob('*'):
                    protected[str(p.relative_to(ROOT))] = path_evidence(p)
        run_proofs.append({'run_id': run_id, 'container_id': inspected['Id'],
                           'container_stopped': True, 'source_sha256': before,
                           'reviewer_proof': reviewer_proof})
    for p in candidates:
        confined(p)
        info = p.lstat()
        if not stat.S_ISREG(info.st_mode) or p.is_symlink() or info.st_nlink != 1:
            raise ValueError('Only regular selected intermediate files are eligible')
        protected.pop(str(p.relative_to(ROOT)), None)
    if not candidates:
        return {'status': 'no_eligible_intermediates'}
    token = str(time.time_ns())
    directory = ROOT / 'results/intermediate-preservation'
    directory.mkdir(exist_ok=True)
    confined(directory)
    archive = directory / (token + '.tar.gz')
    records = {str(p.relative_to(ROOT)): {'sha256': sha(p), 'bytes': p.stat().st_size,
               'mode': stat.S_IMODE(p.stat().st_mode), 'restore_path': str(p),
               'original_lstat': path_evidence(p)}
               for p in sorted(candidates)}
    plan = {'status': 'preregistered_before_relocation', 'runs': run_proofs,
            'files': records, 'protected_path_evidence': protected, 'archive': str(archive),
            'helper_sha256': sha(Path(__file__)), 'free_before': shutil.disk_usage(ROOT).free,
            'release_and_source_relocation_allowed': False}
    plan_path = directory / (token + '-plan.json')
    write_new(plan_path, plan)
    with tarfile.open(archive, 'x:gz', compresslevel=1) as stream:
        for name in records:
            stream.add(ROOT / name, arcname=name, recursive=False)
    restored = set()
    with tempfile.TemporaryDirectory(dir=directory) as tmp:
        with tarfile.open(archive, 'r|gz') as stream:
            for member in stream:
                record = records.get(member.name)
                if record is None or not member.isfile() or member.name in restored:
                    raise ValueError('Unexpected archive member')
                target = Path(tmp) / 'restored-intermediate'
                with stream.extractfile(member) as source, target.open('wb') as dest:
                    shutil.copyfileobj(source, dest)
                target.chmod(member.mode)
                if (sha(target), target.stat().st_size, stat.S_IMODE(target.stat().st_mode)) != (
                        record['sha256'], record['bytes'], record['mode']):
                    raise ValueError('Restored byte/hash/mode mismatch')
                target.unlink()
                restored.add(member.name)
    if restored != set(records):
        raise ValueError('Archive membership incomplete')
    proof = {**plan, 'status': 'archive_and_restoration_verified_before_relocation',
             'plan_sha256': sha(plan_path), 'archive_sha256': sha(archive),
             'archive_bytes': archive.stat().st_size, 'members_verified': len(restored)}
    proof_path = directory / (token + '-preservation.json')
    write_new(proof_path, proof)
    if any(path_evidence(ROOT / name) != value for name, value in protected.items()):
        raise ValueError('Protected evidence changed before relocation')
    for name, record in records.items():
        p = ROOT / name
        confined(p)
        if path_evidence(p) != record['original_lstat']:
            raise ValueError('Intermediate changed before relocation')
    for name in records:
        (ROOT / name).unlink()
    if any(path_evidence(ROOT / name) != value for name, value in protected.items()):
        raise ValueError('Protected evidence changed after relocation')
    result = {'status': 'complete', 'preservation_path': str(proof_path),
              'preservation_sha256': sha(proof_path), 'archive': str(archive),
              'members_relocated': len(records), 'original_bytes': sum(x['bytes'] for x in records.values()),
              'archive_bytes': archive.stat().st_size, 'protected_files_unchanged': len(protected),
              'free_after': shutil.disk_usage(ROOT).free}
    write_new(directory / (token + '-complete.json'), result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='append', default=[])
    args = parser.parse_args()
    print(json.dumps(compact(args.run)))
