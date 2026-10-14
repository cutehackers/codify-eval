"""Prospective quality-first C19 normal-close adapter, retaining the original closer.

Requires original native normal lifecycle authority. Failed/interrupted runs
need separate failure closure. This adapter grants no comparison admission.
"""
import json
from pathlib import Path

import improvement_optional_comparison_inputs_v3 as inputs
from contextlib import contextmanager
import shutil
import hashlib
import stat
import improvement_optional_quality_assessment_v1 as quality
import improvement_optional_native_close_v4 as original
import improvement_optional_native_dispatch_v4 as native_dispatch
import improvement_optional_result_classification_v1 as classifier



OVERLAY = inputs.ROOT / 'improvement_cases/O02-development-quality-supplement-v1/encoder_success_invariants_test.dart'


def source_guard():
    quality.amendment.original.admission()
    control = quality.amendment.original.control
    base = quality.amendment.original.BASE
    for name in ('C19-forward-inputs-review-v1.json',
                 'O02-development-quality-supplement-v1-static-review.json',
                 'O02-development-quality-pair-outcome-review-v1.json',
                 'C19-quality-first-normal-close-review-v2.json'):
        review = json.loads((base / name).read_bytes())
        original.require(review['verdict'] == 'pass' and review['issues'] == [],
                         'Independent current forward grading review required')
        for category in ('source_entities', 'evidence_entities'):
            for path, pin in review[category].items():
                control.reviewed_entity(inputs.ROOT / path, pin)
        if name == 'C19-quality-first-normal-close-review-v2.json':
            original.require(str(Path(__file__).resolve().relative_to(inputs.ROOT))
                             in review['source_entities'], 'Exact forward close source review required')


@contextmanager
def grading(row, warnings):
    source_guard()
    expected = 30 if row['case_id'] == 'O02' else 24
    original_verify = original.verifier.verify
    overlay_pin = quality.amendment.original.control.entity(OVERLAY)

    def verify(source, folder, deadline, expected_tests=24):
        original.require(expected_tests == 24, 'Original combined grading entry point required')
        source_guard()
        run_folder = inputs.ROOT / 'runtime' / row['run_id']
        source_path = Path(source)
        original.require(not run_folder.is_symlink() and not source_path.is_symlink()
                         and source_path.resolve() == run_folder / 'native-close/combined-source',
                         'Exact owned combined-source path required')
        events = [original.audit.inventory.decoded(path.read_bytes())
                  for path in sorted((run_folder / 'events').glob('*.json'))]
        snapshots = [event for event in events if event.get('op') == 'stopped_snapshot'
                     and event.get('job') == 'root']
        original.require(snapshots and snapshots[-1]['scope_error'] is None,
                         'Original stopped source scope guard required')
        snapshot = snapshots[-1]
        export_path = Path(snapshot['export'])
        original.require(not export_path.is_symlink()
                         and export_path.resolve().is_relative_to(run_folder / 'snapshots'),
                         'Exact owned real stopped export required')
        stopped = snapshot['inventory']['source_entities']
        acceptance = inputs.case_directory(row) / 'private/acceptance_test.dart'
        expected_copy = dict(stopped)
        private_name = 'test/author_acceptance_test.dart'
        original.require(private_name not in expected_copy, 'Private acceptance collision')
        expected_copy[private_name] = {'kind': 'file',
                                      'mode': stat.S_IMODE(acceptance.stat().st_mode),
                                      'sha256': hashlib.sha256(acceptance.read_bytes()).hexdigest()}

        def fence(expected_tree):
            original.require(original.verifier.tree(export_path) == stopped,
                             'Stopped export differs from original recorded inventory')
            original.require(original.verifier.tree(source_path) == expected_tree,
                             'Combined source differs from exact stopped inventory and frozen tests')

        fence(expected_copy)
        if row['case_id'] == 'O02':
            target = Path(source) / 'test/supplement_encoder_success_invariants_test.dart'
            original.require(not target.exists(), 'Frozen supplement destination collision')
            shutil.copyfile(OVERLAY, target)
            original.require(quality.amendment.original.control.entity(OVERLAY) == overlay_pin,
                             'Frozen supplement changed while copying')
            supplement_name = 'test/supplement_encoder_success_invariants_test.dart'
            expected_copy[supplement_name] = {'kind': 'file',
                                             'mode': stat.S_IMODE(OVERLAY.stat().st_mode),
                                             'sha256': hashlib.sha256(OVERLAY.read_bytes()).hexdigest()}
        fence(expected_copy)
        receipt = original_verify(source, folder, deadline, expected_tests=expected)
        fence(expected_copy)
        source_guard()
        return receipt

    try:
        with quality.amendment.observer.lifecycle_decoder(), quality.output_warnings(warnings):
            original.verifier.verify = verify
            yield expected
    finally:
        original.verifier.verify = original_verify

