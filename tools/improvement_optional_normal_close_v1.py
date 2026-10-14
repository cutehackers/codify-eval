"""Prospective normal-close adapter preserving the original qualified closer.

Requires original native normal lifecycle authority. Failed/interrupted runs
need separate failure closure. This adapter grants no comparison admission.
"""
import json
from pathlib import Path

import improvement_optional_comparison_inputs_v2 as inputs
import improvement_optional_native_close_v4 as original
import improvement_optional_native_dispatch_v4 as native_dispatch
import improvement_optional_result_classification_v1 as classifier


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
        result = classifier.classify(receipt, 24)
    outcome = {'row': row, 'original_outcome': str(folder / 'native-close/outcome.json'),
               'classification': result, 'owned_cleanup_verified': value['owned_cleanup_verified'],
               'usage': value.get('usage'), 'whole_observed_seconds': value['whole_observed_seconds'],
               'comparison_admitted': False, 'superiority_proven': False}
    original.atomic_json(folder / 'native-close/classified-outcome-v1.json', outcome, exclusive=True)
    return outcome
