"""Frozen, same-artifact supplementary development test pair, not final proof.

Reuses the pristine offline grader. No product execution, source modification,
original result replacement, or changes to the frozen 24-test oracle.
"""
import json
from pathlib import Path
import shutil
import time

import improvement_optional_quality_assessment_v1 as quality

original = quality.original
control = quality.amendment.original.control
BASE = quality.amendment.original.BASE
ROOT = original.ROOT
TEST = ROOT / 'improvement_cases/O02-development-quality-supplement-v1/encoder_success_invariants_test.dart'
REVIEW = BASE / 'O02-development-quality-pair-prelaunch-review-v1.json'
FREEZE = BASE / 'O02-development-quality-pair-freeze-v1.json'
ROWS = (
    {'condition': 'A', 'run': 'optional-development-v2-O02-A-1', 'assessment': 'native-close'},
    {'condition': 'C17', 'run': 'optional-development-v2-O02-C17-1', 'assessment': 'supplemental-quality-v1'},
)
require = original.require


def reviewed(path):
    value = json.loads(path.read_bytes())
    require(value['verdict'] == 'pass' and value['issues'] == [], 'Independent current review required')
    for category in ('source_entities', 'evidence_entities'):
        for name, pin in value[category].items():
            control.reviewed_entity(ROOT / name, pin)
    return value


def payload():
    quality.amendment.original.admission()
    reviewed(BASE / 'O02-development-quality-supplement-v1-static-review.json')
    reviewed(BASE / 'output-limit-quality-assessment-outcome-review-v1.json')
    review = reviewed(REVIEW)
    require(str(Path(__file__).resolve().relative_to(ROOT)) in review['source_entities'],
            'Exact paired grader source must be reviewed')
    sources = []
    for row in ROWS:
        folder = ROOT / 'runtime' / row['run'] / row['assessment']
        receipt = json.loads((folder / 'combined-verifier/receipt.json').read_bytes())
        require(quality.classifier.classify(receipt, 24)['software_pass'] is True,
                'Original same-code 24-test assessment must be verified')
        source = folder / 'combined-source'
        require(original.verifier.tree(source) == receipt['source_before'],
                'Exact recorded original graded source required')
        sources.append({'row': row, 'source': str(source), 'tree': receipt['source_before'],
                        'original_receipt_entity': control.entity(folder / 'combined-verifier/receipt.json')})
    return {'source_pairs': sources, 'overlay_entity': control.entity(TEST),
            'prelaunch_review_entity': control.entity(REVIEW),
            'fixture_review_entity': control.entity(BASE / 'O02-development-quality-supplement-v1-static-review.json'),
            'model': 'gpt-6.1-sol', 'effort': 'medium', 'new_product_model_allocations': 0,
            'order': ['A', 'C17'], 'supplemental_tests': 6, 'expected_total_tests': 30,
            'per_assessment_seconds': 300, 'original_comparison_unchanged': True,
            'scope': 'Exposed O02 development coverage supplement', 'superiority_proven': False}


def freeze():
    value = payload()
    control.atomic_json(FREEZE, value, exclusive=True)
    return value


def assess(condition):
    require(condition in ('A', 'C17'), 'Exact paired development condition required')
    value = payload()
    require(json.loads(FREEZE.read_bytes()) == value, 'Frozen original artifacts or grader changed')
    item = next(item for item in value['source_pairs'] if item['row']['condition'] == condition)
    if condition == 'C17':
        prior = ROOT / 'runtime/O02-quality-pair-v1-A/outcome.json'
        require(prior.is_file(), 'Preserve first condition before second assessment')
        previous = json.loads(prior.read_bytes())
        require(previous['owned_cleanup_verified'] is True, 'First grader cleanup must finish before next')
    folder = ROOT / 'runtime' / ('O02-quality-pair-v1-' + condition)
    folder.mkdir()
    started = time.time()
    result = {'condition': condition, 'original_run': item['row']['run'],
              'freeze_entity': control.entity(FREEZE), 'started_at': started,
              'software_pass': None, 'classification': 'evaluation_error',
              'first_error': None, 'owned_cleanup_verified': False,
              'new_product_model_allocations': 0, 'original_comparison_unchanged': True,
              'held_out_final': False, 'superiority_proven': False}
    control.atomic_json(folder / 'intent.json', result, exclusive=True)
    try:
        source = Path(item['source'])
        require(original.verifier.tree(source) == item['tree'], 'Original source changed before copy')
        copy = folder / 'combined-source'
        shutil.copytree(source, copy)
        require(original.verifier.tree(copy) == item['tree'], 'Exact original source copy required')
        target = copy / 'test/supplement_encoder_success_invariants_test.dart'
        require(not target.exists(), 'Supplement destination collision')
        shutil.copyfile(TEST, target)
        require(control.entity(TEST) == value['overlay_entity'], 'Overlay changed during copy')
        result['verification'] = original.verifier.verify(copy, folder / 'verifier',
                                                         started + 300, expected_tests=30)
        result.update(quality.classifier.classify(json.loads(json.dumps(result['verification'])), 30))
        result['owned_cleanup_verified'] = result['verification'].get('removed') is True
        require(result['owned_cleanup_verified'], 'Supplement grader cleanup incomplete')
        require(original.verifier.tree(source) == item['tree'], 'Original source changed through grading')
        require(payload() == value, 'Frozen source, overlay or authority changed through grading')
    except BaseException as error:
        result['first_error'] = {'type': type(error).__name__, 'message': str(error)}
        result['software_pass'] = None
        result['classification'] = 'evaluation_error'
    result['finished_at'] = time.time()
    result['supplemental_wall_seconds'] = result['finished_at'] - started
    control.atomic_json(folder / 'outcome.json', result, exclusive=True)
    return result
