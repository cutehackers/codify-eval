"""Read-only six-row development summary, retaining the amended preparation.

No actors, SDK checks, retroactive regrading, billing or superiority inference.
"""
import json
from pathlib import Path
import time

import improvement_optional_comparison_driver_v4 as d

ROOT, BASE = d.ROOT, d.BASE
OUTPUT = BASE / 'fresh-optional-development-comparison-summary-v4-amended-v2.json'
COUNTERS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens',
            'output_tokens', 'reasoning_output_tokens', 'total_tokens')
FLAGS = ('original_terminal_preservation_verified', 'owned_cleanup_verified',
         'all_failed_attempts_and_costs_preserved')
require = d.require


def counters(value):
    require(isinstance(value, dict) and all(type(value.get(k)) is int and value[k] >= 0
                                          for k in COUNTERS), 'Exact native integer counters required')
    require(value['total_tokens'] == value['input_tokens'] + value['output_tokens']
            and value['cached_input_tokens'] <= value['input_tokens']
            and value['cache_write_input_tokens'] <= value['input_tokens']
            and value['reasoning_output_tokens'] <= value['output_tokens'],
            'Original counter totals/subsets inconsistent')
    return {k: value[k] for k in COUNTERS}


def tests(outcome, expected):
    names, passed, failed = {}, [], []
    for check in outcome['verification']['checks']:
        for line in check.get('stdout', '').splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get('type') == 'testStart':
                names[event['test']['id']] = event['test']['name']
            if event.get('type') == 'testDone' and not event.get('hidden'):
                require(event.get('skipped') is False and event['testID'] in names,
                        'Complete unskipped grading identities required')
                (passed if event['result'] == 'success' else failed).append(names[event['testID']])
    require(len(passed) + len(failed) == expected, 'Original exact closed test count required')
    return {'expected': expected, 'passed': len(passed), 'failed': len(failed),
            'failed_test_names': failed}



def validated_usage(usage, seen_uuids):
    require(isinstance(usage, dict)
            and usage.get('pending_allocation_slots') == []
            and usage.get('all_supplied_member_completions_observed') is True,
            'Actual supplied members must terminate')
    require(isinstance(usage.get('members'), list) and bool(usage['members']),
            'Explicit actual member list required')
    unknown = usage.get('unknown_usage_paths')
    require(isinstance(unknown, list)
            and all(isinstance(path, str) and bool(path) for path in unknown)
            and len(unknown) == len(set(unknown)),
            'Unknown paths must be explicit unique nonempty strings')
    known = {k: 0 for k in COUNTERS}
    members, derived_unknown, paths, local_uuids = [], [], set(), set()
    for member in usage['members']:
        require(isinstance(member, dict) and 'usage' in member,
                'Every member must explicitly report known or unknown usage')
        uid, path = member.get('native_session_id'), member.get('agent_path')
        require(isinstance(uid, str) and bool(uid)
                and uid not in seen_uuids and uid not in local_uuids,
                'Every actual native UUID must be counted once')
        require(isinstance(path, str) and bool(path) and path not in paths,
                'Every member must have a unique nonempty agent path')
        local_uuids.add(uid); paths.add(path)
        value = member['usage']
        if value is None:
            derived_unknown.append(path)
        else:
            for key, number in counters(value).items():
                known[key] += number
        members.append({'agent_path': path, 'native_session_id': uid,
                        'usage': value, 'metric_error': member.get('metric_error')})
    require(set(unknown) == set(derived_unknown),
            'Unknown paths must exactly identify all and only unknown member usage')
    require('observed_prefix_totals' in usage,
            'Original observed totals must explicitly report known or unknown')
    observed = usage['observed_prefix_totals']
    require((observed is None) == bool(derived_unknown),
            'Observed totals must be unknown if and only if any member usage is unknown')
    if observed is not None:
        require(counters(observed) == known,
                'Complete observed counters must match original actual members')
    if 'known_valid_prefix_category_totals' in usage:
        require(counters(usage['known_valid_prefix_category_totals']) == known,
                'Partial category counters must equal actual known members')
    if 'known_valid_prefix_totals_are_partial' in usage:
        require(type(usage['known_valid_prefix_totals_are_partial']) is bool
                and usage['known_valid_prefix_totals_are_partial'] == bool(derived_unknown),
                'Partial counter flag must preserve actual unknown membership')
    if 'distinct_uuid_count' in usage:
        require(type(usage['distinct_uuid_count']) is int
                and usage['distinct_uuid_count'] == len(local_uuids),
                'Declared member count must match actual distinct UUIDs')
    seen_uuids.update(local_uuids)
    return known, members, observed


