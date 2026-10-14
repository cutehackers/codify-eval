"""Prospective decoder-only amendment for the four unallocated frozen rows.

Existing actors, failures and the original comparison freeze are immutable.
No model input, permissions, clock, allocation order or software grader changes.
"""
import json
from pathlib import Path
import improvement_optional_comparison_driver_v2 as original
import improvement_optional_native_watch_v5 as observer

REVIEW = original.BASE / 'C17-optional-millisecond-observer-amendment-review-v1.json'
FREEZE = original.BASE / 'fresh-optional-development-comparison-observer-amendment-v1.json'
ROWS = original.inputs.sequence()[2:]


def payload():
    original.admission()
    review = json.loads(REVIEW.read_bytes())
    original.require(review['verdict'] == 'pass' and review['issues'] == [],
                     'Independent prospective observer/closure amendment required')
    pins = {}
    for category in ('source_entities', 'evidence_entities'):
        pins[category] = {key: original.control.reviewed_entity(original.ROOT / key, pin)
                          for key, pin in review[category].items()}
    original.require({Path(__file__).resolve(), Path(observer.__file__).resolve(),
                      Path(observer.replacement.__file__).resolve()}
                     <= {(original.ROOT / key).resolve() for key in pins['source_entities']},
                     'Exact supplementary source closure required')
    return {'original_comparison_freeze_entity': original.control.entity(original.FREEZE),
            'review_entity': original.control.entity(REVIEW), 'pins': pins, 'rows': ROWS,
            'change': 'Adjacent trigger_turn=false native worker delivery: 0..1 millisecond timestamp difference',
            'model': 'gpt-6.1-sol', 'effort': 'medium', 'trajectory_seconds': 1200,
            'worker_cap': 2, 'retries': 0, 'software_grader_changed': False,
            'actor_inputs_changed': False, 'original_errors_retained': True,
            'comparative_behavior_qualified': False, 'superiority_proven': False}


def freeze():
    value = payload()
    original.control.atomic_json(FREEZE, value, exclusive=True)
    return value


def admission(row):
    original.inputs.row_valid(row)
    original.require(original.runtime.encoded(row) in [original.runtime.encoded(r) for r in ROWS],
                     'Amendment applies only to the four originally unallocated rows')
    original.require(FREEZE.is_file() and not FREEZE.is_symlink(), 'Supplementary source freeze required')
    original.require(original.runtime.encoded(json.loads(FREEZE.read_bytes()))
                     == original.runtime.encoded(payload()), 'Supplementary source or evidence changed')


def select_observer(row):
    admission(row)
    path = original.BASE / (row['run_id'] + '-preparation.json')
    prepared = json.loads(path.read_bytes())
    original.require(original.runtime.encoded(prepared['row']) == original.runtime.encoded(row)
                     and prepared['model'] == 'gpt-6.1-sol' and prepared['effort'] == 'medium'
                     and prepared['model_actors_allocated'] == 0,
                     'Original exact pre-actor preparation required')
    argv = ['python3', str(Path(observer.__file__).resolve()), row['run_id'],
            row['actor_path'], prepared['coordinator_id']]
    original.control.atomic_json(original.BASE / (row['run_id'] + '-observer-amendment.json'), {
        'row': row, 'original_preparation_entity': original.control.entity(path),
        'amendment_freeze_entity': original.control.entity(FREEZE), 'observer_argv': argv,
        'original_started_at': prepared['original_started_at'], 'deadline': prepared['deadline'],
        'observer_restarts': 0, 'model_actors_allocated': 0}, exclusive=True)
    return argv


def close(row, coordinator_source, inventory_call_id):
    admission(row)
    with observer.lifecycle_decoder():
        return original.close(row, coordinator_source, inventory_call_id)


def close_failure(row, coordinator_source, inventory_call_id, first_error):
    admission(row)
    with observer.lifecycle_decoder():
        return original.close_failure(row, coordinator_source, inventory_call_id, first_error)
