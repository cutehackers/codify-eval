"""Prospective P02 v9 controls check. Preserve the failed v8 name mapping."""
import hashlib
import json
from pathlib import Path
import shutil
import time

from prepare import ROOT
from improvement_p02_verifier_v1 import verify
from improvement_qualify_v3 import failed_tests
from improvement_pilot_qualify_v3 import assertion_failure_names


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def check():
    pre = ROOT / 'results/improvement-v1/pilot-P02-verifier-prelaunch-review-v1.json'
    review = ROOT / 'results/improvement-v1/pilot-P02-negative-controls-review-v3.json'
    executor, construction = read(pre), read(review)
    assert executor['verdict'] == 'pass'
    assert construction['verdict'] == 'eligible_for_fresh_actual_fixed_image_qualification_only'
    assert not executor['issues'] and not construction['issues']
    pins = construction['fullinventory']
    for inventory in (executor['sourcepins'], executor['evidencepins'], construction['source_hashes'], pins):
        for name, digest in inventory.items():
            assert sha(ROOT / name) == digest, name
    case = ROOT / 'improvement_cases/pilot-expansion-v9/P02'
    previous = ROOT / 'improvement_cases/pilot-expansion-v6/P02'
    for prefix in ('repo', 'oracle', 'reference'):
        for path in (previous / prefix).rglob('*'):
            if path.is_file():
                assert sha(path) == sha(case / path.relative_to(previous))
    assert sha(case / 'task.md') == sha(previous / 'task.md')
    gold_path = ROOT / 'runtime/protocol-probes/p02-v6-independent-reference-check-v1/receipt.json'
    assert read(gold_path)['status'] == 'reference_checks_passed_not_full_fixture_qualification'
    manifest = read(case / 'negative-manifest.json')
    assert len(manifest['controls']) == 8
    folder = ROOT / 'runtime/protocol-probes/p02-v9-controls-check-v2'
    folder.mkdir()
    receipt = folder / 'receipt.json'
    value = {'status': 'running', 'purpose': 'start_and_single_defect_fixed_image_checks',
             'source_inventory': pins, 'construction_review_sha256': sha(review),
             'executor_prelaunch_sha256': sha(pre), 'reference_receipt_sha256': sha(gold_path),
             'reference_v6_v9_behavior_sources_equivalent': True, 'stages': [],
             'helper_sha256': sha(__file__), 'classifier_sha256': {
                 name: sha(ROOT / 'tools' / name) for name in
                 ('improvement_qualify_v3.py', 'improvement_pilot_qualify_v3.py')},
             'previous_mapping_failure_retained': 'runtime/protocol-probes/p02-v8-controls-check-v1/receipt.json',
             'candidate_runs': False, 'model_tokens': 0, 'complete_fixture_qualification': False,
             'superiority_proven': False, 'started_at': time.time()}

    def persist():
        receipt.write_text(json.dumps(value, indent=2) + '\n')

    persist()
    deadline = time.time() + 600
    try:
        controls = [{'id': 'start', 'overlay': None, 'discriminating_test_names': []}] + manifest['controls']
        for control in controls:
            label = control['id']
            assert label.replace('_', '').isalnum()
            source = folder / (label + '-source')
            shutil.copytree(case / 'repo', source)
            if control['overlay']:
                overlay = (case / control['overlay']).resolve()
                assert overlay.is_relative_to(case / 'negative')
                files = {str(path.relative_to(overlay)): path for path in overlay.rglob('*') if path.is_file()}
                assert set(files) == {'lib/event_processor.dart', 'lib/checkpoint_codec.dart'}
                for name, path in files.items():
                    shutil.copyfile(path, source / name)
            shutil.copytree(case / 'oracle/test', source / 'test', dirs_exist_ok=True)
            destination = folder / (label + '-execution')
            result = verify(source, destination, deadline, 24, True)
            log = result['checks'][1]['stdout'] if len(result['checks']) > 1 else ''
            names, incomplete = failed_tests(log)
            assertions, nonassertion = assertion_failure_names(log)
            row = {'id': label, 'status': result['status'],
                   'test_count': result.get('machine', {}).get('test_count'),
                   'checks': [entry['exit_code'] for entry in result['checks']],
                   'failed_tests': sorted(names), 'assertion_failure_names': sorted(assertions),
                   'nonassertion_error': nonassertion, 'incomplete': incomplete,
                   'removed': result.get('removed'), 'source_unchanged': result.get('source_unchanged'),
                   'expected': control['discriminating_test_names'],
                   'receipt_sha256': sha(destination / 'receipt.json'),
                   'lock_unchanged': sha(source / 'pubspec.lock') == sha(destination / 'repo/pubspec.lock')}
            row['qualified'] = (row['status'] == 'completed' and row['checks'] == [0, 1, 0]
                                and row['removed'] and row['source_unchanged'] and row['lock_unchanged']
                                and row['test_count'] == 24 and bool(names) and not incomplete)
            if label != 'start':
                row['qualified'] = (row['qualified'] and not nonassertion
                                    and set(row['expected']) <= set(names) and set(names) <= assertions)
            value['stages'].append(row)
            persist()
            print({'id': label, 'qualified': row['qualified'], 'checks': row['checks'],
                   'failed_count': len(names), 'removed': row['removed']}, flush=True)
            if not row['qualified']:
                raise ValueError('Control did not qualify: ' + label)
            assert all(sha(ROOT / name) == digest for name, digest in pins.items())
        value['status'] = 'all_controls_passed_pending_independent_qualification_review'
    except Exception as error:
        value.update(status='control_qualification_failed', first_error={
            'type': type(error).__name__, 'message': str(error)})
    finally:
        value['case_unchanged'] = all(sha(ROOT / name) == digest for name, digest in pins.items())
        value['finished_at'] = time.time()
        persist()
        print({'status': value['status'], 'case_unchanged': value['case_unchanged']}, flush=True)
    return value


if __name__ == '__main__':
    check()
