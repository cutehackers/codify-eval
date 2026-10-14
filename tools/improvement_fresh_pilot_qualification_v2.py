"""Revised fixture qualification with explicit reuse of identical executed inputs.

Intentional starting stubs are informational, never negative discriminators.
Original qualification receipts and frozen fixtures remain immutable.
"""
import hashlib
import json
from pathlib import Path
import shutil
import time

import improvement_fresh_pilot_qualification_v1 as prior
from improvement_q04_artifacts_v1 import atomic_json, tree
from improvement_q04_verifier_v5 import IMAGE, verify

ROOT = prior.ROOT
CASES = ROOT / 'improvement_cases/fresh-pilot-v2'
OLD = ROOT / 'results/improvement-v1/fresh-pilot-v1-qualification'
RESULTS = ROOT / 'results/improvement-v1/fresh-pilot-v2-qualification'
RUNTIME = ROOT / 'runtime/protocol-probes/fresh-pilot-v2-qualification'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def intentional_stub(receipt, count):
    classified = prior.classify(receipt, count)
    if not classified['valid_behavior_observation']:
        return False
    if classified['positive_checks_pass']:
        return True
    errors = []
    for line in receipt['checks'][1]['stdout'].splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get('type') == 'error':
            errors.append(event)
    return (receipt['checks'][1]['exit_code'] == 1 and bool(errors)
            and all(e.get('isFailure') is False
                    and e.get('error') == 'UnimplementedError: Implement the task contract'
                    for e in errors))


