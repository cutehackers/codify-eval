"""Post-native evaluator-only Q04 acceptance. Never an actor broker operation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time

import improvement_q04_artifacts_v1 as artifacts
import improvement_q04_broker_v1 as broker
from improvement_q04_verifier_v5 import COMMANDS, verify

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'improvement_cases/confirmatory/Q04'


def qualified_outcome(receipt):
    """Only a complete genuine eight-test lifecycle supports behavior grading."""
    checks = receipt.get('checks')
    machine = receipt.get('machine')
    complete = (receipt.get('status') == 'completed' and receipt.get('removed') is True
                and receipt.get('source_unchanged') is True and isinstance(checks, list)
                and len(checks) == 3 and isinstance(machine, dict)
                and machine.get('well_formed') is True and machine.get('test_count') == 8
                and type(machine.get('pass')) is bool
                and all(isinstance(check, dict) and check.get('inner_argv') == expected
                        and type(check.get('exit_code')) is int
                        and check['exit_code'] not in {124, 137, 143}
                        for check, expected in zip(checks, COMMANDS)))
    if not complete or checks[0]['exit_code'] != 0:
        return {'status': 'evaluation_error', 'observed_behavior_pass': None,
                'observed_software_checks_pass': None, 'overall_pass': None}
    return {'status': 'review_pending', 'observed_behavior_pass': machine['pass'],
            'observed_software_checks_pass': all(check['exit_code'] == 0 for check in checks)
                and machine['pass'], 'overall_pass': None}


def grade(name):
    folder = broker.folder_for(name)
    registration = broker.config(folder)
    state = broker.load(folder)
    assert state['phase'] == 'closed_protocol_as_of_seal', 'Original successful native closure required'
    assert set(state['native']) == set(broker.JOBS)
    for proof in state['native'].values():
        assert proof['usage']['native_completion_observed'], 'No grader before all product actors terminal'
    rstate = broker.runtime.load(folder)
    assert all(row['status'] == 'removed' for row in rstate['jobs'].values())
    for job, proof in state['bindings'].items():
        recorded = state['native'][job]
        assert hashlib.sha256(Path(proof['source']).read_bytes()).hexdigest() == recorded['usage']['source_sha256'], 'Late native append'
    intent = json.loads(Path(state['transaction']).read_text())
    assert artifacts.tree(folder / 'root/repo') == intent['expected_after']
    required = {Path(__file__).resolve(), CASE / 'oracle/test/acceptance_test.dart', CASE / 'metadata.json'}
    for path in required:
        name_in_freeze = str(path.relative_to(ROOT))
        assert name_in_freeze in registration['source_hashes'], 'Grader/oracle must be pinned before allocation'
        assert broker.sha(path) == registration['source_hashes'][name_in_freeze]
    target = folder / 'external-private-grade-v1'
    assert not target.exists(), 'No private grader retries or overwritten outcome'
    target.mkdir()
    result_path = target / 'grade.json'
    value = {'status': 'started', 'started_at': time.time(), 'run_name': name,
             'private_grading_allocated': False, 'actor_inputs_public_only': True,
             'native_closure_sha256': broker.sha(folder / 'broker-state.json'),
             'product_tokens_as_of_seal': state['product_tokens_as_of_seal'],
             'product_wall_seconds': state['wall_seconds'],
             'superiority_proven': False, 'complete_final_cost': False,
             'independent_outcome_review_required': True, 'first_error': None}
    artifacts.atomic_json(result_path, value, exclusive=True)
    try:
        source = target / 'source'
        shutil.copytree(folder / 'root/repo', source)
        acceptance = source / 'test/acceptance_test.dart'
        assert not acceptance.exists(), 'Acceptance path was not public actor input'
        shutil.copyfile(CASE / 'oracle/test/acceptance_test.dart', acceptance)
        value['oracle_sha256'] = broker.sha(acceptance)
        value['private_grading_allocated'] = True
        artifacts.atomic_json(result_path, value)
        receipt = verify(source, target / 'verifier', value['started_at'] + 600, expected_tests=8)
        value['verification_receipt'] = receipt
        assert artifacts.tree(folder / 'root/repo') == intent['expected_after'], 'Sealed product changed'
        value.update(qualified_outcome(receipt))
    except BaseException as error:
        value.update(status='evaluation_error', first_error={'type': type(error).__name__, 'message': str(error)},
                     observed_behavior_pass=None, observed_software_checks_pass=None, overall_pass=None)
    finally:
        value['completed_at'] = time.time()
        value['private_grading_elapsed_seconds'] = value['completed_at'] - value['started_at']
        value['allocation_through_grade_seconds'] = value['completed_at'] - rstate['started_at']
        artifacts.atomic_json(result_path, value)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    result = grade(parser.parse_args().run)
    print(json.dumps({k: result[k] for k in ('status', 'overall_pass', 'first_error')}))