def close(row, coordinator_source, inventory_call_id):
    inputs.row_valid(row)
    folder = inputs.ROOT / 'runtime' / row['run_id']
    state = original.runtime.load(folder)
    configuration = original.runtime.registry.read(folder / 'registry')['configuration']
    # Namespace names identify the comparison row. The runtime retains its
    # independent immutable allocation UUID, also used by the registry.
    original.require(configuration['run_id'] == state['run_id']
                     and configuration['started_at'] == state['started_at']
                     and configuration['deadline'] == state['deadline']
                     and configuration['case_id'] == row['case_id']
                     and configuration['condition'] == row['condition'],
                     'Original exact comparison configuration required')
    dispatch = original.audit.inventory.decoded(
        original.broker.original(folder / 'native-dispatch/configuration.json'))
    parent_raw = original.capture(coordinator_source, 256 * 1024 * 1024)
    parent_id = original.audit.inventory.core.parse(parent_raw)[0]['payload']['id']
    original.require(dispatch['root_path'] == row['actor_path']
                     and dispatch['coordinator_id'] == parent_id
                     and dispatch['run_id'] == configuration['run_id']
                     and dispatch['configuration_sha256'] == original.runtime.registry.sha(configuration)
                     and dispatch['runtime_configuration_sha256'] == native_dispatch.runtime_identity(folder, configuration),
                     'Original dispatch must bind this row and coordinator')
    acceptance = inputs.case_directory(row) / 'private/acceptance_test.dart'
    warnings = []
    with grading(row, warnings) as expected_tests:
        value = original.close(folder, coordinator_source, inventory_call_id, acceptance)
    result = {'software_pass': None, 'classification': 'evaluation_error'}
    receipt_path = folder / 'native-close/combined-verifier/receipt.json'
    # Keep original outcome bytes. Its initial False flag is not sufficient
    # evidence of a software failure when an earlier audit/cleanup failed.
    if (value.get('first_error') is None and value.get('owned_cleanup_verified') is True
            and value.get('source_fences_unchanged') is True and receipt_path.is_file()):
        receipt = json.loads(receipt_path.read_bytes())
        returned = json.loads(json.dumps(value.get('verification'), allow_nan=False))
        original.require(original.runtime.encoded(receipt)
                         == original.runtime.encoded(returned),
                         'Original returned verifier and persisted receipt differ')
        result = classifier.classify(receipt, expected_tests)
    outcome = {'row': row, 'original_outcome': str(folder / 'native-close/outcome.json'),
               'classification': result, 'output_warnings': list({json.dumps(w, sort_keys=True): w for w in warnings}.values()),
               'expected_tests': expected_tests, 'owned_cleanup_verified': value['owned_cleanup_verified'],
               'usage': value.get('usage'), 'whole_observed_seconds': value['whole_observed_seconds'],
               'comparison_admitted': False, 'superiority_proven': False}
    original.atomic_json(folder / 'native-close/classified-outcome-v2.json', outcome, exclusive=True)
    return outcome
