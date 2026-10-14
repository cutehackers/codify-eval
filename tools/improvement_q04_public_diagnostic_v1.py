"""Separate post-hoc diagnostic. Original pilot grades remain untouched."""
import hashlib
import json
from pathlib import Path
import shutil
import time

from improvement_q04_artifacts_v1 import atomic_json, tree
from improvement_q04_verifier_v5 import COMMANDS, verify

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / 'results/improvement-v1/Q04-public-contract-diagnostic-v1'
DEST = ROOT / 'runtime/protocol-probes/q04-public-contract-diagnostic-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not DEST.exists(), 'No overwritten diagnostic or silent retries'
    manifest = json.loads((TESTS / 'manifest.json').read_text())
    test = TESTS / 'public_contract_diagnostic_test.dart'
    assert sha(test) == manifest['test_sha256']
    assert manifest['test_count'] == 29
    for name, digest in manifest['source_sha256'].items():
        assert sha(ROOT / name) == digest
    sources = {
        condition: ROOT / f'runtime/protocol-probes/q04-broker-v1-pilot-{condition.lower()}-1/root/repo'
        for condition in ('A', 'C0', 'C14')
    }
    before = {condition: tree(source) for condition, source in sources.items()}
    freeze = {
        'status': 'frozen_before_diagnostic_allocation',
        'evidence_class': 'post_hoc_exploratory_not_primary_holdout',
        'original_pilot_grades_changed': False,
        'expected_tests': 30,
        'expected_tests_basis': '29 diagnostic tests plus unchanged public smoke test',
        'runner_sha256': sha(Path(__file__)),
        'test_sha256': sha(test),
        'manifest_sha256': sha(TESTS / 'manifest.json'),
        'verifier_sha256': sha(ROOT / 'tools/improvement_q04_verifier_v5.py'),
        'public_sources': manifest['source_sha256'],
        'sealed_source_trees': before,
        'review': 'Root checked public contract, exact entry points, independent BigInt expectations, representable outputs, no unspecified overflow policy',
        'started_at': time.time(),
        'conditions': ['A', 'C0', 'C14'],
        'superiority_proven': False,
    }
    atomic_json(TESTS / 'execution-freeze-v1.json', freeze, exclusive=True)
    DEST.mkdir()
    outcomes = {}
    for condition, source in sources.items():
        assert tree(source) == before[condition]
        copy = DEST / condition / 'source'
        shutil.copytree(source, copy)
        target = copy / 'test/public_contract_diagnostic_test.dart'
        assert not target.exists()
        shutil.copyfile(test, target)
        receipt = verify(copy, DEST / condition / 'verifier', time.time() + 600, expected_tests=30)
        checks = receipt.get('checks', [])
        machine = receipt.get('machine', {})
        valid = (receipt.get('status') == 'completed'
                 and receipt.get('removed') is True
                 and receipt.get('source_unchanged') is True
                 and machine.get('well_formed') is True
                 and machine.get('test_count') == 30
                 and len(checks) == 3
                 and all(c.get('inner_argv') == command
                         and type(c.get('exit_code')) is int
                         and c['exit_code'] not in {124, 137, 143}
                         for c, command in zip(checks, COMMANDS))
                 and checks[0]['exit_code'] == 0)
        assert tree(source) == before[condition], 'Sealed original changed'
        outcomes[condition] = {
            'evaluation_valid': valid,
            'behavior_pass': machine.get('pass') if valid else None,
            'software_checks_pass': receipt['pass'] if valid else None,
            'receipt': str(DEST / condition / 'verifier/receipt.json'),
            'receipt_sha256': sha(DEST / condition / 'verifier/receipt.json'),
            'original_source_unchanged': True,
            'removed': receipt.get('removed'),
        }
        print(json.dumps({condition: outcomes[condition]}), flush=True)
    result = {'status': 'observed_pending_independent_review',
              'evidence_class': freeze['evidence_class'], 'outcomes': outcomes,
              'original_pilot_grades_changed': False,
              'superiority_proven': False, 'completed_at': time.time()}
    atomic_json(TESTS / 'execution-summary-v1.json', result, exclusive=True)


if __name__ == '__main__':
    main()
