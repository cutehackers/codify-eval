"""Qualify newly authored fixtures before exposing public inputs to actors."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import time

from improvement_q04_artifacts_v1 import atomic_json, tree
from improvement_q04_verifier_v5 import COMMANDS, IMAGE, verify

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'improvement_cases/fresh-pilot-v1'
RESULTS = ROOT / 'results/improvement-v1/fresh-pilot-v1-qualification'
RUNTIME = ROOT / 'runtime/protocol-probes/fresh-pilot-v1-qualification'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_closure():
    pending, found = [Path(__file__).resolve()], set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_bytes())):
            names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                if name:
                    local = ROOT / 'tools' / (name.split('.')[0] + '.py')
                    if local.is_file() and local not in found:
                        pending.append(local)
    return found


def classify(receipt, expected):
    checks = receipt.get('checks', [])
    machine = receipt.get('machine', {})
    valid = (receipt.get('status') == 'completed'
             and receipt.get('source_unchanged') is True
             and receipt.get('removed') is True
             and machine.get('well_formed') is True
             and machine.get('test_count') == expected
             and len(checks) == 3
             and all(c.get('inner_argv') == command
                     and type(c.get('exit_code')) is int
                     and c['exit_code'] not in {124, 137, 143}
                     for c, command in zip(checks, COMMANDS))
             and checks[0]['exit_code'] == 0
             and checks[2]['exit_code'] == 0)
    errors, ends = [], []
    for line in checks[1]['stdout'].splitlines() if len(checks) == 3 else []:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get('type') == 'error':
            errors.append(event)
        elif event.get('type') == 'testDone':
            ends.append(event)
    genuine_negative = (valid and machine.get('pass') is False
                        and checks[1]['exit_code'] == 1 and bool(errors)
                        and all(e.get('isFailure') is True for e in errors)
                        and all(e.get('result') in {'success', 'failure'} for e in ends)
                        and any(e.get('result') == 'failure' for e in ends))
    positive = valid and machine.get('pass') is True and checks[1]['exit_code'] == 0
    return {'valid_behavior_observation': valid,
            'behavior_pass': machine.get('pass') if valid else None,
            'software_pass': receipt.get('pass') if valid else None,
            'genuine_assertion_negative': genuine_negative,
            'positive_checks_pass': positive,
            'removed': receipt.get('removed'),
            'source_unchanged': receipt.get('source_unchanged')}


def main():
    assert not RESULTS.exists() and not RUNTIME.exists()
    files = sorted(p for p in CASES.rglob('*') if p.is_file())
    assert files
    pins = {str(p.relative_to(ROOT)): sha(p) for p in files}
    for path in source_closure() | {ROOT / 'AGENTS.md', ROOT / 'docs/improvement-spec-v1.md',
                                   ROOT / 'runtime/image.json'}:
        pins[str(path.relative_to(ROOT))] = sha(path)
    RESULTS.mkdir()
    atomic_json(RESULTS / 'preallocation-freeze-v1.json', {
        'status': 'frozen_before_fixture_qualification', 'source_hashes': pins,
        'image_id': IMAGE, 'models_allocated': False,
        'superiority_proven': False, 'started_at': time.time()}, exclusive=True)
    all_outcomes = {}
    for case_id in ('S01', 'S02', 'Q01', 'Q02'):
        case = CASES / case_id
        metadata = json.loads((case / 'metadata.json').read_text())
        public_count = metadata['expected_total_test_count'] - metadata['expected_private_test_count']
        assert type(public_count) is int and public_count > 0
        total = metadata['expected_total_test_count']
        assert total > public_count
        negatives = sorted((case / 'negative').iterdir())
        assert len(negatives) >= 3 and all(p.is_dir() for p in negatives)
        rows = [('starting_public', None, False, public_count, True),
                ('starting_full', None, True, total, False),
                ('reference', case / 'reference/lib/implementation.dart', True, total, True)]
        rows += [(p.name, p / 'lib/implementation.dart', True, total, False) for p in negatives]
        outcomes = {}
        original = tree(case)
        for label, implementation, hidden, count, expected_pass in rows:
            assert all(sha(ROOT / name) == digest for name, digest in pins.items())
            source = RUNTIME / case_id / label / 'source'
            shutil.copytree(case / 'repo', source)
            if implementation:
                shutil.copyfile(implementation, source / 'lib/implementation.dart')
            if hidden:
                target = source / 'test/acceptance_test.dart'
                assert not target.exists()
                shutil.copyfile(case / 'oracle/test/acceptance_test.dart', target)
            receipt_folder = RUNTIME / case_id / label / 'verifier'
            receipt = verify(source, receipt_folder, time.time() + 600, expected_tests=count)
            observation = classify(receipt, count)
            observation.update(expected_behavior_pass=expected_pass,
                               qualified=(observation['positive_checks_pass'] if expected_pass
                                          else observation['genuine_assertion_negative']),
                               receipt=str(receipt_folder / 'receipt.json'),
                               receipt_sha256=sha(receipt_folder / 'receipt.json'))
            outcomes[label] = observation
            assert tree(case) == original
            atomic_json(RESULTS / f'{case_id}-{label}-v1.json', observation, exclusive=True)
            print(json.dumps({'case': case_id, 'variant': label, **observation}), flush=True)
        all_outcomes[case_id] = {'rows': outcomes,
                                 'behavior_qualified': all(v['qualified'] for v in outcomes.values()),
                                 'semantic_review_required': True}
    atomic_json(RESULTS / 'summary-v1.json', {
        'status': 'observed_pending_independent_semantic_review',
        'cases': all_outcomes, 'models_allocated': False,
        'superiority_proven': False, 'completed_at': time.time()}, exclusive=True)


if __name__ == '__main__':
    main()
