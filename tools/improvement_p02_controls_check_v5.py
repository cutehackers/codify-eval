"""Prospective v10 fixture qualification. Exact closed traces and failure sets."""
import hashlib
import json
from pathlib import Path
import shutil
import time
from prepare import ROOT
from improvement_p02_verifier_v3 import verify
from improvement_qualify_v3 import failed_tests
from improvement_p02_assertion_classifier_v1 import assertion_failure_names
from improvement_software_artifacts_v3 import atomic_json, tree


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def case_inventory(case):
    return {str((case/name).relative_to(ROOT)): record['sha256']
            for name, record in tree(case).items() if record['kind'] == 'file'}


def check():
    review = ROOT/'results/improvement-v1/pilot-P02-complete-failure-map-construction-review-v1.json'
    prelaunch = ROOT/'results/improvement-v1/P02-controls-check-v5-prelaunch-review-v1.json'
    construction, approved = read(review), read(prelaunch)
    assert construction['verdict'] == 'eligible_for_fresh_fixed_image_gold_start_and_eight_controls'
    assert not construction['issues'] and approved['verdict'] == 'pass' and not approved['issues']
    case = ROOT/'improvement_cases/pilot-expansion-v11/P02'
    pins = construction['fullcurrentv11inventory']
    assert case_inventory(case) == pins
    for inventory in (construction['source_hashes'], approved['sourcepins'], approved['evidencepins']):
        for name, digest in inventory.items():
            assert sha(ROOT/name) == digest, name
    manifest = read(case/'negative-manifest.json')
    assert len(manifest['controls']) == 8
    folder = ROOT/'runtime/protocol-probes/p02-v11-controls-check-v5'
    folder.mkdir()
    receipt = folder/'receipt.json'
    value = {'status': 'running', 'purpose': 'fresh_reference_start_eight_controls',
             'source_inventory': pins, 'construction_review_sha256': sha(review),
             'prelaunch_review_sha256': sha(prelaunch), 'stages': [], 'helper_sha256': sha(__file__),
             'previous_failures_preserved': True, 'candidate_runs': False, 'model_tokens': 0,
             'complete_fixture_qualification': False, 'superiority_proven': False, 'started_at': time.time()}
    atomic_json(receipt, value, exclusive=True)
    deadline = time.time()+900
    try:
        stages = [{'id': 'reference', 'overlay': 'reference', 'discriminating_test_names': []},
                  {'id': 'start', 'overlay': None, 'discriminating_test_names': []}] + manifest['controls']
        for control in stages:
            label = control['id']
            assert label.replace('_', '').isalnum()
            assert case_inventory(case) == pins
            source = folder/(label+'-source')
            shutil.copytree(case/'repo', source)
            if control['overlay']:
                overlay = (case/control['overlay']).resolve()
                assert overlay.is_relative_to(case)
                artifacts = {name: record for name,record in tree(overlay).items() if record['kind'] == 'file'}
                assert set(artifacts) == {'lib/event_processor.dart', 'lib/checkpoint_codec.dart'}
                if label != 'reference':
                    assert {name: record['sha256'] for name,record in artifacts.items()} == control['files_sha256']
                for name in artifacts:
                    shutil.copyfile(overlay/name, source/name)
            shutil.copytree(case/'oracle/test', source/'test', dirs_exist_ok=True)
            destination = folder/(label+'-execution')
            result = verify(source, destination, deadline, 24, True)
            checks = [entry['exit_code'] for entry in result['checks']]
            log = result['checks'][1]['stdout'] if len(result['checks']) > 1 else ''
            names, incomplete = failed_tests(log)
            assertions, nonassertion = assertion_failure_names(log)
            parsed = result.get('machine', {})
            row = {'id': label, 'status': result['status'], 'checks': checks,
                   'test_count': parsed.get('test_count'), 'well_formed': parsed.get('well_formed', False),
                   'protocol_errors': parsed.get('protocol_errors'), 'failed_tests': sorted(names),
                   'assertion_failure_names': sorted(assertions), 'nonassertion_error': nonassertion,
                   'incomplete': incomplete, 'removed': result.get('removed'),
                   'source_unchanged': result.get('source_unchanged'),
                   'mandatory_discriminators': control['discriminating_test_names'],
                   'expected': control.get('expected_failure_test_names', []),
                   'receipt_sha256': sha(destination/'receipt.json'),
                   'lock_unchanged': sha(source/'pubspec.lock') == sha(destination/'repo/pubspec.lock')}
            common = (row['status'] == 'completed' and row['removed'] and row['source_unchanged']
                      and row['lock_unchanged'] and row['test_count'] == 24 and row['well_formed']
                      and not incomplete and not nonassertion)
            if label == 'reference':
                row['qualified'] = bool(common and checks == [0,0,0] and result['pass'] and not names and not assertions)
            else:
                row['qualified'] = bool(common and checks == [0,1,0] and not result['pass'] and names
                                        and set(names) == set(assertions))
                if label != 'start':
                    row['qualified'] = (row['qualified'] and bool(row['expected'])
                                        and set(row['mandatory_discriminators']) <= set(row['expected'])
                                        and set(names) == set(row['expected']))
            value['stages'].append(row)
            atomic_json(receipt, value)
            print(json.dumps({'id': label, 'qualified': row['qualified'], 'checks': checks,
                              'failed_count': len(names), 'removed': row['removed']}), flush=True)
            assert row['qualified'], 'Fixture stage did not qualify: '+label
        value['status'] = 'all_stages_passed_pending_independent_qualification_review'
    except Exception as error:
        value.update(status='fixture_qualification_failed', first_error={'type': type(error).__name__, 'message': str(error)})
    finally:
        value['case_unchanged'] = case_inventory(case) == pins
        value['finished_at'] = time.time()
        atomic_json(receipt, value)
        print(json.dumps({'status': value['status'], 'case_unchanged': value['case_unchanged']}), flush=True)
    return value


if __name__ == '__main__':
    check()
