"""Read-only all-assigned v6 development observation, including evaluator failure.

No allocation, retry, regrading, billing, candidate promotion or superiority proof.
"""
import json
import math
from pathlib import Path
import time

import improvement_optional_comparison_driver_v8 as d
import improvement_optional_comparison_summary_v6 as preserved

ROOT, BASE = d.ROOT, d.BASE
OUTPUT = BASE / 'fresh-optional-development-comparison-summary-v6-amended-v1.json'
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


def completed_evaluator_failure(row, review, seen):
    require(d.runtime.encoded(row) == d.runtime.encoded(d.inputs.sequence()[0])
            and review.get('software_pass') is None,
            'Exact original ungraded evaluator-failure row required')
    folder = ROOT / 'runtime' / row['run_id']
    original = pinned(folder / 'native-close/outcome.json', review)
    classified = pinned(folder / 'native-close/classified-outcome-v7.json', review)
    failure = pinned(folder / 'completed-failure-close-v6/outcome.json', review)
    error = {'type': 'ValueError', 'message': 'Latest inventory must be unfiltered'}
    require(d.runtime.encoded(original['first_error']) == d.runtime.encoded(error)
            and d.runtime.encoded(failure['first_error']) == d.runtime.encoded(error)
            and original.get('usage') is None and classified['usage'] is None
            and classified['classification']['software_pass'] is None
            and classified['classification']['classification'] == 'evaluation_error'
            and failure['status'] == 'preserved_completed_failure'
            and failure['software_pass'] is None and failure['owned_cleanup_verified'] is True
            and d.runtime.encoded(failure['row']) == d.runtime.encoded(row),
            'Original failed close and genuine preservation must stay distinct')
    require(not (folder / 'native-close/combined-verifier').exists()
            and not (folder / 'native-close/combined-verifier').is_symlink(),
            'An ungraded failed close must not acquire a private grader result')
    usage = failure['usage']
    known, members, observed = preserved.validated_usage(usage, seen)
    require(usage['all_supplied_member_completions_observed'] is True
            and usage['allocation_proof_prefixes_matched'] is True,
            'Actual original completed product members required')
    first = original['whole_observed_seconds']; whole = failure['whole_observed_seconds']
    clocks = [first, whole, original['original_started_at'], original['finished_at'],
              failure['original_started_at'], failure['started_at'], failure['finished_at']]
    require(all(type(value) in (int, float) and math.isfinite(value) and value >= 0
                for value in clocks)
            and d.runtime.encoded(original['original_started_at'])
                == d.runtime.encoded(failure['original_started_at'])
            and d.runtime.encoded(first) == d.runtime.encoded(classified['whole_observed_seconds'])
            and abs(first - original['finished_at'] + original['original_started_at']) < 0.000001
            and abs(whole - failure['finished_at'] + failure['original_started_at']) < 0.000001
            and original['finished_at'] <= failure['started_at'] <= failure['finished_at']
            and whole >= first,
            'Keep the continuous original clock and every failed-close/recovery interval')
    return {'row': row, 'classification': 'infra_ungraded_completed_evaluator_failure',
            'software_pass': None, 'tests': None, 'members': members,
            'product_native_trajectory_applicable': True, 'observed_native_totals': observed,
            'known_valid_partial_native_totals': known, 'unknown_usage_paths': usage['unknown_usage_paths'],
            'first_actual_runtime_whole_seconds': whole,
            'all_recorded_run_episode_seconds': whole,
            'evaluator_failure': {'original_error': error,
                                  'original_failed_close_whole_seconds': first,
                                  'failed_close_through_preservation_seconds': whole - first,
                                  'continuous_whole_includes_first_failure_not_added_twice': True,
                                  'private_grading_performed': False,
                                  'product_model_retry_performed': False},
            'owned_cleanup_verified': True,
            'owned_cleanup_scope': 'Original completed product IDs removed by qualified failure preservation',
            'output_warnings': classified['output_warnings'],
            'output_warnings_have_quality_penalty': False}


