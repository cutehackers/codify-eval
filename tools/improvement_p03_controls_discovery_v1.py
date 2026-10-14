"""First fixed-image qualification evidence, never a candidate comparison.

Observed full failure sets are retained rather than silently substituted for
prospective requirements. A separate review must qualify this evidence.
"""
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

CASE = ROOT / 'improvement_cases/pilot-expansion-v14/P03'
REVIEW = ROOT / 'results/improvement-v1/P03-contract-review-v3.json'
FOLDER = ROOT / 'runtime/protocol-probes/p03-v14-controls-discovery-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory():
    return {str((CASE / name).relative_to(ROOT)): value['sha256']
            for name, value in tree(CASE).items() if value['kind'] == 'file'}


def check():
    approved = json.loads(REVIEW.read_bytes())
    assert approved['verdict'] in {'pass', 'pass_static_contract'} and not approved['issues']
    pins = inventory()
    assert pins == {
        name: digest for name, digest in approved['source_hashes'].items() if name.startswith(str(CASE.relative_to(ROOT)) + '/')}
    for name, digest in approved['source_hashes'].items():
        assert sha(ROOT / name) == digest, name
    metadata = json.loads((CASE / 'metadata.json').read_bytes())
    assert metadata['expected_total_test_count'] == 22
    allowed = set(metadata['allowed_paths'])
    assert allowed == {'lib/archive_importer.dart', 'lib/manifest_codec.dart'}
    negative_root = CASE / 'negative'
    variants = sorted(path for path in negative_root.iterdir() if path.is_dir())
    assert len(variants) == 8
    assert not subprocess_live_owned()
    FOLDER.mkdir()
    receipt = FOLDER / 'receipt.json'
    value = {'status': 'running_discovery', 'started_at': time.time(),
             'source_hashes': pins, 'review_sha256': sha(REVIEW),
             'helper_sha256': sha(__file__), 'stages': [],
             'candidate_runs': False, 'superiority_proven': False,
             'complete_fixture_qualification': False, 'actor_tokens': 0}
    atomic_json(receipt, value, exclusive=True)
    deadline = time.time() + 900
    stages = [('reference', CASE / 'reference'), ('start', None)] + [(path.name, path) for path in variants]
    try:
        for label, overlay in stages:
            assert inventory() == pins
            source = FOLDER / (label + '-source')
            shutil.copytree(CASE / 'repo', source)
            if overlay:
                entries = {name for name, record in tree(overlay).items() if record['kind'] == 'file'}
                assert entries == allowed, label
                for name in entries:
                    shutil.copyfile(overlay / name, source / name)
            shutil.copytree(CASE / 'oracle/test', source / 'test', dirs_exist_ok=True)
            execution = FOLDER / (label + '-execution')
            result = verify(source, execution, deadline, 22, True)
            checks = [entry['exit_code'] for entry in result['checks']]
            log = result['checks'][1]['stdout'] if len(result['checks']) > 1 else ''
            failed, incomplete = failed_tests(log)
            assertions, nonassertion = assertion_failure_names(log, 22)
            machine = result.get('machine', {})
            common = (result['status'] == 'completed' and result.get('removed') is True
                      and result.get('source_unchanged') is True and not result.get('cleanup_errors')
                      and machine.get('well_formed') is True and machine.get('test_count') == 22
                      and not incomplete and not nonassertion
                      and sha(source / 'pubspec.lock') == sha(execution / 'repo/pubspec.lock'))
            valid = (common and checks == [0, 0, 0] and result['pass'] and not failed
                     if label == 'reference' else
                     common and checks == [0, 1, 0] and not result['pass'] and bool(failed)
                     and set(failed) == set(assertions))
            row = {'id': label, 'valid_complete_evidence': bool(valid),
                   'checks': checks, 'failed_tests': sorted(failed),
                   'assertion_failure_names': sorted(assertions), 'nonassertion_error': nonassertion,
                   'incomplete': incomplete, 'machine': machine,
                   'removed': result.get('removed'), 'source_unchanged': result.get('source_unchanged'),
                   'receipt_sha256': sha(execution / 'receipt.json')}
            value['stages'].append(row)
            atomic_json(receipt, value)
            print(json.dumps({'id': label, 'valid_complete_evidence': bool(valid), 'checks': checks,
                              'failed_count': len(failed), 'removed': result.get('removed')}), flush=True)
            assert valid, 'Incomplete or incidental failure evidence: ' + label
        value['status'] = 'complete_observed_failure_maps_pending_independent_review'
    except Exception as error:
        value.update(status='discovery_failed', first_error={'type': type(error).__name__, 'message': str(error)})
    finally:
        value['case_unchanged'] = inventory() == pins
        value['finished_at'] = time.time()
        atomic_json(receipt, value)
    return value


def subprocess_live_owned():
    import subprocess
    return bool(subprocess.check_output(['docker', 'ps', '-q', '--filter', 'name=codify-'], text=True, timeout=30).strip())


if __name__ == '__main__':
    result = check()
    print(json.dumps({'status': result['status'], 'case_unchanged': result['case_unchanged']}))
