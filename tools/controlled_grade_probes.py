"""Deterministic integration probes for controlled grading, with no actor/Docker run."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest.mock import patch

import dialogue_control
import finalize
import grade
import prepare

ROOT = prepare.ROOT
OUTPUT = ROOT / 'results/controlled-grade-gate-final2-probes-v3.6.json'
TOOLS = ('prepare.py', 'grade.py', 'dialogue_control.py', 'finalize.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def probes():
    checks = []

    def passed(name, mode):
        checks.append({'name': name, 'pass': True, 'mode': mode})

    def rejected(call, errors=(ValueError, OSError)):
        try:
            call()
        except errors:
            return
        raise AssertionError('Expected rejection')

    with tempfile.TemporaryDirectory(prefix='controlled-final-grade-') as temporary:
        root = Path(temporary)
        for name in TOOLS:
            target = root / 'tools' / name
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(ROOT / 'tools' / name, target)
        case = root / 'contract_cases/S03'
        (case / 'repo').mkdir(parents=True)
        (case / 'repo/seed.txt').write_text('seed\n')
        source = 'D-DELETE는 A를 선택한다. 확인 대화상자를 사용한다.'
        meta = {'type': 'contract', 'turn_requests': ['initial', source], 'decision_rules': {}}
        write(case / 'metadata.json', meta)
        write(root / 'runtime/image.json', {'image_id': 'sha256:probe-image'})
        mounts = {}
        invocations = []

        def fake_process(args, **options):
            invocations.append(args)
            if args[0] == 'git':
                return subprocess.CompletedProcess(args, 0, stdout=b'', stderr=b'')
            if args[:2] == ['docker', 'run']:
                container = args[args.index('--name') + 1]
                mounts[container] = next(value.split(':/eval-input:ro')[0]
                                         for value in args if value.endswith(':/eval-input:ro'))
                return subprocess.CompletedProcess(args, 0, stdout=b'probe-container\n', stderr=b'')
            if args[:2] == ['docker', 'inspect']:
                return subprocess.CompletedProcess(args, 0, stdout=json.dumps([{
                    'Id': 'probe-container', 'Image': 'sha256:probe-image', 'Mounts': [{
                        'Type': 'bind', 'Destination': '/eval-input',
                        'Source': mounts[args[2]], 'RW': False}]}]), stderr='')
            raise AssertionError('Unexpected subprocess: ' + repr(args))

        with patch.multiple(prepare, ROOT=root), patch.multiple(grade, ROOT=root), \
                patch.multiple(dialogue_control, ROOT=root), patch.multiple(finalize, ROOT=root), \
                patch('subprocess.run', side_effect=fake_process):
            rejected(lambda: prepare.prepare('S03', 'A', phase='auxiliary'))
            rejected(lambda: prepare.prepare('S03', 'A', phase='pilot'))
            assert not invocations and not (root / 'runtime/auxiliary-S03-A-1').exists()
            passed('missing_core_and_unknown_phase_reject_before_run_mutation', 'actual prepare preflight')

            core = root / 'results/frozen-core-v3.6.json'
            write(core, {})
            rejected(lambda: prepare.prepare('S03', 'A', phase='auxiliary'))
            cohort = root / 'results/controlled-dialogue-cohort-v3.6.json'
            write(cohort, {'runs': [{'run_id': 'auxiliary-S03-A-2'}]})
            rejected(lambda: prepare.prepare('S03', 'A', phase='auxiliary'))
            assert not invocations and not (root / 'runtime/auxiliary-S03-A-1').exists()
            passed('missing_cohort_and_unregistered_run_reject_without_container_or_files',
                   'actual prepare preflight, synthetic preregistration files')

            prepared = prepare.prepare('S03', 'A', repeat=2, phase='auxiliary')
            folder = root / 'runtime' / prepared['run_id']
            baseline = json.loads((folder / 'run.json').read_text())
            protocol = baseline['dialogue_protocol']
            assert baseline['evaluation_core'] == {'path': str(core), 'sha256': sha(core)}
            assert protocol['cohort'] == {'path': str(cohort), 'sha256': sha(cohort)}
            assert protocol['selector'] == 'turn_requests:1'
            assert protocol['input_sha256'] == hashlib.sha256(source.encode()).hexdigest()
            assert protocol['container_identity']['id'] == 'probe-container'
            assert protocol['container_identity']['mount']['RW'] is False
            assert not list((folder / 'control-inputs').iterdir())
            passed('prepare_pins_core_cohort_source_container_and_leaves_input_empty',
                   'actual prepare, mocked git/Docker only')

            def create_run(label):
                run_id = 'control-probe-grade-' + label
                run = deepcopy(baseline)
                run.update(run_id=run_id, phase='control-probe-grade', turns=[
                    {'request': 'initial', 'final': 'question'},
                    {'request': 'unqualified caller request', 'final': 'answer'}])
                write(root / 'runtime' / run_id / 'run.json', run)
                return run_id, run

            calls = []

            def behavior(case_path, repository, turns):
                calls.append(deepcopy(turns))
                return {'case_id': 'S03', 'type': 'contract', 'behavior_pass': True,
                        'scope_pass': True, 'overall_pass': True}

            with patch.object(grade, 'grade_contract', side_effect=behavior):
                run_id, run = create_run('missing-stage')
                result = grade.grade(run_id)  # Actual attest, no synthetic receipt.
                assert result['status'] == 'evaluation_error' and not calls
                assert result['control_audit']['category'] == 'control_integrity_fault'
                assert result['case_id'] == 'S03' and result['type'] == 'controlled_input_protocol'
                passed('actual_native_attest_missing_stage_blocks_behavior', 'actual attest and grade')

                run_id, run = create_run('removed-marker')
                run.pop('dialogue_protocol')
                write(root / 'runtime' / run_id / 'run.json', run)
                with patch.object(dialogue_control, 'attest', side_effect=AssertionError('must reject marker first')):
                    result = grade.grade(run_id)
                assert result['status'] == 'evaluation_error' and not calls
                assert result['control_audit']['category'] == 'control_protocol_invalid'
                passed('new_scripted_run_marker_removal_cannot_become_legacy', 'actual gate')

                run_id, run = create_run('tool-drift')
                run['dialogue_protocol']['tool_hashes']['tools/grade.py'] = 'changed'
                write(root / 'runtime' / run_id / 'run.json', run)
                with patch.object(dialogue_control, 'attest', side_effect=AssertionError('must reject tool drift first')):
                    result = grade.grade(run_id)
                assert result['status'] == 'evaluation_error' and not calls
                assert result['control_audit']['category'] == 'control_tool_drift'
                passed('prepared_tool_hash_drift_rejects_before_attestation_or_behavior', 'actual gate')

                for status, category in [('evaluation_error', 'controlled_receipt_unavailable'),
                                         ('fail', 'actor_control_read_missing')]:
                    run_id, run = create_run(status)
                    error = dialogue_control.ControlFault(status, category, 'probe outcome')
                    with patch.object(dialogue_control, 'attest', side_effect=error):
                        result = grade.grade(run_id)
                    assert result['status'] == status and result['behavior_pass'] is None and not calls
                    assert result['overall_pass'] is (False if status == 'fail' else None)
                    assert result['case_id'] == 'S03' and result['type'] == 'controlled_input_protocol'
                    assert json.loads((root / 'results' / run_id / 'controlled-input-audit.json').read_text()) == result['control_audit']
                    passed('typed_' + status + '_blocks_behavior_and_persists_audit', 'stub attest outcome, actual grade')

                run_id, run = create_run('qualified-source')
                qualified = {'status': 'pass', 'protocol': dialogue_control.PROTOCOL, 'run_id': run_id,
                             'input_sha256': protocol['input_sha256']}
                with patch.object(dialogue_control, 'attest', return_value=qualified):
                    result = grade.grade(run_id)
                assert result['status'] == 'pass' and len(calls) == 1
                assert calls[-1][1]['request'] == source and calls[-1][0]['request'] == 'initial'
                assert json.loads((root / 'runtime' / run_id / 'run.json').read_text())['turns'][1]['request'] == 'unqualified caller request'
                passed('qualified_exact_source_replaces_only_behavior_input_without_rewriting_evidence',
                       'stub valid attest, actual grade')
                audit_path = root / 'results' / run_id / 'controlled-input-audit.json'
                preserved = audit_path.read_bytes()
                with patch.object(dialogue_control, 'attest', return_value={**qualified, 'input_sha256': 'changed'}):
                    conflict = grade.grade(run_id)
                assert conflict['status'] == 'evaluation_error'
                assert conflict['control_audit']['category'] == 'control_audit_conflict'
                assert audit_path.read_bytes() == preserved and len(calls) == 1
                passed('conflicting_requalification_preserves_original_audit_and_blocks_behavior', 'actual audit persistence')

                run_id, run = create_run('downstream-failure')
                qualified = {**qualified, 'run_id': run_id}
                with patch.object(dialogue_control, 'attest', return_value=qualified), \
                        patch.object(grade, 'grade_contract', return_value={
                            'case_id': 'S03', 'type': 'contract', 'behavior_pass': False,
                            'scope_pass': True, 'overall_pass': False}):
                    result = grade.grade(run_id)
                assert result['status'] == 'fail' and result['behavior_pass'] is False
                assert result['control_audit']['status'] == 'pass'
                passed('qualified_receipt_preserves_downstream_behavior_failure', 'stub valid attest and behavior, actual grade')

                run_id, run = create_run('legacy')
                run.pop('dialogue_protocol'); run.pop('evaluation_core')
                write(root / 'runtime' / run_id / 'run.json', run)
                with patch.object(dialogue_control, 'attest', side_effect=AssertionError('legacy must skip')):
                    result = grade.grade(run_id)
                assert result['status'] == 'pass' and 'control_audit' not in result
                assert calls[-1][1]['request'] == 'unqualified caller request'
                passed('legacy_unmarked_runs_keep_existing_behavior', 'actual legacy grade path')

            # Execute both real W branches, replacing only their external app runner.
            import software_fixtures
            import w02_fixtures
            for case_id, runner in [('W01', software_fixtures), ('W02', w02_fixtures)]:
                run_id = 'control-probe-software-output-' + case_id
                case_root = root / 'software_cases' / case_id
                repository = root / 'runtime' / run_id / 'repo'
                (case_root / 'repo/lib').mkdir(parents=True)
                (case_root / 'repo/lib/main.dart').write_text('void main() {}\n')
                shutil.copytree(case_root / 'repo', repository)
                software_meta = {'type': 'software_creation' if case_id == 'W01' else 'software_integration'}
                choice = '완료한 항목은 영구 삭제하지 않고 보관하세요.'
                if case_id == 'W02':
                    software_meta['decision_rules'] = [{'reply': choice, 'required_before_implementation': True}]
                write(case_root / 'metadata.json', software_meta)
                run = deepcopy(baseline)
                run.update(run_id=run_id, case_id=case_id, phase='control-probe-software-output', turns=[
                    {'request': 'initial', 'final': 'first'},
                    {'request': 'incorrect caller request without the human choice', 'final': 'second'}])
                run.pop('evaluation_core')
                if case_id == 'W01':
                    run.pop('dialogue_protocol')
                    run['turns'] = run['turns'][:1]
                else:
                    run['dialogue_protocol']['selector'] = 'decision_rules:0:reply'
                    run['dialogue_protocol']['input_sha256'] = hashlib.sha256(choice.encode()).hexdigest()
                write(root / 'runtime' / run_id / 'run.json', run)
                expected_output = root / 'runtime/software-grading' / run_id
                external_calls = []

                def external_grade(repo, output, image):
                    external_calls.append((repo, output, image))
                    assert repo == repository and output == expected_output
                    assert image == 'sha256:probe-image'
                    output.mkdir(parents=True)
                    write(output / 'software-evidence.json', {'synthetic': True})
                    return {'status': 'pass', 'checks': [{'exit_code': 0, 'command': 'synthetic app probe'}]}

                qualified = {'status': 'pass', 'protocol': dialogue_control.PROTOCOL, 'run_id': run_id,
                             'input_sha256': hashlib.sha256(choice.encode()).hexdigest()}
                with patch.object(runner, 'grade_repo', side_effect=external_grade), \
                        patch.object(dialogue_control, 'attest', return_value=qualified):
                    result = grade.grade(run_id)
                canonical = root / 'results' / run_id
                assert len(external_calls) == 1 and result['status'] == 'review_pending'
                assert result['behavior_pass'] is True and result['scope_pass'] is True
                assert json.loads((canonical / 'grade.json').read_text()) == result
                assert (expected_output / 'software-evidence.json').exists()
                assert not (expected_output / 'grade.json').exists()
                if case_id == 'W02':
                    assert json.loads((canonical / 'controlled-input-audit.json').read_text()) == result['control_audit']
                    assert not (expected_output / 'controlled-input-audit.json').exists()
                    assert result['decision_evidence']['human_choice_received'] is True
                    assert result['decision_evidence']['source'] == 'qualified_controlled_source_and_native_receipt'
                    assert json.loads((root / 'runtime' / run_id / 'run.json').read_text())['turns'][1]['request'] == 'incorrect caller request without the human choice'
                else:
                    assert not (canonical / 'controlled-input-audit.json').exists()
                passed(case_id.lower() + '_software_runtime_output_and_canonical_grade_paths',
                       'actual W branch and scope/decision grading, stub external grade_repo' +
                       (', stub valid controlled attest' if case_id == 'W02' else ''))

            # Synthetic blind-review records exercise the real finalizer only.
            def final_fixture(label, audit):
                run_id = 'control-probe-final-' + label
                destination = root / 'results' / run_id
                external = {'run_id': run_id, 'case_id': 'S03', 'status': 'fail' if audit['status'] == 'fail' else 'pass',
                            'behavior_pass': None if audit['status'] == 'fail' else True,
                            'scope_pass': True, 'overall_pass': False if audit['status'] == 'fail' else True,
                            'control_audit': audit}
                write(destination / 'manifest.json', {'dialogue_protocol': protocol})
                write(destination / 'grade.json', external)
                write(destination / 'controlled-input-audit.json', audit)
                write(destination / 'turns.json', [])
                alias = 'blind-' + label
                bundle = root / 'runtime/blind-reviews' / alias
                write(bundle / 'evidence.json', {'synthetic': True})
                write(bundle / 'review.json', {'report_pass': True, 'evidence': ['synthetic probe judgment']})
                write(destination / 'review-bundle-map.json', {
                    'alias': alias, 'source_grade_sha256': sha(destination / 'grade.json'),
                    'source_turns_sha256': sha(destination / 'turns.json'), 'bundle_sha256': sha(bundle / 'evidence.json')})
                session = root / 'synthetic-reviewer.jsonl'
                session.write_text('\n'.join(json.dumps(event) for event in [
                    {'type': 'turn_context', 'payload': {'model': 'gpt-6.1-sol', 'effort': 'medium'}},
                    {'type': 'event_msg', 'payload': {'type': 'task_complete'}}]) + '\n')
                return run_id, destination, session

            pass_audit = {'status': 'pass', 'protocol': dialogue_control.PROTOCOL}
            for label in ('missing', 'changed', 'evaluation-error', 'other-fail'):
                audit = dict(pass_audit)
                if label == 'evaluation-error': audit['status'] = 'evaluation_error'
                if label == 'other-fail': audit.update(status='fail', category='control_integrity_fault')
                run_id, destination, session = final_fixture(label, audit)
                before = (destination / 'grade.json').read_bytes()
                if label == 'missing': (destination / 'controlled-input-audit.json').unlink()
                if label == 'changed': write(destination / 'controlled-input-audit.json', {**audit, 'changed': True})
                with patch.object(finalize, 'find_session', side_effect=AssertionError('must reject before reviewer access')):
                    rejected(lambda: finalize.finalize(run_id, '/synthetic-reviewer'))
                assert (destination / 'grade.json').read_bytes() == before
                passed('finalizer_rejects_' + label + '_audit_before_mutation', 'actual finalize, synthetic review fixture')

            run_id, destination, session = final_fixture('actor-read-missing', {
                'status': 'fail', 'protocol': dialogue_control.PROTOCOL, 'category': 'actor_control_read_missing'})
            with patch.object(finalize, 'find_session', return_value=session):
                result = finalize.finalize(run_id, '/synthetic-reviewer')
            final_grade = json.loads((destination / 'grade.json').read_text())
            assert result['status'] == 'fail' and final_grade['overall_pass'] is False
            assert final_grade['behavior_pass'] is None
            passed('finalizer_preserves_qualified_actor_protocol_failure', 'actual finalize, synthetic reviewer metadata')

            run_id, destination, session = final_fixture('pass', pass_audit)
            with patch.object(finalize, 'find_session', return_value=session):
                result = finalize.finalize(run_id, '/synthetic-reviewer')
            assert result['status'] == 'pass'
            assert json.loads((destination / 'grade.json').read_text())['overall_pass'] is True
            passed('finalizer_accepts_unchanged_qualified_pass_audit', 'actual finalize, synthetic reviewer metadata')

    return checks


if __name__ == '__main__':
    report = {'scope': 'Deterministic grade/prepare/finalize probes. No actors, Docker or H-case semantics.',
              'source_hashes': {'tools/' + name: sha(ROOT / 'tools' / name) for name in TOOLS},
              'probe_script_sha256': sha(Path(__file__)),
              'limits': ['Valid and typed-failure attest outcomes are stubbed to isolate integration.',
                         'The missing-stage case calls actual native attestation.',
                         'Docker/git identity and core/cohort documents are synthetic.',
                         'W01/W02 app grade_repo results are stubbed. Actual W dispatch, result paths, scope and W02 decision-source checks run.',
                         'Finalizer reviewer records are synthetic. No model receipt or cohort outcome is claimed.']}
    try:
        report.update(status='pass', checks=probes())
    except Exception as error:
        report.update(status='fail', error=f'{type(error).__name__}: {error}')
        write(OUTPUT, report)
        raise
    write(OUTPUT, report)
    print(json.dumps({'status': report['status'], 'checks': len(report['checks']), 'artifact': str(OUTPUT)}))
