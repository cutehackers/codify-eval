"""DRAFT voluntary optional adapter. No admitted freeze or allocation authority.

prepare/close reject until a separately versioned, independently reviewed
admission mechanism exists. The reusable preparation body is exercised only
with actor-free mocks. Existing qualified control sources remain unchanged.
Gaps: full case/skill/source/mode freeze, independent prerequisite schema,
actual 0..2 lifecycle and treatment access proof, terminal native inventory,
deadline failure closure, strict private result classification and all costs.
"""
import json
from pathlib import Path
import re
import time

import improvement_optional_comparison_inputs_v1 as inputs
import improvement_optional_native_control_v9 as control

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/improvement-v1'
runtime, broker, dispatch = control.runtime, control.broker, control.dispatch
require = runtime.require


def admission():
    raise ValueError('DRAFT unqualified: separate prelaunch review, freeze and lifecycle admission required')


def paths(row):
    inputs.row_valid(row)
    return (ROOT / 'runtime' / row['run_id'],
            BASE / (row['run_id'] + '-preparation.json'),
            BASE / (row['run_id'] + '-allocation-intent.json'))


def previous_reviews(row):
    """Prospective schema only; admission must independently qualify this gate."""
    inputs.row_valid(row)
    sequence = inputs.sequence()
    for prior in sequence[:sequence.index(row)]:
        review = json.loads((BASE / (prior['run_id'] + '-independent-review.json')).read_bytes())
        require(review.get('run_id') == prior['run_id'] and review.get('verdict') == 'pass'
                and review.get('issues') == [] and review.get('complete_observation') is True
                and review.get('owned_cleanup_verified') is True,
                'Prior original independent outcome and owned cleanup required')


def prepare(row, coordinator_id):
    inputs.row_valid(row)
    require(isinstance(coordinator_id, str)
            and re.fullmatch('[A-Za-z0-9_-]{1,100}', coordinator_id),
            'Exact original coordinator identity required')
    admission()  # Always rejects in this DRAFT, before any persistent/effectful operation.
    previous_reviews(row)
    folder, output, intent = paths(row)
    require(not folder.exists() and not output.exists(), 'No retry or reused namespace')
    case = inputs.case_directory(row)
    metadata = json.loads((case / 'metadata.json').read_bytes())
    task = inputs.public_task(row)
    control.atomic_json(intent, {'row': row, 'coordinator_id': coordinator_id,
                        'intent_started_at': time.time(), 'model_actors_allocated': 0,
                        'driver_entity': control.entity(__file__)}, exclusive=True)
    ownership = []

    def own(created):
        require(Path(created).resolve() == folder.resolve(), 'Ownership callback path changed')
        ownership.append(folder)

    try:
        # Skill is exported during the original runtime.create clock, before its
        # Git/protected baseline and all lazy worker snapshots. No pre-clock copy.
        with inputs.skill_export(row, folder):
            created = runtime.create(folder, case / 'repo', row['case_id'], row['condition'],
                                     task, metadata['editable_paths'], record_ownership=own)
        cap = created['root_capability']
        broker.register(folder, 'root', cap)
        dispatched = dispatch.create(folder, row['actor_path'], coordinator_id, cap)
        state = runtime.load(folder)
        require(state['deadline'] == state['started_at'] + 1200, 'Original clock changed')
        value = {'row': row, 'folder': str(folder), 'actor_path': row['actor_path'],
                 'coordinator_id': coordinator_id, 'root_dispatch': dispatched,
                 'observer_argv': ['python3', str(Path(control.observer.__file__).resolve()),
                                   folder.name, row['actor_path'], coordinator_id],
                 'original_started_at': state['started_at'], 'deadline': state['deadline'],
                 'model': 'gpt-6.1-sol', 'effort': 'medium', 'model_actors_allocated': 0,
                 'native_qualified': False, 'comparison_eligible': False,
                 'superiority_proven': False}
        control.atomic_json(output, value, exclusive=True)
        return value
    except BaseException as error:
        failure = {'row': row, 'status': 'preparation_failed',
                   'first_error': {'type': type(error).__name__, 'message': str(error)},
                   'runtime_ownership_observed': bool(ownership), 'model_actors_allocated': 0,
                   'native_qualified': False, 'comparison_eligible': False,
                   'superiority_proven': False}
        if ownership:
            try:
                runtime.failure(folder, error)
            except BaseException as original:
                failure['preservation_error'] = {'type': type(original).__name__, 'message': str(original)}
            try:
                failure['owned_cleanup'] = runtime.cleanup(folder)
            except BaseException as original:
                failure['cleanup_error'] = {'type': type(original).__name__, 'message': str(original)}
        try:
            control.atomic_json(output, failure, exclusive=True)
        except BaseException as original:
            # Durable exclusive intent stays intact; original failure is never replaced.
            print(json.dumps({'original_preparation_failure': failure,
                              'report_error': str(original)}))
        raise


def close(row, coordinator_source, inventory_call_id):
    inputs.row_valid(row)
    admission()
    # Deliberately no unqualified substitution of control.close_control: it
    # assumes O01/A and forced counts. Future review must qualify dynamic case
    # closure, actual UUID membership, private result and preserved failures.
    raise ValueError('DRAFT dynamic comparison closure not implemented')


if __name__ == '__main__':
    print(json.dumps({'status': 'draft_unqualified', 'sequence': inputs.sequence(),
                      'native_qualified': False, 'comparison_eligible': False,
                      'superiority_proven': False}))
