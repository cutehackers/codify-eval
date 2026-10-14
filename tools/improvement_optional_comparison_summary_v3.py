"""Descriptive frozen six-row development summary, including every failure.

No SDK, product rerun, grading, source rewrite, price or superiority admission.
Complete cost stays unknown if any original member's usage is unknown.
"""
import hashlib
import json

import improvement_optional_comparison_driver_v3 as driver

ROOT, BASE = driver.ROOT, driver.BASE
require = driver.require


def reviewed(row):
    path = BASE / (row['run_id'] + '-independent-review.json')
    raw = path.read_bytes()
    value = json.loads(raw)
    require(value.get('row') == row and value.get('verdict') == 'pass'
            and value.get('issues') == [] and all(value.get(key) is True for key in (
                'original_terminal_preservation_verified', 'owned_cleanup_verified',
                'all_failed_attempts_and_costs_preserved')), 'Every exact row needs preservation review')
    for category in ('source_entities', 'evidence_entities'):
        pins = value.get(category)
        require(isinstance(pins, dict) and bool(pins), 'Current typed row review pins required')
        for key, pin in pins.items():
            driver.control.reviewed_entity(ROOT / key, pin)
    root_check = BASE / (row['run_id'] + '-root-verification.json')
    check = json.loads(root_check.read_bytes())
    if row == driver.inputs.sequence()[0] and set(check) == {'all_current_pins_verified', 'review_entity'}:
        require(check['all_current_pins_verified'] is True
                and check['review_entity'] == driver.control.entity(path),
                'First-row original typed root verification must match current review')
    else:
        require(check.get('pass') is True
                and check.get('review_sha256') == hashlib.sha256(raw).hexdigest()
                and check.get('sources_verified') == len(value['source_entities'])
                and check.get('evidence_verified') == len(value['evidence_entities']),
                'Root must verify the current exact review before summary')
    return path, root_check


def payload():
    driver.admission()
    rows, evidence = [], {}
    conditions = {name: {'rows': 0, 'software_passes': 0, 'software_failures': 0,
                         'ungraded_errors': 0, 'observed_raw_tokens': 0,
                         'known_valid_partial_tokens': 0, 'unknown_usage_paths': [],
                         'whole_seconds_including_failures_and_recovery': 0.0}
                  for name in ('A', 'C0', 'C19')}
    native_ids = set()
    for row in driver.inputs.sequence():
        review, root_check = reviewed(row)
        folder = ROOT / 'runtime' / row['run_id']
        classified_path = folder / 'native-close/classified-outcome-v2.json'
        original_path = folder / 'native-close/outcome.json'
        classified = json.loads(classified_path.read_bytes())
        original = json.loads(original_path.read_bytes())
        require(classified.get('row') == row, 'Original classified row changed')
        final_path = original_path
        final = original
        status = 'normal_closed'
        if original.get('first_error') is not None:
            final_path = folder / 'errored-failure-close-v1/outcome.json'
            final = json.loads(final_path.read_bytes())
            require(final.get('row') == row
                    and final.get('first_error') == original['first_error']
                    and final.get('status') == 'preserved_errored_failure'
                    and final.get('software_pass') is None,
                    'Original ungraded failure and actual final recovery required')
            status = final['status']
        require(final.get('owned_cleanup_verified') is True,
                'Unresolved owned resources cannot enter completed summary')
        software = classified['classification']['software_pass']
        require(software is None or type(software) is bool, 'Boolean or unknown software outcome required')
        usage = final.get('usage') if status != 'normal_closed' else classified.get('usage')
        require(isinstance(usage, dict), 'Preserved actual usage ledger required')
        members = usage['members']
        ids = {member['native_session_id'] for member in members}
        require(len(ids) == len(members) and not native_ids.intersection(ids),
                'Actual product UUID may be counted only once')
        native_ids.update(ids)
        totals = usage.get('observed_prefix_totals')
        unknown = usage['unknown_usage_paths']
        require((totals is None) == bool(unknown), 'Unknown usage cannot become a complete total')
        partial = usage['known_valid_prefix_category_totals']['total_tokens']
        whole = final['whole_observed_seconds']
        require(whole >= 0, 'Original whole clock required')
        item = {'row': row, 'software_pass': software,
                'classification': classified['classification']['classification'],
                'expected_tests': classified['expected_tests'], 'final_status': status,
                'original_first_error': original.get('first_error'),
                'output_budget_warning_patterns': classified['output_warnings'],
                'observed_raw_tokens': None if totals is None else totals['total_tokens'],
                'known_valid_partial_tokens': partial, 'unknown_usage_paths': unknown,
                'whole_seconds_including_recovery': whole,
                'product_native_ids': sorted(ids), 'owned_cleanup_verified': True,
                'whole_final_cost_qualified': False}
        rows.append(item)
        aggregate = conditions[row['condition']]
        aggregate['rows'] += 1
        aggregate['software_passes' if software is True else
                  'software_failures' if software is False else 'ungraded_errors'] += 1
        aggregate['known_valid_partial_tokens'] += partial
        aggregate['unknown_usage_paths'].extend(unknown)
        if aggregate['observed_raw_tokens'] is not None:
            aggregate['observed_raw_tokens'] = (None if totals is None else
                                               aggregate['observed_raw_tokens'] + totals['total_tokens'])
        aggregate['whole_seconds_including_failures_and_recovery'] += whole
        for path in {review, root_check, classified_path, original_path, final_path}:
            evidence[path.relative_to(ROOT).as_posix()] = driver.control.entity(path)
    require(len(rows) == 6 and all(item['rows'] == 2 for item in conditions.values()),
            'Every originally frozen row must be retained')
    return {'study': 'fresh-optional-development-comparison-v3',
            'model': 'gpt-6.1-sol', 'reasoning': 'medium', 'rows': rows,
            'condition_totals': conditions, 'distinct_product_native_ids': sorted(native_ids),
            'output_budget_excess_is_warning_only': True,
            'all_original_errors_failed_checks_and_recovery_preserved': True,
            'scope': 'Two exposed development task clusters, one trial per condition and task',
            'software_quality_general_superiority_proven': False,
            'paired_confidence_intervals': None, 'untouched_final_confirmation': False,
            'cost_or_time_causal_superiority_proven': False,
            'whole_final_cost_qualified': False, 'billable_currency_observed': False,
            'external_research_cost_included': False,
            'comparison_admitted': False, 'superiority_proven': False,
            'source_entities': {'tools/improvement_optional_comparison_summary_v3.py':
                                driver.control.entity(__file__)},
            'evidence_entities': {**evidence, driver.FREEZE.relative_to(ROOT).as_posix():
                                  driver.control.entity(driver.FREEZE)}}


def write():
    value = payload()
    path = BASE / 'fresh-optional-development-comparison-summary-v3.json'
    driver.control.atomic_json(path, value, exclusive=True)
    return value


if __name__ == '__main__':
    value = write()
    print(json.dumps({'rows': len(value['rows']), 'condition_totals': value['condition_totals'],
                      'superiority_proven': False}))
