"""Additive same-actor failed-observer closure, without grading or observer restart."""
import json
from contextlib import contextmanager
from pathlib import Path
import improvement_optional_comparison_driver_v2 as driver
import improvement_optional_lifecycle_v5 as replacement

REVIEW = driver.BASE / 'C17-optional-lifecycle-millisecond-review-v1.json'

@contextmanager
def qualified_lifecycle():
    module = driver.failure_close.gate.original.inventory.lifecycle
    saved = module.lifecycle
    module.lifecycle = replacement.lifecycle
    try:
        yield
    finally:
        module.lifecycle = saved


def close(coordinator_source, inventory_call_id):
    driver.admission()  # Existing comparison source/input freeze remains unchanged.
    review = json.loads(REVIEW.read_bytes())
    driver.require(review['verdict'] == 'pass' and review['issues'] == [],
                   'Independent additive lifecycle/recovery review required')
    for category in ('source_entities', 'evidence_entities'):
        for key, pin in review[category].items():
            driver.control.reviewed_entity(driver.ROOT / key, pin)
    registered = {(driver.ROOT / key).resolve() for key in review['source_entities']}
    driver.require({Path(__file__).resolve(), Path(replacement.__file__).resolve()} <= registered,
                   'Exact additive recovery source closure required')
    row = driver.inputs.sequence()[1]
    folder = driver.ROOT / 'runtime' / row['run_id']
    preservation = folder / 'observer-failure-preservation-v1'
    failure = json.loads((preservation / 'failure.json').read_bytes())
    driver.require(driver.runtime.encoded(failure['row']) == driver.runtime.encoded(row)
                   and failure['observer_exit_code'] == 1
                   and failure['observer_restarted'] is False
                   and failure['first_error'] == {'type': 'ValueError',
                       'message': 'Worker final started an unapproved turn'},
                   'Exact original observer failure required')
    for role, member in failure['members'].items():
        driver.control.reviewed_entity(preservation / (role + '.jsonl'), member['preserved_entity'])
        driver.require(driver.normal_close.original.capture(member['original_source'], 256*1024*1024)
                       == (preservation / (role + '.jsonl')).read_bytes(),
                       'Original completed member changed after failed observer')
    driver.control.atomic_json(folder / 'millisecond-failure-recovery-v1-intent.json', {
        'row': row, 'review_entity': driver.control.entity(REVIEW),
        'recovery_entity': driver.control.entity(__file__),
        'lifecycle_entity': driver.control.entity(replacement.__file__),
        'original_failure_entity': driver.control.entity(preservation / 'failure.json'),
        'original_comparison_freeze': driver.control.entity(driver.FREEZE),
        'observer_restarted': False, 'model_actors_allocated': 0,
        'software_pass': None, 'comparison_admitted': False, 'superiority_proven': False}, exclusive=True)
    with qualified_lifecycle():
        return driver.failure_close.close(row, coordinator_source, inventory_call_id, failure['first_error'])