def selected_row(row, sources, evidence, seen_uuids):
    review_path = BASE / (row['run_id'] + '-independent-review.json')
    review = json.loads(review_path.read_bytes())
    require(review.get('row') == row and review.get('verdict') == 'pass'
            and review.get('issues') == [] and all(review.get(k) is True for k in FLAGS),
            'Exact independently preserved original row required')
    for category, target in (('source_entities', sources), ('evidence_entities', evidence)):
        require(isinstance(review.get(category), dict) and bool(review[category]),
                'Typed original row closure required')
        for key, pin in review[category].items():
            actual = d.control.reviewed_entity(ROOT / key, pin)
            require(key not in target or target[key] == actual, 'Conflicting original row pins')
            target[key] = actual
    root_path = BASE / (row['run_id'] + '-root-verification.json')
    root = json.loads(root_path.read_bytes())
    require(root.get('verdict') == 'pass' and root.get('all_current_pins_verified') is True
            and root.get('review_entity') == d.control.entity(review_path)
            and root.get('source_entities_verified') == len(review['source_entities'])
            and root.get('evidence_entities_verified') == len(review['evidence_entities']),
            'Current exact root verification required')
    for path in (review_path, root_path):
        evidence[str(path.relative_to(ROOT))] = d.control.entity(path)
    folder = ROOT / 'runtime' / row['run_id']
    original_path = folder / 'native-close/outcome.json'
    classified_path = folder / 'native-close/classified-outcome-v3.json'
    for path in (original_path, classified_path):
        key = str(path.relative_to(ROOT))
        require(key in review['evidence_entities'], 'Original output must be independently pinned')
        d.control.reviewed_entity(path, review['evidence_entities'][key])
    original = json.loads(original_path.read_bytes())
    classified = json.loads(classified_path.read_bytes())
    expected = 24 if row['case_id'] == 'O01' else 30
    require(classified['row'] == row and classified['expected_tests'] == expected
            and original['first_error'] is None and original['owned_cleanup_verified'] is True
            and original['source_fences_unchanged'] is True,
            'Original completed software grading and cleanup required')
    grade = tests(original, expected)
    software = classified['classification']['software_pass']
    require(type(software) is bool and software == (grade['failed'] == 0)
            and software == original['software_combined_pass']
            and review['software_pass'] == software, 'Software outcome cannot be reclassified')
    usage = classified['usage']
    require(usage == original['usage'], 'Classified usage must preserve original outcome usage')
    known, members, observed = validated_usage(usage, seen_uuids)
    local_whole = original['whole_observed_seconds']
    require(type(local_whole) in (int, float) and local_whole >= 0
            and local_whole == classified['whole_observed_seconds'],
            'Original local runtime clock required')
    episode_whole = local_whole
    amended = row['run_id'] == 'optional-development-v4-O02-C0-1'
    amendment = None
    if amended:
        account_path = BASE / (row['run_id'] + '-all-preparation-attempts-observation-v2.json')
        key = str(account_path.relative_to(ROOT))
        require(key in review['evidence_entities'], 'Earlier preparation episode must be pinned')
        d.control.reviewed_entity(account_path, review['evidence_entities'][key])
        account = json.loads(account_path.read_bytes())
        require(account['row'] == row and account['original_failure_preserved'] is True
                and account['original_runtime_clock_continuity'] is False
                and account['earlier_runtime_local_start_unavailable'] is True
                and account['paired_efficiency_claim_from_amended_row_permitted'] is False
                and account['first_actual_runtime_whole_seconds'] == local_whole
                and account['outcome_entity'] == d.control.entity(original_path)
                and account['usage'] == original['usage'],
                'Explicit original failure/amended clock observation required')
        episode_whole = account['all_preparation_attempts_whole_seconds']
        wait = account['earlier_preallocation_failure_wait_and_repair_seconds']
        require(wait >= 0 and abs(episode_whole - local_whole - wait) < 0.000001,
                'No earlier waiting or repair may be discarded')
        amendment = {'earlier_preallocation_failure_wait_and_repair_seconds': wait,
                     'original_runtime_clock_continuity': False,
                     'earlier_runtime_local_start_unavailable': True,
                     'matched_efficiency_claim_permitted': False}
    return {'row': row, 'software_pass': software, 'tests': grade,
            'members': members, 'observed_native_totals': observed,
            'known_valid_partial_native_totals': known,
            'unknown_usage_paths': usage['unknown_usage_paths'],
            'first_actual_runtime_whole_seconds': local_whole,
            'all_recorded_preparation_attempts_whole_seconds': episode_whole,
            'preparation_amendment': amendment,
            'output_warnings': classified['output_warnings'],
            'output_warnings_have_quality_penalty': False,
            'owned_cleanup_verified': True}


