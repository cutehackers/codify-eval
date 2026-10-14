"""Qualify frozen Q fixtures without exposing implementation text to coordinator.

Behavior qualification only. Q03 dialogue and Q04 orchestration run evidence
remain separate prerequisites, not inferred from reference/negative tests.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from improvement_boundary_v1 import inspect_repo
from improvement_qualify_v1 import ROOT, digest_tree
from improvement_qualify_v3 import failed_tests


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qualify(case_id):
    assert case_id in {'Q01', 'Q02', 'Q03', 'Q04'}
    coverage_path = ROOT / 'results/improvement-v1/confirmation-coverage-review-v2.json'
    coverage = json.loads(coverage_path.read_text())
    assert coverage['verdict'] == 'fixture_static_pass_pending_runtime_and_run_evidence'
    for name, digest in coverage['source_hashes'].items():
        assert sha(ROOT / name) == digest, name
    case = ROOT / 'improvement_cases/confirmatory' / case_id
    frozen = digest_tree(case)
    assert {str((case / name).relative_to(ROOT)): value for name, value in frozen.items()} == {
        name: value for name, value in coverage['source_hashes'].items()
        if name.startswith(str(case.relative_to(ROOT)) + '/')
    }, 'Case inventory differs from independently reviewed inventory'
    metadata = json.loads((case / 'metadata.json').read_text())
    out = ROOT / 'results/improvement-v1/confirmation-qualification-v1' / case_id
    runtime = ROOT / 'runtime/improvement-confirmation-qualification-v1' / case_id
    assert not out.exists() and not runtime.exists(), 'Preserve every previous attempt'
    out.mkdir(parents=True)
    image_path = ROOT / 'runtime/image.json'
    image = json.loads(image_path.read_text())['image_id']
    rows = []
    receipt = {'case_id': case_id, 'image_id': image, 'source_hashes': frozen,
               'coverage_sha256': sha(coverage_path), 'helper_sha256': sha(Path(__file__)),
               'dependency_hashes': {name: sha(ROOT / 'tools' / name) for name in (
                   'improvement_qualify_v1.py', 'improvement_qualify_v3.py', 'improvement_boundary_v1.py')},
               'variants': rows, 'status': 'running', 'runtime_tier': 'Dart domain behavior only',
               'question_run_qualified': False, 'orchestration_run_qualified': False,
               'superiority_proven': False}

    def persist():
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

    persist()
    variants = [('start', None), ('reference', case / 'reference')] + [
        (name, case / 'negative' / name) for name in metadata['negative_variants']]
    try:
        for label, overlay in variants:
            assert shutil.disk_usage(ROOT).free >= 3 * 1024**3, 'Disk below 3GiB floor'
            repo = runtime / label / 'repo'
            shutil.copytree(case / 'repo', repo)
            if overlay:
                shutil.copytree(overlay / 'lib', repo / 'lib', dirs_exist_ok=True)
            inspect_repo(repo)
            container = f'codify-confirm-qual-v1-{case_id.lower()}-{label.lower()}'
            row = {'variant': label, 'checks': [], 'qualified': False}
            rows.append(row)
            persist()
            started_container = False
            try:
                launched = subprocess.run(['docker', 'run', '-d', '--name', container, '--network', 'none',
                                '--label', 'codify.eval.role=confirmation-qualification-v1',
                                '-v', str(repo) + ':/work/repo', '-w', '/work/repo', image,
                                'sleep', 'infinity'], check=True, capture_output=True, text=True, timeout=60)
                started_container = True
                container_id = launched.stdout.strip()
                identity = json.loads(subprocess.run(['docker', 'inspect', container_id], check=True,
                                                     capture_output=True, text=True, timeout=30).stdout)[0]
                identity_path = out / (label + '-container-identity.json')
                identity_path.write_text(json.dumps(identity, indent=2) + '\n')
                assert identity['Id'] == container_id and identity['Image'] == image
                assert identity['HostConfig']['NetworkMode'] == 'none'
                assert identity['Config']['Labels']['codify.eval.role'] == 'confirmation-qualification-v1'
                assert len(identity['Mounts']) == 1
                mount = identity['Mounts'][0]
                assert mount['Type'] == 'bind' and mount['Source'] == str(repo) and mount['Destination'] == '/work/repo'
                row['container_id'] = container_id
                row['identity_sha256'] = sha(identity_path)

                def command(text, stage):
                    started = time.monotonic()
                    proc = subprocess.run(['docker', 'exec', container_id, 'timeout', '180s',
                                           'bash', '-lc', text], capture_output=True, text=True, timeout=190)
                    log = out / f'{label}-{stage}.log'
                    log.write_text(proc.stdout + proc.stderr)
                    result = {'stage': stage, 'command': text, 'exit_code': proc.returncode,
                              'elapsed_seconds': time.monotonic() - started,
                              'output': str(log), 'sha256': sha(log)}
                    row['checks'].append(result)
                    persist()
                    return result

                deps = command('flutter pub get --offline', 'dependencies')
                public = command('flutter test --no-pub --machine', 'public')
                # Public smoke acceptance is independent of private behavioral tests.
                shutil.copytree(case / 'oracle/test', repo / 'test', dirs_exist_ok=True)
                inspect_repo(repo)
                tests = command('flutter test --no-pub --machine', 'behavior')
                analyze = command('flutter analyze --no-pub', 'analysis')
                names, invalid_failure = failed_tests(Path(tests['output']).read_text())
                row.update(failing_tests=names, compile_or_timeout_or_incomplete=invalid_failure)
                baseline_ok = deps['exit_code'] == public['exit_code'] == 0
                if label == 'reference':
                    row['qualified'] = baseline_ok and tests['exit_code'] == analyze['exit_code'] == 0
                else:
                    expected = coverage['expected_failing_tests'][case_id][label]
                    row['qualified'] = baseline_ok and tests['exit_code'] == 1 and not invalid_failure and bool(set(expected) & set(names))
            finally:
                if started_container:
                    stopped = subprocess.run(['docker', 'stop', '-t', '2', container_id], capture_output=True, text=True, timeout=30)
                    row['stop'] = {'exit_code': stopped.returncode}
                    # Preserve writable-layer diagnostics before removal. Repo is already host-owned.
                    archived = subprocess.run(['docker', 'cp', container_id + ':/tmp', str(out / (label + '-container-tmp'))], capture_output=True, text=True, timeout=60)
                    row['diagnostic_archive'] = {'exit_code': archived.returncode}
                    removed = subprocess.run(['docker', 'rm', '-f', container_id], capture_output=True, text=True, timeout=30)
                    row['cleanup'] = {'exit_code': removed.returncode}
                    assert stopped.returncode == archived.returncode == removed.returncode == 0, 'Lifecycle cleanup failed'
                persist()
            assert digest_tree(case) == frozen, 'Immutable source mutated'
            print(case_id, label, row['qualified'], flush=True)
        receipt['status'] = 'behavior_qualified' if all(r['qualified'] for r in rows) else 'fail'
    except Exception as error:
        receipt.update(status='evaluation_error', first_error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        persist()
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('case', choices=['Q01', 'Q02', 'Q03', 'Q04'])
    result = qualify(parser.parse_args().case)
    raise SystemExit(0 if result['status'] == 'behavior_qualified' else 1)