def main():
    assert not RESULTS.exists() and not RUNTIME.exists()
    old_freeze_path = OLD / 'preallocation-freeze-v1.json'
    old_freeze = json.loads(old_freeze_path.read_text())
    old_summary = json.loads((OLD / 'summary-v1.json').read_text())
    assert old_summary['status'] == 'observed_pending_independent_semantic_review'
    assert old_freeze['image_id'] == IMAGE
    for name, digest in old_freeze['source_hashes'].items():
        assert sha(ROOT / name) == digest, 'Original frozen source changed: ' + name
    files = sorted(p for p in CASES.rglob('*') if p.is_file())
    assert files
    pins = {str(p.relative_to(ROOT)): sha(p) for p in files}
    # Reuse the reviewed AST closure traversal with this new entry point.
    import ast
    pending, found = [Path(__file__).resolve()], set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_bytes())):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                if name:
                    local = ROOT / 'tools' / (name.split('.')[0] + '.py')
                    if local.is_file() and local not in found:
                        pending.append(local)
    for path in found | {old_freeze_path, OLD / 'summary-v1.json', ROOT / 'AGENTS.md',
                         ROOT / 'docs/improvement-spec-v1.md', ROOT / 'runtime/image.json'}:
        pins[str(path.relative_to(ROOT))] = sha(path)
    # Seal every original receipt before deciding whether its input is identical.
    original_receipts = {}
    for case_id in ('S01', 'S02', 'Q01', 'Q02'):
        metadata = json.loads((CASES / case_id / 'metadata.json').read_text())
        public_count = metadata['expected_total_test_count'] - metadata['expected_private_test_count']
        rows = old_summary['cases'][case_id]['rows']
        assert set(rows) == {'starting_public', 'starting_full', 'reference', 'N01', 'N02', 'N03', 'N04'}
        for label, row in rows.items():
            path = ROOT / f'runtime/protocol-probes/fresh-pilot-v1-qualification/{case_id}/{label}/verifier/receipt.json'
            assert Path(row['receipt']).resolve() == path.resolve()
            assert sha(path) == row['receipt_sha256'], 'Original receipt replaced'
            receipt = json.loads(path.read_text())
            count = public_count if label == 'starting_public' else metadata['expected_total_test_count']
            assert receipt['image_id'] == IMAGE and receipt['identity']['Image'] == IMAGE
            assert receipt['expected_nonloading_tests'] == count
            assert receipt['machine']['test_count'] == count
            assert receipt['source_path'] == str(path.parent.parent / 'source')
            original_receipts[(case_id, label)] = (receipt, path)
            pins[str(path.relative_to(ROOT))] = sha(path)
    RESULTS.mkdir()
    atomic_json(RESULTS / 'preallocation-freeze-v1.json', {
        'status': 'frozen_before_revision_qualification', 'source_hashes': pins,
        'image_id': IMAGE, 'started_at': time.time(), 'models_allocated': False,
        'reuse_policy': 'Exact same input tree bytes/modes, fixed image and unchanged verifier closure; reused evidence explicitly labeled',
        'starting_policy': 'Known intentional unimplemented starting code is informational, never a seeded-negative discriminator',
        'superiority_proven': False}, exclusive=True)
    all_outcomes = {}
    for case_id in ('S01', 'S02', 'Q01', 'Q02'):
        case = CASES / case_id
        metadata = json.loads((case / 'metadata.json').read_text())
        public_count = metadata['expected_total_test_count'] - metadata['expected_private_test_count']
        total = metadata['expected_total_test_count']
        assert type(public_count) is int and public_count > 0 and total > public_count
        negatives = sorted((case / 'negative').iterdir())
        assert len(negatives) >= 3 and all(p.is_dir() for p in negatives)
        rows = [('starting_public', None, False, public_count, 'informational_start'),
                ('starting_full', None, True, total, 'informational_start'),
                ('reference', case / 'reference/lib/implementation.dart', True, total, 'positive_control')]
        rows += [(p.name, p / 'lib/implementation.dart', True, total, 'negative_control') for p in negatives]
        outcomes = {}
        before = tree(case)
        for label, implementation, hidden, count, purpose in rows:
            assert all(sha(ROOT / name) == digest for name, digest in pins.items())
            source = RUNTIME / case_id / label / 'source'
            shutil.copytree(case / 'repo', source)
            if implementation:
                shutil.copyfile(implementation, source / 'lib/implementation.dart')
            if hidden:
                shutil.copyfile(case / 'oracle/test/acceptance_test.dart', source / 'test/acceptance_test.dart')
            old_receipt, old_receipt_path = original_receipts[(case_id, label)]
            if tree(source) == old_receipt['source_before']:
                receipt, receipt_path = old_receipt, old_receipt_path
                origin = 'reused_original_identical_input_fixture_observation'
            else:
                receipt_path = RUNTIME / case_id / label / 'verifier/receipt.json'
                receipt = verify(source, receipt_path.parent, time.time() + 600, expected_tests=count)
                origin = 'new_changed_input_fixture_observation'
            classified = prior.classify(receipt, count)
            qualified = (intentional_stub(receipt, count) if purpose == 'informational_start'
                         else classified['positive_checks_pass'] if purpose == 'positive_control'
                         else classified['genuine_assertion_negative'])
            observation = {**classified, 'purpose': purpose, 'qualified': qualified,
                           'evidence_origin': origin, 'receipt': str(receipt_path),
                           'receipt_sha256': sha(receipt_path),
                           'current_input_tree': tree(source),
                           'input_matches_observed_receipt': tree(source) == receipt['source_before']}
            assert observation['input_matches_observed_receipt']
            assert tree(case) == before
            outcomes[label] = observation
            atomic_json(RESULTS / f'{case_id}-{label}-v1.json', observation, exclusive=True)
            print(json.dumps({'case': case_id, 'variant': label, 'qualified': qualified,
                              'purpose': purpose, 'evidence_origin': origin}), flush=True)
        all_outcomes[case_id] = {'rows': outcomes,
                                 'behavior_qualified': all(v['qualified'] for v in outcomes.values()),
                                 'semantic_review_required': True}
    atomic_json(RESULTS / 'summary-v1.json', {
        'status': 'observed_pending_independent_semantic_review', 'cases': all_outcomes,
        'models_allocated': False, 'original_v1_evidence_unchanged': True,
        'superiority_proven': False, 'completed_at': time.time()}, exclusive=True)


if __name__ == '__main__':
    main()
