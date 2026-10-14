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
import uuid

from improvement_boundary_v1 import inspect_repo
from improvement_qualify_v1 import ROOT, digest_tree
from improvement_qualify_v3 import failed_tests


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assertion_failure_names(log):
    """Require matcher assertion evidence for each failed test, not any exception."""
    tests = {}
    assertions = set()
    for line in log.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get('type') == 'testStart':
            tests[event['test']['id']] = event['test']['name']
        if event.get('type') == 'error':
            error = str(event.get('error', ''))
            if ('Expected:' in error and 'Actual:' in error) or 'TestFailure' in error:
                assertions.add(event.get('testID'))
    return {tests[test_id] for test_id in assertions if test_id in tests}


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
    out = ROOT / 'results/improvement-v1/confirmation-qualification-v2' / case_id
    runtime = ROOT / 'runtime/improvement-confirmation-qualification-v2' / case_id
    assert not out.exists() and not runtime.exists(), 'Preserve every previous attempt'
    out.mkdir(parents=True)
    image_path = ROOT / 'runtime/image.json'
    image = json.loads(image_path.read_text())['image_id']
    rows = []
    owner_token = uuid.uuid4().hex
    receipt = {'case_id': case_id, 'image_id': image, 'source_hashes': frozen,
               'coverage_sha256': sha(coverage_path), 'helper_sha256': sha(Path(__file__)),
               'dependency_hashes': {name: sha(ROOT / 'tools' / name) for name in (
                   'improvement_qualify_v1.py', 'improvement_qualify_v3.py', 'improvement_boundary_v1.py')},
               'variants': rows, 'status': 'running', 'runtime_tier': 'Dart domain behavior only',
               'question_run_qualified': False, 'orchestration_run_qualified': False,
               'superiority_proven': False, 'owner_token': owner_token}

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
            container_id = None
            failure = None
            try:
                launched = subprocess.run(['docker', 'create', '--name', container, '--network', 'none',
                                '--label', 'codify.eval.role=confirmation-qualification-v2',
                                '--label', 'codify.eval.owner=' + owner_token,
                                '-v', str(repo) + ':/work/repo', '-w', '/work/repo', image,
                                'sleep', 'infinity'], check=True, capture_output=True, text=True, timeout=60)
                container_id = launched.stdout.strip()
                identity = json.loads(subprocess.run(['docker', 'inspect', container_id], check=True,
                                                     capture_output=True, text=True, timeout=30).stdout)[0]
                identity_path = out / (label + '-container-identity.json')
                identity_path.write_text(json.dumps(identity, indent=2) + '\n')
                assert identity['Id'] == container_id and identity['Image'] == image
                assert identity['HostConfig']['NetworkMode'] == 'none'
                assert identity['Config']['Labels']['codify.eval.role'] == 'confirmation-qualification-v2'
                assert len(identity['Mounts']) == 1
                mount = identity['Mounts'][0]
                assert mount['Type'] == 'bind' and mount['Source'] == str(repo) and mount['Destination'] == '/work/repo'
                row['container_id'] = container_id
                row['identity_sha256'] = sha(identity_path)
                subprocess.run(['docker', 'start', container_id], check=True, capture_output=True, timeout=60)

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
                assertion_failures = assertion_failure_names(Path(tests['output']).read_text())
                row.update(failing_tests=names, assertion_failure_names=sorted(assertion_failures), compile_or_timeout_or_incomplete=invalid_failure)
                baseline_ok = deps['exit_code'] == public['exit_code'] == 0
                if label == 'reference':
                    row['qualified'] = baseline_ok and tests['exit_code'] == analyze['exit_code'] == 0
                else:
                    expected = coverage['expected_failing_tests'][case_id][label]
                    row['qualified'] = baseline_ok and tests['exit_code'] == 1 and not invalid_failure and set(expected) == set(names) and set(names) <= assertion_failures
            except Exception as error:
                failure = error
                row['first_error'] = {'type': type(error).__name__, 'message': str(error)}
                persist()
            finally:
                # Recover creation/start timeouts by the unique persisted ownership token.
                # Cleanup errors are separate evidence and cannot replace first_error.
                row['lifecycle_errors'] = []
                try:
                    found = subprocess.run(['docker', 'inspect', container], capture_output=True, text=True, timeout=30)
                    if found.returncode == 0:
                        identity = json.loads(found.stdout)[0]
                        owned = (identity['Config']['Labels'].get('codify.eval.owner') == owner_token
                                 and identity['Image'] == image and len(identity['Mounts']) == 1
                                 and identity['Mounts'][0]['Source'] == str(repo)
                                 and identity['Mounts'][0]['Destination'] == '/work/repo')
                        assert owned, 'Cleanup ownership mismatch; container retained'
                        container_id = identity['Id']
                        archived_ok = False
                        for stage, args in [
                            ('stop', ['docker', 'stop', '-t', '2', container_id]),
                            ('diagnostic_archive', ['docker', 'cp', container_id + ':/tmp', str(out / (label + '-container-tmp'))]),
                            ('cleanup', ['docker', 'rm', '-f', container_id]),
                        ]:
                            if stage == 'cleanup' and not archived_ok:
                                row['lifecycle_errors'].append('Diagnostic archive unavailable; owned container retained')
                                continue
                            try:
                                result = subprocess.run(args, capture_output=True, text=True, timeout=60)
                                row[stage] = {'exit_code': result.returncode}
                                if stage == 'diagnostic_archive':
                                    archived_ok = result.returncode == 0
                                if result.returncode != 0:
                                    row['lifecycle_errors'].append(stage + ' failed: ' + result.stderr[-1000:])
                            except Exception as error:
                                row['lifecycle_errors'].append(stage + ': ' + type(error).__name__ + ': ' + str(error))
                    elif 'No such object' in found.stderr:
                        row['cleanup'] = {'status': 'container_not_created_or_already_removed'}
                    else:
                        row['lifecycle_errors'].append('Ownership inspection failed: ' + found.stderr[-1000:])
                except Exception as error:
                    row['lifecycle_errors'].append(type(error).__name__ + ': ' + str(error))
                persist()
            if failure:
                raise failure
            if row['lifecycle_errors']:
                raise RuntimeError('Owned lifecycle incomplete; inspect preserved receipt')
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
