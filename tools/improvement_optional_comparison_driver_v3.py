"""Prospective matched A/C0/C19 voluntary development comparison.

No allocation is admitted without current source/input freezes, independent
prelaunch reviews and the genuine all-member deadline control. Untouched final
confirmation, statistical superiority and global research billing are separate.
"""
import json
from pathlib import Path
import re
import time

import improvement_optional_comparison_inputs_v3 as inputs
import improvement_optional_native_control_v9 as control
import improvement_optional_candidate_registry_v2 as registry_extension
import improvement_optional_normal_close_v2 as normal_close
import improvement_optional_completed_failure_close_v3 as failure_close
import improvement_optional_deadline_close_v3 as deadline_close
import improvement_optional_native_watch_v5 as observer

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/improvement-v1'
runtime, broker, dispatch = control.runtime, control.broker, control.dispatch
require = runtime.require


FREEZE = BASE / 'fresh-optional-development-comparison-freeze-v3.json'
REVIEWS = ('C17-optional-registry-extension-review-v1.json',
           'C17-optional-inputs-review-v2.json',
           'C17-optional-normal-close-review-v3.json',
           'C17-optional-completed-failure-gate-review-v1.json',
           'C17-optional-completed-failure-close-v2-review-v1.json',
           'C17-optional-deadline-members-review-v1.json',
           'C17-optional-deadline-close-review-v3.json',
           'fresh-optional-cohort-v1-qualification-outcome-review-v1.json',
           'fresh-optional-native-control-outcome-review-v10.json',
           'fresh-optional-deadline-control-outcome-review-v1.json',
           'C17-optional-comparison-driver-prelaunch-review-v2.json',
           'C19-static-design-review-v1.json',
           'C19-forward-inputs-review-v1.json',
           'C19-quality-first-normal-close-review-v2.json',
           'O02-development-quality-supplement-v1-static-review.json',
           'O02-development-quality-pair-outcome-review-v1.json',
           'C19-failure-and-deadline-adapters-review-v1.json',
           'C19-optional-comparison-driver-prelaunch-review-v1.json')


def review_entities(name, review, category):
    if category in review:
        return review[category]
    require(name == 'fresh-optional-cohort-v1-qualification-outcome-review-v1.json',
            'Typed independent review entities required: ' + name)
    legacy = review.get(category.replace('_entities', '_hashes'))
    require(isinstance(legacy, dict) and bool(legacy), 'Original qualification hashes required')
    entities = {}
    for key, digest in legacy.items():
        require(isinstance(key, str) and isinstance(digest, str)
                and re.fullmatch('[0-9a-f]{64}', digest), 'Exact original qualification hash required')
        actual = control.entity(ROOT / key)
        require(actual['sha256'] == digest, 'Original qualified file changed: ' + key)
        # Historical byte hashes remain authoritative. Current file mode/size
        # are explicitly captured by the prospective freeze, not inferred old metadata.
        entities[key] = actual
    return entities


def freeze_payload():
    shared = control.checked_freeze()
    sources = dict(shared['source_entities']); reviews = {}; evidence = {}
    for name in REVIEWS:
        path = BASE / name; review = json.loads(path.read_bytes())
        require(review.get('verdict') == 'pass' and review.get('issues') == [],
                'Exact independently reviewed prerequisites required: ' + name)
        reviews[name] = control.entity(path)
        for key, pin in review_entities(name, review, 'source_entities').items():
            actual = control.reviewed_entity(ROOT / key, pin)
            require(key not in sources or sources[key] == actual, 'Conflicting reviewed source closure')
            sources[key] = actual
        for key, pin in review_entities(name, review, 'evidence_entities').items():
            actual = control.reviewed_entity(ROOT / key, pin)
            require(key not in evidence or evidence[key] == actual, 'Conflicting original evidence pins')
            evidence[key] = actual
    deadline_review = json.loads((BASE / 'fresh-optional-deadline-control-outcome-review-v1.json').read_bytes())
    require(deadline_review.get('actual_native_interruption_and_cleanup_verified') is True
            and deadline_review.get('observer_original_clock_continuity_verified') is True
            and deadline_review.get('all_actual_member_termination_authority_verified') is True
            and deadline_review.get('owned_cleanup_verified') is True,
            'Actual original all-member native deadline control must qualify first')
    essential = {Path(module.__file__).resolve() for module in (
        inputs, registry_extension, normal_close, failure_close, deadline_close,
        runtime, broker, dispatch, observer)} | {Path(__file__).resolve()}
    require(essential <= {(ROOT / key).resolve() for key in sources},
            'Exact prospective driver and dynamic script closure required')
    cases = {}
    for case in inputs.CASES:
        directory = ROOT / 'improvement_cases/fresh-optional-cohort-v1' / case
        cases[case] = {'repo': runtime.source.inventory(directory / 'repo'),
                       'public': control.entity(directory / 'public/request.md'),
                       'private': control.entity(directory / 'private/acceptance_test.dart'),
                       'metadata': control.entity(directory / 'metadata.json')}
    return {'sequence': inputs.sequence(), 'seed': inputs.SEED,
            'model': 'gpt-6.1-sol', 'effort': 'medium', 'trajectory_seconds': 1200,
            'worker_cap': 2, 'retries': 0, 'sources': sources, 'reviews': reviews,
            'evidence': evidence, 'cases': cases,
            'skills': {condition: runtime.source.inventory(ROOT / 'snapshots' / condition)
                       for condition in ('C0', 'C19')},
            'public_tasks': {row['run_id']: inputs.public_task(row) for row in inputs.sequence()},
            'grading_tests': {'O01': 24, 'O02': 30},
            'quality_overlay': control.entity(normal_close.OVERLAY),
            'output_budget_excess_is_warning_only': True,
            'observer_entity': control.entity(observer.__file__),
            'comparison_admitted': False, 'superiority_proven': False}


