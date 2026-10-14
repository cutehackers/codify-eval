"""Actual owned-container I/O/lifecycle control. Zero evaluated model actors."""
import json
import argparse
from pathlib import Path
import shutil
import subprocess
import time

import agent_io
import prepare
import improvement_q01_dialogue_pilot_v1 as pilot
from improvement_software_artifacts_v3 import atomic_json
from improvement_q04_verifier_v5 import verify

ROOT = pilot.ROOT
PHASE = 'control-probe-fresh-Q01-runtime-v1'
RUN = PHASE + '-Q01-C15-1'
REPORT = pilot.CONTROL


def run(revision=1):
    global PHASE, RUN, REPORT
    assert type(revision) is int and revision > 0
    PHASE = 'control-probe-fresh-Q01-runtime-v' + str(revision)
    RUN = PHASE + '-Q01-C15-1'
    REPORT = ROOT / ('results/improvement-v1/fresh-Q01-dialogue-runtime-control-v' + str(revision) + '.json')
    assert not REPORT.exists() and not (ROOT / 'runtime' / RUN).exists()
    assert not subprocess.check_output(['docker', 'ps', '-q', '--filter', 'name=codify-'], text=True, timeout=30).strip()
    started = time.time()
    value = {'status': 'RUNNING', 'started_at': started, 'model_actors_allocated': 0,
             'model_question_semantics_qualified': False, 'native_reply_delivery_qualified': False,
             'actual_container_IO_only': True, 'owned_containers_removed': False, 'checks': {}}
    atomic_json(REPORT, value, exclusive=True)
    metadata = None
    try:
        prepare.case_directory = pilot.case_directory
        prepare.prepare('Q01', 'C15', 1, PHASE)
        folder = ROOT / 'runtime' / RUN
        metadata = pilot.legacy.read(folder / 'run.json')
        identity = json.loads(subprocess.check_output(['docker', 'inspect', metadata['container']], text=True, timeout=30))[0]
        metadata.update(container_id=identity['Id'], started_at=started, agent_started_at=started, time_limit_seconds=1200)
        atomic_json(folder / 'run.json', metadata)
        before = pilot.solo.protected_tree(folder / 'repo')
        controls = folder / 'control-inputs'
        assert not any(controls.iterdir())
        policy = (pilot.CASE / 'private/question-evaluator.json').read_bytes()
        expected = pilot.core.reply_bytes(policy)
        assert expected.decode().strip() not in (folder / 'request.txt').read_text()
        value['checks']['initial_private_reply_absent_and_control_empty'] = True
        value['stop'] = pilot.stop_owned(metadata)
        received = pilot.write_reply_scalar(controls, policy)
        assert received == expected
        assert sorted(p.name for p in controls.iterdir()) == ['turn-2.txt']
        assert (controls / 'turn-2.txt').stat().st_mode & 0o777 == 0o444
        assert (controls / 'turn-2.txt').read_bytes() == expected
        try:
            pilot.write_reply_scalar(controls, policy)
        except AssertionError:
            value['checks']['second_staging_rejected'] = True
        else:
            raise AssertionError('Second staging must be rejected')
        subprocess.run(['docker', 'start', metadata['container']], capture_output=True, check=True, timeout=30)
        assert pilot.legacy.owned_identity(metadata)['Id'] == identity['Id']
        record = agent_io.run_command(RUN, pilot.core.READ, timeout=20)
        assert record['exit_code'] == 0 and record['output'] == expected.decode()
        value['reply_read_broker_receipt'] = record
        denied = agent_io.run_command(RUN, "printf changed > /eval-input/turn-2.txt", timeout=20)
        assert denied['exit_code'] != 0
        value['readonly_control_mount_negative_receipt'] = denied
        assert (controls / 'turn-2.txt').read_bytes() == expected
        assert pilot.solo.protected_tree(folder / 'repo') == before
        value['checks']['same_owned_container_empty_then_exact_readonly_scalar'] = True
        value['checks']['product_repo_unchanged'] = True
        pilot.stop_owned(metadata)
        value['product_cleanup'] = pilot.legacy.remove_owned(metadata)
        # Reference is root-only in a separate verification source, after the
        # transport product is removed. This is not an actor outcome.
        source = ROOT / ('runtime/protocol-probes/fresh-Q01-runtime-v' + str(revision) + '/reference-public-source')
        assert not source.exists()
        shutil.copytree(pilot.CASE / 'repo', source)
        shutil.copyfile(pilot.CASE / 'reference/lib/implementation.dart', source / 'lib/implementation.dart')
        execution = verify(source, source.parent / 'public-verification', started + 1200, expected_tests=1)
        value['public_reference_verification'] = execution
        assert pilot.solo.complete_observation(execution, 1) and execution['pass']
        value['owned_containers_removed'] = value['product_cleanup']['removed'] and execution['removed']
        value['checks']['actual_fixed_image_public_verifier_full1'] = True
        value['status'] = 'PASS'
    except Exception as error:
        value.update(status='FAIL', first_error={'type': type(error).__name__, 'message': str(error)})
    finally:
        if metadata is not None and not value.get('product_cleanup', {}).get('removed'):
            try:
                pilot.stop_owned(metadata)
                value['product_cleanup'] = pilot.legacy.remove_owned(metadata)
            except Exception as error:
                value['cleanup_error'] = {'type': type(error).__name__, 'message': str(error)}
        value['finished_at'] = time.time()
        files = [Path(__file__), ROOT / 'tools/improvement_q01_dialogue_pilot_v1.py',
                 ROOT / 'tools/agent_io.py', ROOT / 'tools/prepare.py', ROOT / 'tools/improvement_q04_verifier_v5.py']
        if metadata is not None:
            files.extend((ROOT / 'runtime' / RUN / name) for name in ('run.json', 'request.txt', 'commands.jsonl'))
        value['source_hashes'] = {str(p.relative_to(ROOT)): pilot.legacy.sha(p) for p in files if p.exists()}
        atomic_json(REPORT, value)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--revision', type=int, default=1)
    args = parser.parse_args()
    result = run(args.revision)
    print(json.dumps({'status': result['status'], 'owned_containers_removed': result['owned_containers_removed'],
                      'first_error': result.get('first_error'), 'report': str(REPORT)}))
    raise SystemExit(0 if result['status'] == 'PASS' else 1)
