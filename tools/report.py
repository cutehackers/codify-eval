"""Aggregate recorded comparisons without turning missing evidence into success."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
FINAL = {'pass', 'fail'}


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else None


def recorded_status(grade):
    """An external contract verdict still needs independent report review."""
    if grade is None:
        return 'not_evaluated'
    status = grade.get('status', 'unknown')
    if status in FINAL and not grade.get('reviewer'):
        return 'review_pending'
    return status


def observed(values):
    known = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return {'known_count': len(known), 'unavailable_count': len(values) - len(known),
            'median': statistics.median(known) if known else None}


def efficiency(run_id):
    metadata = read_json(ROOT / 'runtime' / run_id / 'run.json') or {}
    usage = (metadata.get('native_usage') or {}).get('total_token_usage') or {}
    inp, cached = usage.get('input_tokens'), usage.get('cached_input_tokens')
    return {'elapsed_seconds': metadata.get('elapsed_seconds'),
            'total_tokens': usage.get('total_tokens'),
            'uncached_input_tokens': inp - cached
            if isinstance(inp, int) and isinstance(cached, int) and 0 <= cached <= inp else None}


def matched_efficiency(cases, candidate):
    """Compare complete, successful cases, not different mixes of tasks."""
    output = []
    phases = dict.fromkeys(phase for phase, _, _ in cases)
    for phase in phases:
        case_ids = list(dict.fromkeys(case for p, case, _ in cases if p == phase))
        for baseline, treatment in [('A', 'B'), ('A', candidate), ('B', candidate)]:
            eligible = [case for case in case_ids
                        if (phase, case, baseline) in cases and (phase, case, treatment) in cases]
            if not eligible:
                continue
            included, excluded = [], []
            for case in eligible:
                left, right = cases[(phase, case, baseline)], cases[(phase, case, treatment)]
                if not all(row['status'] in FINAL for row in left + right):
                    excluded.append({'case': case, 'reason': 'not_all_repeats_final'})
                    continue
                if not all(row['status'] == 'pass' for row in left + right):
                    excluded.append({'case': case, 'reason': 'not_all_repeats_successful'})
                    continue
                metrics = {}
                left_values = [efficiency(row['run_id']) for row in left]
                right_values = [efficiency(row['run_id']) for row in right]
                for key in ('elapsed_seconds', 'total_tokens', 'uncached_input_tokens'):
                    left_observed = observed([v[key] for v in left_values])
                    right_observed = observed([v[key] for v in right_values])
                    complete = not (left_observed['unavailable_count'] or
                                    right_observed['unavailable_count'])
                    a, b = left_observed['median'], right_observed['median']
                    metrics[key] = {'baseline': left_observed, 'treatment': right_observed,
                                    'median_difference': b - a if complete else None,
                                    'median_ratio': b / a if complete and a > 0 else None}
                included.append({'case': case, 'baseline_runs': [r['run_id'] for r in left],
                                 'treatment_runs': [r['run_id'] for r in right], 'metrics': metrics})
            output.append({'phase': phase, 'baseline': baseline, 'treatment': treatment,
                           'eligible_cases': len(eligible), 'included_cases': len(included),
                           'excluded': excluded, 'cases': included,
                           'across_case_median_ratios': {
                               key: observed([c['metrics'][key]['median_ratio'] for c in included])
                               for key in ('elapsed_seconds', 'total_tokens', 'uncached_input_tokens')}})
    return output


def aggregate(candidate='C0'):
    schedule_path = ROOT / 'results' / f'schedule-{candidate}.json'
    schedule = read_json(schedule_path)
    if schedule is None:
        raise ValueError(f'Missing schedule: {schedule_path}')
    groups = defaultdict(list)
    cases = defaultdict(list)
    states = Counter()
    rows = []
    for task in schedule['runs']:
        run_id = task['run_id']
        grade_path = ROOT / 'results' / run_id / 'grade.json'
        grade = read_json(grade_path)
        state = recorded_status(grade)
        states[state] += 1
        row = {**task, 'status': state, 'grade_file': str(grade_path) if grade else None}
        if grade:
            for key in ('behavior_pass', 'scope_pass', 'critical_violation', 'report_pass',
                        'verification_pass', 'overall_pass', 'error_category'):
                row[key] = grade.get(key)
        groups[(task['phase'], task['condition'])].append(row)
        cases[(task['phase'], task['case'], task['condition'])].append(row)
        rows.append(row)

    summaries = []
    for (phase, condition), items in groups.items():
        final = [r for r in items if r['status'] in FINAL]
        successful = [r for r in final if r['status'] == 'pass']
        elapsed, tokens, uncached_input = [], [], []
        for row in successful:
            metrics = efficiency(row['run_id'])
            elapsed.append(metrics['elapsed_seconds'])
            tokens.append(metrics['total_tokens'])
            uncached_input.append(metrics['uncached_input_tokens'])
        summaries.append({'phase': phase, 'condition': condition, 'planned': len(items),
                          'final_valid': len(final), 'states': dict(Counter(r['status'] for r in items)),
                          'behavior_pass': sum(r.get('behavior_pass') is True for r in final),
                          'scope_pass': sum(r.get('scope_pass') is True for r in final),
                          'critical_violation': sum(r.get('critical_violation') is True for r in final),
                          'report_pass': sum(r.get('report_pass') is True for r in final),
                          'verification_pass': sum(r.get('verification_pass') is True for r in final)
                          if phase == 'software' else None,
                          'metric_availability': {
                              key: {'known_count': sum(type(r.get(key)) is bool for r in final),
                                    'unavailable_count': sum(type(r.get(key)) is not bool for r in final)}
                              for key in ('behavior_pass', 'scope_pass', 'critical_violation',
                                          'report_pass', 'verification_pass')},
                          'efficiency_success_only': {'elapsed_seconds': observed(elapsed),
                                                      'total_tokens': observed(tokens),
                                                      'uncached_input_tokens': observed(uncached_input)}})
    case_summaries = [{'phase': phase, 'case': case, 'condition': condition,
                       'planned': len(items), 'states': dict(Counter(r['status'] for r in items)),
                       'all_repeats_final': all(r['status'] in FINAL for r in items)}
                      for (phase, case, condition), items in cases.items()]
    archived = []
    for path in sorted((ROOT / 'results' / 'invalid-attempts').glob('*/*/grade.json')):
        grade = read_json(path)
        archived.append({'run_id': path.parents[1].name, 'attempt': path.parent.name,
                         'status': grade.get('status'), 'evidence': str(path),
                         'error_category': grade.get('error_category', grade.get('reason')),
                         'confirmed_protocol_calls': grade.get('confirmed_collaboration_tool_calls'),
                         'original_transport_audit_count': grade.get('original_transport_violation_count')})
    grading_recoveries = []
    for path in sorted((ROOT / 'results').glob('*/revisions/*/recovered-grading-attempt-*.json')):
        record = read_json(path)
        history = [path.parent / name.split('/')[-1] for name in record['previous_attempts']]
        grading_recoveries.append({
            'run_id': path.parents[2].name, 'evidence': str(path),
            'external_grading_attempt_number': record['external_grading_attempt_number'],
            'actor_reexecuted': record['actor_reexecuted'],
            'same_artifact_post_recovery_resumption_count': record['same_artifact_post_recovery_resumption_count'],
            'actor_repo_hash_unchanged': record['actor_repo_hash_unchanged'],
            'turn_hash_unchanged': record['turn_hash_unchanged'],
            'previous_attempts': [{'evidence': str(source), 'available': source.exists(),
                                   'status': (read_json(source) or {}).get('status')}
                                  for source in history]})
    return {'candidate': candidate, 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'schedule_sha256': hashlib.sha256(schedule_path.read_bytes()).hexdigest(),
            'reporter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'planned_comparisons': schedule['count'], 'states': dict(states),
            'comparisons_finished': all(r['status'] in FINAL for r in rows),
            'groups': summaries, 'cases': case_summaries, 'runs': rows,
            'matched_case_efficiency': matched_efficiency(cases, candidate),
            'archived_invalid_attempts': archived,
            'external_grading_recoveries': grading_recoveries,
            'notes': ['Pilots and fixture validation are excluded from comparison results.',
                      'Unfinished or invalid runs are not inferred to pass or included as valid performance.',
                      'Efficiency uses successful runs only; unavailable usage is not zero.',
                      'Group efficiency is descriptive; comparative efficiency uses cases with all repeats successful in both conditions.',
                      'Matched efficiency excludes failures and therefore does not measure overall performance or causal savings.',
                      'Archived invalid actor attempts and external grading infrastructure attempts remain separate from final valid comparisons.',
                      'Successful-trajectory efficiency excludes discarded invalid attempts and external grading recovery costs; it is not total evaluation cost.',
                      'Phases measure different capabilities and are reported separately.',
                      'Dataset completion does not prove overall goal completion or skill superiority.',
                      'Repeated three-run observations do not establish statistical certainty.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', default='C0')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    report = aggregate(args.candidate)
    if args.write:
        destination = ROOT / 'results' / f'analysis-{args.candidate}.json'
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('candidate', 'planned_comparisons', 'states',
                                                  'comparisons_finished', 'archived_invalid_attempts')},
                     ensure_ascii=False, indent=2))
