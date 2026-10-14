"""Fixture-only qualification. Preserve attempt one and use exact parent test IDs."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'runtime/protocol-probes/software-broker-fixture-v2'
OUT = ROOT / 'results/improvement-v1/software-broker-fixture-v2-host-qualification-v2.json'
WORK = ROOT / 'runtime/protocol-probes/software-broker-fixture-v2-host-qualification-v2'
RUNNER = '''import json, unittest
suite = unittest.defaultTestLoader.discover('tests')
result = unittest.TestResult()
suite.run(result)
def record(test, trace):
    parent = test.test_case if isinstance(test, unittest.case._SubTest) else test
    return {'id': test.id(), 'parent_id': parent.id(), 'trace': trace}
print(json.dumps({'tests_run': result.testsRun,
 'failures': [record(t, s) for t, s in result.failures],
 'errors': [record(t, s) for t, s in result.errors],
 'successful': result.wasSuccessful()}))
raise SystemExit(0 if result.wasSuccessful() else 1)
'''

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def inventory(path):
    entries = sorted(path.rglob('*'))
    if any(p.is_symlink() or not (p.is_file() or p.is_dir()) for p in entries):
        raise ValueError('nonregular fixture entity')
    return {str(p.relative_to(path)): sha(p) for p in entries if p.is_file()}

def save(data):
    # Exclusive first creation; updates only this invocation's newly created receipt.
    OUT.write_text(json.dumps(data, indent=2) + '\n')

def main():
    if OUT.exists() or WORK.exists():
        raise ValueError('qualification namespace already exists')
    old = ROOT / 'results/improvement-v1/software-broker-fixture-v2-host-qualification.json'
    review = ROOT / 'results/improvement-v1/software-broker-fixture-v2-review.json'
    original = inventory(FIXTURE)
    previous = json.loads(old.read_text())
    assert previous['fixture_files_sha256'] == original
    assert previous['status'] == 'fail'
    assert json.loads(review.read_text())['verdict'] == 'pass'
    meta = json.loads((FIXTURE / 'fixture.json').read_text())
    receipt = {'status': 'frozen_not_run', 'fixture_files_sha256': original,
        'previous_attempt_sha256': sha(old), 'review_sha256': sha(review),
        'qualification_source_sha256': sha(Path(__file__)),
        'test_runner_sha256': hashlib.sha256(RUNNER.encode()).hexdigest(),
        'python': sys.version, 'rows': [], 'model_run': False,
        'broker_qualified': False, 'superiority_proven': False}
    with OUT.open('x') as f:
        f.write(json.dumps(receipt, indent=2) + '\n')
    WORK.mkdir()
    try:
        for probe in meta['discrimination_probes']:
            clone = WORK / probe['id']
            shutil.copytree(FIXTURE / 'starting', clone)
            for overlay in (probe.get('base_overlay'), probe.get('overlay')):
                if overlay:
                    shutil.copytree(FIXTURE / overlay, clone, dirs_exist_ok=True)
            before = inventory(clone)
            proc = subprocess.run([sys.executable, '-B', '-c', RUNNER],
                cwd=clone, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                capture_output=True, text=True, timeout=30)
            observed = json.loads(proc.stdout)
            want_success = probe['expected_exit'] == 'zero'
            discriminator = probe.get('discriminating_test')
            qualified = (proc.returncode == (0 if want_success else 1)
                and observed['tests_run'] == 10 and not observed['errors']
                and observed['successful'] == want_success
                and bool(observed['failures']) != want_success
                and (not discriminator or discriminator in
                     {r['parent_id'] for r in observed['failures']})
                and before == inventory(clone) and not proc.stderr)
            receipt['rows'].append({'id': probe['id'], 'qualified': qualified,
                'exit_code': proc.returncode, 'observed': observed,
                'stdout': proc.stdout, 'stderr': proc.stderr,
                'clone_files_sha256': before, 'clone_unchanged': before == inventory(clone)})
            save(receipt)
        assert inventory(FIXTURE) == original
        assert sha(old) == receipt['previous_attempt_sha256']
        assert sha(review) == receipt['review_sha256']
        receipt['status'] = ('host_fixture_behavior_qualified' if
                            all(r['qualified'] for r in receipt['rows']) else 'fail')
    except BaseException as error:
        receipt['status'] = 'evaluation_error'
        receipt['error'] = {'type': type(error).__name__, 'message': str(error)}
        save(receipt)
        raise
    save(receipt)
    print(json.dumps({'status': receipt['status'], 'rows':
        [{'id': r['id'], 'qualified': r['qualified'],
          'failures': len(r['observed']['failures'])} for r in receipt['rows']]}))
    if receipt['status'] != 'host_fixture_behavior_qualified':
        raise SystemExit(1)

if __name__ == '__main__':
    main()
