"""Real pristine verifier controls; no evaluated model or domain outcome claim."""
import hashlib
import json
from pathlib import Path
import shutil
import time

from improvement_q04_broker_v1 import source_closure
from improvement_q04_artifacts_v1 import atomic_json, tree
from improvement_q04_verifier_v5 import verify

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'runtime/protocol-probes/q04-public-controls-v1'
RESULT = ROOT / 'results/improvement-v1/Q04-public-controls-v1.json'


def main():
    assert not RESULT.exists() and not FOLDER.exists()
    fixture = ROOT / 'improvement_cases/confirmatory/Q04/repo'
    files = source_closure() | {Path(__file__).resolve()} | {p for p in fixture.rglob('*') if p.is_file()}
    pins = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    value = {'status': 'running', 'source_hashes': pins, 'started_at': time.time(),
             'actual_actor_allocated': False, 'native_binding_qualified': False,
             'private_acceptance_grading': False, 'superiority_proven': False,
             'launch_qualified': False, 'runs': {}, 'first_error': None}
    atomic_json(RESULT.with_name('Q04-public-controls-freeze-v1.json'), dict(value, status='frozen_coordinator_controls_only'), exclusive=True)
    atomic_json(RESULT, value, exclusive=True)
    original = tree(fixture)
    FOLDER.mkdir()
    deadline = time.time() + 600
    try:
        for label in ('starting', 'intentional_failure'):
            source = FOLDER / label / 'source'
            shutil.copytree(fixture, source)
            if label == 'intentional_failure':
                (source / 'test/coordinator_failure_test.dart').write_text("import 'package:flutter_test/flutter_test.dart';\nvoid main() { test('coordinator synthetic failure control', () { expect(1, 2); }); }\n")
            receipt = verify(source, FOLDER / label / 'verifier', deadline, expected_tests=1 if label == 'starting' else 2)
            value['runs'][label] = receipt
            atomic_json(RESULT, value)
            assert receipt['status'] == 'completed' and receipt['removed'] and receipt['source_unchanged']
            assert receipt['machine']['well_formed']
            assert receipt['checks'][0]['exit_code'] == 0 and receipt['checks'][2]['exit_code'] == 0
            if label == 'starting':
                assert receipt['pass'] and receipt['checks'][1]['exit_code'] == 0
            else:
                assert not receipt['pass'] and receipt['checks'][1]['exit_code'] != 0
                assert receipt['machine']['test_errors']
        assert tree(fixture) == original
        assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == expected for p, expected in pins.items())
        value['status'] = 'pass_public_controls_only'
    except BaseException as error:
        value.update(status='failed', first_error={'type': type(error).__name__, 'message': str(error)})
    finally:
        value['completed_at'] = time.time()
        value['elapsed_seconds'] = value['completed_at'] - value['started_at']
        atomic_json(RESULT, value)
    print(json.dumps({k: value[k] for k in ('status', 'first_error', 'elapsed_seconds')}))
    return 0 if value['status'] == 'pass_public_controls_only' else 1


if __name__ == '__main__':
    raise SystemExit(main())
