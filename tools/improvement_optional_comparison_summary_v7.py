"""Read-only all-assigned v5 development observation, including preparation failure.

No allocation, retry, regrading, billing, candidate promotion or superiority proof.
"""
import json
import math
from pathlib import Path
import time

import improvement_optional_comparison_driver_v7 as d
import improvement_optional_comparison_summary_v6 as preserved

ROOT, BASE = d.ROOT, d.BASE
OUTPUT = BASE / 'fresh-optional-development-comparison-summary-v5.json'
COUNTERS = preserved.COUNTERS
FLAGS = preserved.FLAGS
require = d.require


def closure(row, sources, evidence):
    path = BASE / (row['run_id'] + '-independent-review.json')
    review = json.loads(path.read_bytes())
    require(d.runtime.encoded(review.get('row')) == d.runtime.encoded(row)
            and review.get('verdict') == 'pass' and review.get('issues') == []
            and all(review.get(flag) is True for flag in FLAGS),
            'Exact independent original preservation review required')
    for category, merged in [('source_entities', sources), ('evidence_entities', evidence)]:
        require(isinstance(review.get(category), dict) and bool(review[category]),
                'Typed original closure required')
        for key, pin in review[category].items():
            actual = d.reviewed_entity(ROOT / key, pin)
            require(key not in merged or merged[key] == actual, 'Conflicting preserved pins')
            merged[key] = actual
    root_path = BASE / (row['run_id'] + '-root-verification.json')
    root = json.loads(root_path.read_bytes())
    require(root.get('verdict') == 'pass' and root.get('all_current_pins_verified') is True
            and root.get('review_entity') == d.control.entity(path)
            and root.get('source_entities_verified') == len(review['source_entities'])
            and root.get('evidence_entities_verified') == len(review['evidence_entities']),
            'Exact current root verification required')
    evidence[str(path.relative_to(ROOT))] = d.control.entity(path)
    evidence[str(root_path.relative_to(ROOT))] = d.control.entity(root_path)
    return review


def pinned(path, review):
    key = str(path.relative_to(ROOT))
    require(key in review['evidence_entities'], 'Original observation must be independently pinned')
    d.reviewed_entity(path, review['evidence_entities'][key])
    return json.loads(path.read_bytes())