def observer_terminal_receipt(folder, review):
    path = folder / 'terminal-resource-cleanup-v1/observer-terminal-parent-prefix-v1.jsonl'
    key = str(path.relative_to(ROOT))
    require(key in review['evidence_entities'], 'Exact original observer terminal source must be reviewed')
    d.reviewed_entity(path, review['evidence_entities'][key])
    raw = path.read_bytes()
    require(raw.endswith(b'\n'), 'Complete original parent prefix required')
    events = [json.loads(line) for line in raw.splitlines()]
    require(events[0]['payload']['id'] == '01a122a7-1f52-7810-8588-f0a7a8732fa1',
            'Original observer coordinator identity required')
    call_id = 'call_c8062ca93aa7480dbb670e20befbf747'
    calls = [e['payload'] for e in events if e.get('type') == 'response_item'
             and e.get('payload', {}).get('type') == 'custom_tool_call'
             and e['payload'].get('call_id') == call_id]
    returns = [e['payload'] for e in events if e.get('type') == 'response_item'
               and e.get('payload', {}).get('type') == 'custom_tool_call_output'
               and e['payload'].get('call_id') == call_id]
    require(len(calls) == len(returns) == 1 and calls[0]['name'] == 'exec'
            and calls[0]['input'].startswith('text(await tools.write_stdin({session_id:86320,chars:"","yield_time_ms":1000,"max_output_tokens":300}));\n'),
            'Exact original observer handle and empty poll join required')
    blocks = returns[0]['output']
    require(isinstance(blocks, list) and len(blocks) == 3
            and all(isinstance(b, dict) and set(b) == {'type', 'text'}
                    and b['type'] == 'input_text' and isinstance(b['text'], str) for b in blocks)
            and blocks[0]['text'].startswith('Script completed\n'), 'Original terminal renderer required')
    terminal = json.loads(blocks[1]['text'])
    require(type(terminal.get('exit_code')) is int and terminal['exit_code'] == 1
            and terminal.get('session_id') is None and terminal.get('chunk_id') == 'c70efe'
            and isinstance(terminal.get('output'), str)
            and terminal['output'].endswith('ValueError: Exact coordinator stop intent required\n'),
            'Genuine original observer terminal failure required')
    return {'call_id': call_id, 'session_id': 86320, 'exit_code': terminal['exit_code'],
            'parent_prefix_entity': d.control.entity(path), 'output_truncated': True,
            'scope': 'Observed terminal code and visible exact traceback; truncated earlier sample output remains incomplete'}


def completed_route_failure(row, review, seen):
    require(d.runtime.encoded(row) == d.runtime.encoded(d.inputs.sequence()[5])
            and review.get('software_pass') is None, 'Exact original ungraded route-failure row required')
    folder = ROOT / 'runtime' / row['run_id']
    original = pinned(folder / 'native-close/outcome.json', review)
    classified = pinned(folder / 'native-close/classified-outcome-v7.json', review)
    failed = pinned(folder / 'completed-failure-close-v6/outcome.json', review)
    cleanup = pinned(folder / 'terminal-resource-cleanup-v1/outcome.json', review)
    error = {'type': 'ValueError', 'message': 'Wrong broker run/job/capability/script'}
    closure_error = {'type': 'ValueError', 'message': 'Coordinator actor activity after terminal authority'}
    require(d.runtime.encoded(original['first_error']) == d.runtime.encoded(error)
            and d.runtime.encoded(failed['first_error']) == d.runtime.encoded(error)
            and d.runtime.encoded(cleanup['original_error']) == d.runtime.encoded(error)
            and d.runtime.encoded(failed['closure_error']) == d.runtime.encoded(closure_error)
            and d.runtime.encoded(cleanup['preservation_closure_error']) == d.runtime.encoded(closure_error)
            and classified['classification'] == {'software_pass': None, 'classification': 'evaluation_error'}
            and classified['usage'] is None and original.get('usage') is None
            and failed['status'] == 'closure_incomplete' and failed['owned_cleanup_verified'] is False
            and cleanup['status'] == 'owned_resources_removed_original_errors_retained'
            and cleanup['owned_cleanup_verified'] is True and cleanup['software_pass'] is None
            and cleanup['grading_performed'] is False and cleanup['product_retry_performed'] is False
            and cleanup['native_qualified'] is False, 'Keep original route, closure and cleanup outcomes distinct')
    require(not (folder / 'native-close/combined-verifier').exists()
            and not (folder / 'native-close/combined-verifier').is_symlink(), 'No private regrading allowed')
    usage = cleanup['usage']
    require(d.runtime.encoded(usage) == d.runtime.encoded(failed['usage']), 'Actual member usage must stay exact')
    known, members, observed = preserved.validated_usage(usage, seen)
    require(usage['all_supplied_member_completions_observed'] is True
            and usage['allocation_proof_prefixes_matched'] is True, 'Original completed member usage required')
    start = original['original_started_at']
    episodes = [original, failed, cleanup]
    require(all(type(v) in (int, float) and math.isfinite(v) and v >= 0
                for item in episodes for v in [item['original_started_at'], item['started_at'],
                                               item['finished_at'], item['whole_observed_seconds']])
            and all(d.runtime.encoded(item['original_started_at']) == d.runtime.encoded(start)
                    and abs(item['whole_observed_seconds'] - item['finished_at'] + start) < 0.000001
                    for item in episodes)
            and original['finished_at'] <= failed['started_at'] <= failed['finished_at']
                <= cleanup['started_at'] <= cleanup['finished_at']
            and d.runtime.encoded(original['whole_observed_seconds'])
                == d.runtime.encoded(classified['whole_observed_seconds']), 'Original continuous clock required')
    stop = pinned(folder / 'native-observer/stop.json', review)
    require(stop == {'reason': 'coordinator_stop', 'root_path': row['actor_path'],
                     'scope': 'terminal-owned-resource-cleanup-only-no-native-qualification'},
            'Keep original invalid stop unchanged')
    terminal_receipt = observer_terminal_receipt(folder, review)
    whole = cleanup['whole_observed_seconds']
    return {'row': row, 'classification': 'route_admission_ungraded_completed_failure',
            'software_pass': None, 'tests': None, 'members': members,
            'product_native_trajectory_applicable': True, 'observed_native_totals': observed,
            'known_valid_partial_native_totals': known, 'unknown_usage_paths': usage['unknown_usage_paths'],
            'first_actual_runtime_whole_seconds': whole, 'all_recorded_run_episode_seconds': whole,
            'evaluator_failure': {'original_error': error, 'failure_close_error': closure_error,
                'observer_stop_error': {'type': 'ValueError', 'message': 'Exact coordinator stop intent required'},
                'observer_exit_code': terminal_receipt['exit_code'],
                'observer_terminal_receipt': terminal_receipt, 'observer_runtime_qualified': False,
                'original_failed_close_whole_seconds': original['whole_observed_seconds'],
                'failed_preservation_whole_seconds': failed['whole_observed_seconds'],
                'continuous_whole_includes_failures_not_added_twice': True,
                'private_grading_performed': False, 'product_model_retry_performed': False},
            'owned_cleanup_verified': True,
            'owned_cleanup_scope': 'Separate exact-ID cleanup, not successful original normal or native closure',
            'output_warnings': classified['output_warnings'], 'output_warnings_have_quality_penalty': False}