def payload():
    frozen = d.admission()
    sources = dict(frozen['sources']); evidence = {}
    sources[str(Path(__file__).resolve().relative_to(ROOT))] = d.control.entity(__file__)
    evidence[str(d.FREEZE.relative_to(ROOT))] = d.control.entity(d.FREEZE)
    for name in ('tools/improvement_optional_comparison_summary_v4.py',
                 'results/improvement-v1/fresh-optional-development-comparison-summary-v4.json',
                 'results/improvement-v1/fresh-optional-development-comparison-summary-v4-independent-review.json'):
        evidence[name] = d.control.entity(ROOT / name)
    seen = set()
    rows = [selected_row(row, sources, evidence, seen) for row in d.inputs.sequence()]
    conditions = {}
    for name in ('A', 'C0', 'C20'):
        chosen = [r for r in rows if r['row']['condition'] == name]
        require(len(chosen) == 2, 'Two assigned cases per exact condition required')
        unknown = [p for r in chosen for p in r['unknown_usage_paths']]
        known = {k: sum(r['known_valid_partial_native_totals'][k] for r in chosen)
                 for k in COUNTERS}
        conditions[name] = {'rows': len(chosen),
                            'software_passed': sum(r['software_pass'] for r in chosen),
                            'software_failed': sum(not r['software_pass'] for r in chosen),
                            'observed_native_totals': None if unknown else known,
                            'known_valid_partial_native_totals': known,
                            'unknown_usage_paths': unknown,
                            'first_actual_runtime_whole_seconds':
                                sum(r['first_actual_runtime_whole_seconds'] for r in chosen),
                            'all_recorded_preparation_attempts_whole_seconds':
                                sum(r['all_recorded_preparation_attempts_whole_seconds'] for r in chosen),
                            'contains_amended_preparation_clock':
                                any(r['preparation_amendment'] is not None for r in chosen)}
    return {'study': 'frozen-optional-development-comparison-v4', 'derived_summary_revision': 2, 'seed': frozen['seed'],
            'model': frozen['model'], 'effort': frozen['effort'],
            'rows': rows, 'conditions': conditions,
            'distinct_actual_native_uuid_count': len(seen),
            'one_cumulative_native_count_per_actual_uuid': True,
            'all_assigned_software_failures_preserved': True,
            'all_owned_cleanup_verified': True,
            'output_budget_excess_warning_only': True,
            'quality_scope': 'Two exposed development tasks; O02 S02-S06 exercise one common '
                             'injected-success output validation gap, not five independent defect families.',
            'clock_scope': 'Keep first actual runtime clocks and all recorded preparation episodes separate. '
                           'C0/O02 has an amended first runtime and retained prior failure/wait/repair. '
                           'It cannot establish matched efficiency advantage.',
            'cost_scope': 'Observed product participant native counters, including failures/reviews/waiting. '
                          'Input/cache and output/reasoning subsets are not added twice. Unknowns are not zero. '
                          'This is neither currency nor a complete external-research/backend-generation ledger.',
            'distinct_task_clusters': 2, 'paired_confidence_intervals_estimated': False,
            'heldout_confirmation': False, 'candidate_installed_or_promoted': False,
            'comparison_eligible': False, 'superiority_proven': False, 'goal_complete': False,
            'source_entities': sources, 'evidence_entities': evidence}


def summarize():
    value = payload()
    value['recorded_at'] = time.time()
    d.control.atomic_json(OUTPUT, value, exclusive=True)
    return value


if __name__ == '__main__':
    print(json.dumps({'status': 'read_only_development_summary_no_allocation',
                      'superiority_proven': False}))