def preparation_failure(row, review):
    require(row == d.inputs.sequence()[1] and review.get('software_pass') is None
            and type(review.get('model_actors_allocated')) is int
            and review['model_actors_allocated'] == 0
            and review.get('current_owned_resource_absence_verified') is True
            and review.get('historical_creation_identity_known') is False
            and review.get('historical_id_removal_proven') is False
            and review.get('creation_never_occurred_proven') is False,
            'Exact zero-model preparation failure preservation required')
    folder = ROOT / 'runtime' / row['run_id']
    require(not (folder / 'native-close').exists() and not (folder / 'native-close').is_symlink(),
            'Ungraded preparation failure cannot acquire a software outcome')
    prep = pinned(BASE / (row['run_id'] + '-preparation.json'), review)
    account = pinned(BASE / (row['run_id'] + '-current-owned-resource-absence-v2.json'), review)
    require(prep['row'] == row and prep['status'] == 'preparation_failed'
            and prep['first_error']['type'] == 'CalledProcessError'
            and prep['runtime_ownership_observed'] is True
            and type(prep['model_actors_allocated']) is int and prep['model_actors_allocated'] == 0
            and account['row'] == row and account['software_pass'] is None
            and account['original_preparation_failure_preserved'] is True
            and account['original_cleanup_failure_preserved'] is True
            and account['current_owned_resource_absence_verified'] is True
            and account['historical_creation_identity_known'] is False
            and account['historical_id_removal_proven'] is False
            and account['creation_never_occurred_proven'] is False
            and type(account['native_zero_product_allocation']['model_actors_allocated_verified']) is int
            and account['native_zero_product_allocation']['model_actors_allocated_verified'] == 0
            and type(account['model_actors_allocated']) is int and account['model_actors_allocated'] == 0
            and account['original_error'] == prep['first_error']
            and account['original_cleanup_error'] == prep['cleanup_error']
            and account['no_retry_or_namespace_replacement'] is True,
            'Original failure, current absence and zero-model observation must stay distinct')
    total = account['all_preparation_failure_wait_restart_recovery_seconds']
    failure = account['original_preparation_through_terminal_observation_seconds']
    recovery = account['terminal_failure_through_current_absence_seconds']
    require(all(type(value) in (int, float) and math.isfinite(value) and value >= 0 for value in (total, failure, recovery))
            and abs(total - failure - recovery) < 0.000001
            and abs(total - account['recorded_at'] + account['original_intent_started_at']) < 0.000001,
            'No failed preparation, restart, waiting or recovery may be dropped')
    return {'row': row, 'classification': 'infra_ungraded_preparation_failure',
            'software_pass': None, 'tests': None, 'members': [],
            'product_native_trajectory_applicable': False,
            'observed_native_totals': None,
            'known_valid_partial_native_totals': {key: 0 for key in COUNTERS},
            'known_zero_member_set_not_imputed_missing_usage': True,
            'unknown_usage_paths': [], 'first_actual_runtime_whole_seconds': None,
            'all_recorded_run_episode_seconds': total,
            'preparation_failure': {'original_error': prep['first_error'],
                                    'original_cleanup_error': prep['cleanup_error'],
                                    'model_actors_allocated': 0,
                                    'historical_creation_identity_known': False,
                                    'historical_id_removal_proven': False,
                                    'creation_never_occurred_proven': False,
                                    'current_owned_resource_absence_verified': True,
                                    'original_terminal_observation_seconds': failure,
                                    'failure_through_current_absence_seconds': recovery,
                                    'matched_efficiency_claim_permitted': False},
            'owned_cleanup_verified': True,
            'owned_cleanup_scope': review['owned_cleanup_verified_scope'],
            'output_warnings': [], 'output_warnings_have_quality_penalty': False}


def selected(row, sources, evidence, seen):
    review = closure(row, sources, evidence)
    if row == d.inputs.sequence()[1]:
        return preparation_failure(row, review)
    folder = ROOT / 'runtime' / row['run_id']
    original = pinned(folder / 'native-close/outcome.json', review)
    classified = pinned(folder / 'native-close/classified-outcome-v6.json', review)
    expected = 24 if row['case_id'] == 'O01' else 30
    require(classified['row'] == row and classified['expected_tests'] == expected
            and original['first_error'] is None and original['source_fences_unchanged'] is True
            and original['owned_cleanup_verified'] is True,
            'Original closed grading and owned cleanup required')
    grade = preserved.tests(original, expected)
    software = classified['classification']['software_pass']
    require(type(software) is bool and type(original['software_combined_pass']) is bool
            and type(review['software_pass']) is bool and software == (grade['failed'] == 0)
            and software == original['software_combined_pass']
            and software == review['software_pass'], 'Original software outcome must not change')
    usage = classified['usage']
    require(d.runtime.encoded(usage) == d.runtime.encoded(original['usage']),
            'Original and classified usage must match including types')
    preserved.validated_usage(original['usage'], set(seen))
    known, members, observed = preserved.validated_usage(usage, seen)
    whole = original['whole_observed_seconds']
    require(type(whole) in (int, float) and math.isfinite(whole) and whole >= 0
            and d.runtime.encoded(whole) == d.runtime.encoded(classified['whole_observed_seconds']), 'Original whole runtime required')
    return {'row': row, 'classification': classified['classification']['classification'],
            'software_pass': software, 'tests': grade, 'members': members,
            'product_native_trajectory_applicable': True, 'observed_native_totals': observed,
            'known_valid_partial_native_totals': known, 'unknown_usage_paths': usage['unknown_usage_paths'],
            'first_actual_runtime_whole_seconds': whole,
            'all_recorded_run_episode_seconds': whole, 'preparation_failure': None,
            'owned_cleanup_verified': True, 'owned_cleanup_scope': 'Exact original product and grader ID cleanup',
            'output_warnings': classified['output_warnings'], 'output_warnings_have_quality_penalty': False}


