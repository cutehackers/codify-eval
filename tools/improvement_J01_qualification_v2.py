"""Independent fixed-image fixture controls, separate from model evaluation."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
import time

from improvement_fresh_pilot_qualification_v1 import classify, sha
from improvement_q04_verifier_v5 import verify, IMAGE
from improvement_software_artifacts_v3 import atomic_json

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / 'improvement_cases/fresh-integrated-v1/J01'
REVIEW = ROOT / 'results/improvement-v1/fresh-J01-N03-revision-review-v3.json'
OUT = ROOT / 'results/improvement-v1/fresh-J01-qualification-v2'
RUNTIME = ROOT / 'runtime/protocol-probes/fresh-J01-qualification-v2'


def owned_path(relative):
    path = CASE / relative
    assert isinstance(relative, str) and not Path(relative).is_absolute() and '..' not in Path(relative).parts
    assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(CASE.resolve())
    return path


def closure():
    pending, found = [Path(__file__).resolve()], set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_bytes())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                if name:
                    local = ROOT / 'tools' / (name.split('.')[0] + '.py')
                    if local.is_file() and local not in found:
                        pending.append(local)
    return found


def run():
    assert not OUT.exists() and not RUNTIME.exists()
    # Never overlap qualification containers with an evaluated product timeline.
    assert not subprocess.check_output(['docker', 'ps', '-a', '-q', '--filter', 'name=codify-'], text=True, timeout=30).strip()
    metadata = json.loads((CASE / 'metadata.json').read_bytes())
    review = json.loads(REVIEW.read_bytes())
    assert review['verdict'] == 'pass' and not review['issues']
    for key in ('source_hashes', 'evidence_hashes'):
        for name, expected in review.get(key, {}).items():
            path = Path(name) if name.startswith('/') else ROOT / name
            assert sha(path) == expected, name
    assert metadata['id'] == 'J01' and metadata['expected_total_test_count'] == 33
    assert metadata['expected_public_test_count'] == 2 and metadata['expected_private_test_count'] == 31
    variants = {'reference': metadata['private_reference'], **metadata['negative_controls']}
    assert set(variants) == {'reference', 'N01', 'N02', 'N03', 'N04'}
    paths = [owned_path(p) for p in variants.values()] + [owned_path(metadata['private_acceptance'])]
    pins = {str(p.relative_to(ROOT)): sha(p) for p in CASE.rglob('*') if p.is_file()}
    pins.update({str(p.relative_to(ROOT)): sha(p) for p in closure() | {REVIEW, ROOT / 'runtime/image.json', ROOT / 'AGENTS.md'}})
    assert json.loads((ROOT / 'runtime/image.json').read_bytes())['image_id'] == IMAGE
    OUT.mkdir(); RUNTIME.mkdir()
    summary = {'status': 'RUNNING', 'model_actors_allocated': 0, 'image_id': IMAGE,
               'source_hashes': pins, 'variants': {}, 'superiority_proven': False,
               'measured_model_difficulty': False, 'started_at': time.time()}
    atomic_json(OUT / 'summary-v1.json', summary, exclusive=True)
    for variant, relative in variants.items():
        source = RUNTIME / variant / 'source'
        shutil.copytree(CASE / 'repo', source)
        shutil.copyfile(owned_path(relative), source / 'lib/implementation.dart')
        oracle = source / 'test/acceptance_test.dart'
        assert not oracle.exists()
        shutil.copyfile(owned_path(metadata['private_acceptance']), oracle)
        receipt = verify(source, RUNTIME / variant / 'verification', time.time() + 600, expected_tests=33)
        atomic_json(OUT / (variant + '-receipt.json'), receipt, exclusive=True)
        result = classify(receipt, 33)
        result['expected_behavior'] = 'pass' if variant == 'reference' else 'genuine_assertion_failure'
        summary['variants'][variant] = result
        summary['all_allocated_containers_removed'] = all(r.get('removed') is True for r in summary['variants'].values())
        atomic_json(OUT / 'summary-v1.json', summary)
        if not result['valid_behavior_observation'] or result['removed'] is not True:
            summary['status'] = 'FAIL_INCOMPLETE_OBSERVATION'
            break
    for name, expected in pins.items():
        assert sha(ROOT / name) == expected, name
    if summary['status'] == 'RUNNING':
        qualified = (len(summary['variants']) == 5 and summary['variants']['reference']['positive_checks_pass']
                     and all(summary['variants'][n]['genuine_assertion_negative'] for n in ('N01', 'N02', 'N03', 'N04')))
        summary['status'] = 'behavior_controls_pass' if qualified else 'FAIL_BEHAVIOR_CONTROL'
    summary['finished_at'] = time.time()
    summary['fixture_semantics_independently_reviewed'] = True
    summary['model_outcome_qualified'] = False
    atomic_json(OUT / 'summary-v1.json', summary)
    return summary


if __name__ == '__main__':
    value = run()
    print(json.dumps({k: v for k, v in value.items() if k != 'source_hashes'}))
    raise SystemExit(0 if value['status'] == 'behavior_controls_pass' else 1)