def freeze():
    value = freeze_payload(); control.atomic_json(FREEZE, value, exclusive=True); return value


def admission():
    require(FREEZE.is_file() and not FREEZE.is_symlink(),
            'Original reviewed comparison freeze is not available')
    value = json.loads(FREEZE.read_bytes())
    require(runtime.encoded(value) == runtime.encoded(freeze_payload()),
            'Original development comparison source/input/policy/evidence freeze changed')
    return value


def paths(row):
    inputs.row_valid(row)
    return (ROOT / 'runtime' / row['run_id'],
            BASE / (row['run_id'] + '-preparation.json'),
            BASE / (row['run_id'] + '-allocation-intent.json'))


def previous_reviews(row):
    """A retained failure may advance; live actors or unresolved cleanup may not."""
    inputs.row_valid(row)
    sequence = inputs.sequence()
    for prior in sequence[:sequence.index(row)]:
        path = BASE / (prior['run_id'] + '-independent-review.json')
        review = json.loads(path.read_bytes())
        require(runtime.encoded(review.get('row')) == runtime.encoded(prior)
                and review.get('verdict') == 'pass' and review.get('issues') == []
                and review.get('original_terminal_preservation_verified') is True
                and review.get('owned_cleanup_verified') is True
                and review.get('all_failed_attempts_and_costs_preserved') is True,
                'Prior exact original terminal preservation and owned cleanup required')
        require(isinstance(review.get('evidence_entities'), dict) and bool(review['evidence_entities']),
                'Original prior outcome/source evidence required')
        for key, pin in review['evidence_entities'].items():
            control.reviewed_entity(ROOT / key, pin)


def prepare(row, coordinator_id):
    inputs.row_valid(row)
    require(isinstance(coordinator_id, str)
            and re.fullmatch('[A-Za-z0-9_-]{1,100}', coordinator_id),
            'Exact original coordinator identity required')
    admission()  # Complete current freeze and actual control required before any effect.
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
        with registry_extension.creation_hook(), inputs.skill_export(row, folder):
            created = runtime.create(folder, case / 'repo', row['case_id'], row['condition'],
                                     task, metadata['editable_paths'], record_ownership=own)
        cap = created['root_capability']
        broker.register(folder, 'root', cap)
        dispatched = dispatch.create(folder, row['actor_path'], coordinator_id, cap)
        state = runtime.load(folder)
        require(state['deadline'] == state['started_at'] + 1200, 'Original clock changed')
        value = {'row': row, 'folder': str(folder), 'actor_path': row['actor_path'],
                 'coordinator_id': coordinator_id, 'root_dispatch': dispatched,
                 'observer_argv': ['python3', str(Path(observer.__file__).resolve()),
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
    inputs.row_valid(row); admission()
    return normal_close.close(row, coordinator_source, inventory_call_id)


def close_failure(row, coordinator_source, inventory_call_id, first_error):
    inputs.row_valid(row); admission()
    with observer.lifecycle_decoder():
        return failure_close.close(row, coordinator_source, inventory_call_id, first_error)


def commit_deadline(row, coordinator_source):
    inputs.row_valid(row); admission()
    return deadline_close.commit(ROOT / 'runtime' / row['run_id'], coordinator_source)


def close_deadline(row, coordinator_source):
    inputs.row_valid(row); admission()
    return deadline_close.close(ROOT / 'runtime' / row['run_id'], coordinator_source)


if __name__ == '__main__':
    print(json.dumps({'status': 'prospective_unadmitted', 'sequence': inputs.sequence(),
                      'native_qualified': False, 'comparison_eligible': False,
                      'superiority_proven': False}))