def payload():
    frozen = d.admission()
    sources = dict(frozen['sources'])
    sources[str(Path(__file__).resolve().relative_to(ROOT))] = d.control.entity(__file__)
    evidence = {str(d.FREEZE.relative_to(ROOT)): d.control.entity(d.FREEZE)}
    seen = set()
    rows = [selected(row, sources, evidence, seen) for row in d.inputs.sequence()]
    conditions = {}
    for condition in ('A', 'C0', 'C21'):
        group = [row for row in rows if row['row']['condition'] == condition]
        require(len(group) == 2, 'Every assigned condition must keep both cases')
        unknown = [path for row in group for path in row['unknown_usage_paths']]
        known = {key: sum(row['known_valid_partial_native_totals'][key] for row in group)
                 for key in COUNTERS}
        conditions[condition] = {'assigned_rows': len(group),
            'software_passed': sum(row['software_pass'] is True for row in group),
            'software_failed': sum(row['software_pass'] is False for row in group),
            'infra_ungraded': sum(row['software_pass'] is None for row in group),
            'actual_native_uuid_count': sum(len(row['members']) for row in group),
            'observed_allocated_participant_native_totals': None if unknown else known,
            'known_valid_partial_native_totals': known, 'unknown_usage_paths': unknown,
            'actual_software_trajectory_whole_seconds': sum(row['first_actual_runtime_whole_seconds'] or 0 for row in group),
            'all_recorded_run_episodes_seconds': sum(row['all_recorded_run_episode_seconds'] for row in group),
            'complete_assigned_software_trajectories': all(row['software_pass'] is not None for row in group),
            'matched_efficiency_claim_permitted': False}
    return {'study': 'frozen-optional-development-comparison-v5', 'seed': frozen['seed'],
            'model': frozen['model'], 'effort': frozen['effort'], 'rows': rows,
            'conditions': conditions, 'distinct_actual_native_uuid_count': len(seen),
            'assigned_rows': len(rows), 'software_graded_rows': sum(row['software_pass'] is not None for row in rows),
            'infra_ungraded_rows': sum(row['software_pass'] is None for row in rows),
            'distinct_task_clusters': 2, 'one_cumulative_count_per_actual_uuid': True,
            'original_failures_wait_restart_and_recovery_preserved': True,
            'current_owned_cleanup_resolution_verified': True,
            'zero_model_failure_not_graded_or_retried': True,
            'quality_scope': 'Two exposed development tasks. O02 S02-S06 represent one common injected-success validation gap, not five independent defect families.',
            'clock_scope': 'Keep five original software trajectory clocks separate from the full zero-model failed preparation/wait/restart/recovery episode. No efficiency advantage may be inferred from the missing C0/O02 trajectory or its recovery time.',
            'cost_scope': 'Actual supplied product participant native prefix counters. No model-native trajectory exists for the authenticated zero-model failure. Its empty member set contributes no participant counters but remains assigned and ungraded. Unknown real member usage is never zero. Cache input and reasoning output are subsets. Research/backend currency remains unqualified.',
            'output_budget_excess_warning_only': True, 'paired_confidence_intervals_estimated': False,
            'heldout_confirmation': False, 'candidate_installed_or_promoted': False,
            'comparison_eligible': False, 'superiority_proven': False, 'goal_complete': False,
            'source_entities': sources, 'evidence_entities': evidence}


def summarize():
    value = payload()
    value['recorded_at'] = time.time()
    d.control.atomic_json(OUTPUT, value, exclusive=True)
    return value


if __name__ == '__main__':
    print(json.dumps({'status': 'read_only_v5_summary_no_allocation', 'superiority_proven': False}))
