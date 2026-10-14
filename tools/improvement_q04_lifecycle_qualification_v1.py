"""Coordinator-authored Docker plumbing qualification, never model performance."""
import base64
import hashlib
import json
from pathlib import Path
import time

import improvement_q04_artifacts_v1 as artifacts
import improvement_q04_broker_v1 as broker
import improvement_q04_runtime_v3 as runtime
from improvement_q04_verifier_v5 import verify

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / 'results/improvement-v1/Q04-lifecycle-qualification-v1.json'
FOLDER = ROOT / 'runtime/protocol-probes/q04-lifecycle-qualification-v1'
CASE = ROOT / 'improvement_cases/confirmatory/Q04'


def main():
    assert not RESULT.exists() and not FOLDER.exists(), 'Fresh immutable evidence namespace required'
    sources = broker.source_closure() | {Path(__file__).resolve()}
    sources |= {p for p in CASE.rglob('*') if p.is_file()}
    pins = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sources)}
    artifacts.atomic_json(RESULT.with_name('Q04-lifecycle-qualification-freeze-v1.json'),
        {'status': 'frozen_coordinator_plumbing_only', 'source_hashes': pins,
         'actor_allocated': False, 'private_inputs_exposed_to_actor': False,
         'native_binding_qualified': False, 'launch_qualified': False}, exclusive=True)
    value = {'status': 'running', 'started_at': time.time(), 'checks': {},
             'source_hashes': pins, 'actual_actor_allocated': False,
             'private_acceptance_grading': False, 'native_binding_qualified': False,
             'launch_qualified': False, 'superiority_proven': False,
             'first_error': None, 'cleanup_errors': []}
    artifacts.atomic_json(RESULT, value, exclusive=True)
    try:
        caps = runtime.create(FOLDER, CASE / 'repo',
            {job: 'Trusted coordinator plumbing qualification only. No model actor.' for job in runtime.JOBS},
            seconds=1200)
        before = runtime.load(FOLDER)
        try:
            runtime.command(FOLDER, 'pricing', caps['reservations'], 'true')
        except ValueError as error:
            assert str(error) == 'Wrong job/capability'
        else:
            raise AssertionError('Cross-role capability accepted')
        assert runtime.load(FOLDER)['jobs']['pricing']['commands'] == before['jobs']['pricing']['commands']
        value['checks']['wrong_capability_denied_before_command'] = True
        ro = runtime.command(FOLDER, 'root', caps['root'], 'printf invalid > lib/pricing.dart')
        assert ro['exit_code'] != 0
        assert artifacts.tree(FOLDER / 'root/repo') == json.loads((FOLDER / 'configuration.json').read_text())['base']['files']
        value['checks']['root_write_rejected'] = ro
        base = json.loads((FOLDER / 'configuration.json').read_text())['base']
        decisions = {}
        for job in ('pricing', 'reservations'):
            payload = (CASE / 'reference/lib' / (job + '.dart')).read_bytes()
            literal = base64.b64encode(payload).decode('ascii')
            command = "python3 -c \"import base64;from pathlib import Path;Path('lib/" + job + ".dart').write_bytes(base64.b64decode('" + literal + "'))\""
            result = runtime.command(FOLDER, job, caps[job], command)
            assert result['exit_code'] == 0
            broker.stop_owned(FOLDER, job)
            seal = artifacts.seal_worker(base, FOLDER / job / 'repo', job, FOLDER / 'artifacts' / (job + '.json'))
            decisions[job] = dict(seal, decision='accept', reason='Coordinator fixture bytes match pinned reference exactly; scoped delta verified by seal_worker.')
            value['checks'][job + '_scoped_seal'] = seal
        broker.stop_owned(FOLDER, 'root')
        transaction = artifacts.integrate(FOLDER / 'root/repo', base, decisions, FOLDER / 'integration')
        intent = json.loads(transaction.read_text())
        assert artifacts.tree(FOLDER / 'root/repo') == intent['expected_after']
        value['checks']['atomic_combined_integration'] = str(transaction)
        grading = verify(FOLDER / 'root/repo', FOLDER / 'public-verifier', runtime.load(FOLDER)['deadline'], expected_tests=1)
        value['checks']['pristine_public_verifier'] = grading
        assert grading['status'] == 'completed' and grading['pass'] and grading['removed'] and grading['source_unchanged']
        assert artifacts.tree(FOLDER / 'root/repo') == intent['expected_after']
        assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == expected for p, expected in pins.items())
        value['checks']['frozen_sources_unchanged'] = True
        value['status'] = 'pass_runtime_plumbing_only'
    except BaseException as error:
        value.update(status='failed', first_error={'type': type(error).__name__, 'message': str(error)})
    finally:
        if (FOLDER / 'state.json').exists():
            try:
                for job, row in runtime.load(FOLDER)['jobs'].items():
                    if row['status'] != 'removed':
                        broker.stop_owned(FOLDER, job, cleanup=True)
                        broker.archive_tmp(FOLDER, row['container'], job)
                runtime.cleanup(FOLDER)
                value['checks']['owned_jobs_removed'] = all(row['status'] == 'removed' for row in runtime.load(FOLDER)['jobs'].values())
            except BaseException as error:
                value['cleanup_errors'].append({'type': type(error).__name__, 'message': str(error)})
                value['status'] = 'failed'
        value['completed_at'] = time.time()
        value['elapsed_seconds'] = value['completed_at'] - value['started_at']
        artifacts.atomic_json(RESULT, value)
    print(json.dumps({k: value[k] for k in ('status', 'first_error', 'cleanup_errors', 'elapsed_seconds')}))
    return 0 if value['status'] == 'pass_runtime_plumbing_only' else 1


if __name__ == '__main__':
    raise SystemExit(main())