def selected(row, sources, evidence, seen):
    review = closure(row, sources, evidence)
    if d.runtime.encoded(row) == d.runtime.encoded(d.inputs.sequence()[0]):
        return completed_evaluator_failure(row, review, seen)
    if d.runtime.encoded(row) == d.runtime.encoded(d.inputs.sequence()[5]):
        return completed_route_failure(row, review, seen)
    folder = ROOT / 'runtime' / row['run_id']
    original = pinned(folder / 'native-close/outcome.json', review)
    classified = pinned(folder / 'native-close/classified-outcome-v7.json', review)
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
    require(all(type(value) in (int, float) and math.isfinite(value) and value >= 0
                for value in [original['original_started_at'], original['started_at'], original['finished_at']])
            and original['original_started_at'] <= original['started_at'] <= original['finished_at']
            and abs(whole - original['finished_at'] + original['original_started_at']) < 0.000001,
            'Whole clock must be bound to actual original start and finish')
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
    for condition in ('A', 'C0', 'C22'):
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
            'actual_software_trajectory_whole_seconds': sum(row['first_actual_runtime_whole_seconds'] for row in group if row['software_pass'] is not None),
            'all_recorded_run_episodes_seconds': sum(row['all_recorded_run_episode_seconds'] for row in group),
            'complete_assigned_software_trajectories': all(row['software_pass'] is not None for row in group),
            'matched_efficiency_claim_permitted': False}
    return {'study': 'frozen-optional-development-comparison-v6', 'seed': frozen['seed'],
            'model': frozen['model'], 'effort': frozen['effort'], 'rows': rows,
            'conditions': conditions, 'distinct_actual_native_uuid_count': len(seen),
            'assigned_rows': len(rows), 'software_graded_rows': sum(row['software_pass'] is not None for row in rows),
            'infra_ungraded_rows': sum(row['software_pass'] is None for row in rows),
            'distinct_task_clusters': 2, 'one_cumulative_count_per_actual_uuid': True,
            'original_failures_wait_restart_and_recovery_preserved': True,
            'current_owned_cleanup_resolution_verified': True,
            'completed_evaluator_failure_not_graded_or_retried': True,
            'quality_scope': 'Two exposed development tasks. O02 S02-S06 represent one common injected-success validation gap, not five independent defect families.',
            'clock_scope': 'Retain every actual product clock, including ungraded C0/O01 evaluator failure and A/O01 route failure, incomplete preservation and separate cleanup. Each continuous whole includes its original failures exactly once. The A/O01 observer exit1 remains unqualified. Graded-only clocks are separately labelled, never substituted for all-assigned efficiency. No advantage may be inferred from evaluator recovery overhead.',
            'cost_scope': 'Actual supplied product participant native prefix counters from all six original model trajectories, including the ungraded evaluator-failure trajectory. Every distinct UUID counts once. Unknown real member usage is never zero. Cache input and reasoning output are subsets. Research/backend currency remains unqualified.',
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
    print(json.dumps({'status': 'read_only_v6_summary_no_allocation', 'superiority_proven': False}))
