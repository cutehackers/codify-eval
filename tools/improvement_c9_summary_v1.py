"""Preserve all historical attempts and append source-bound C9 observations."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/improvement-v1/C9-development-summary-v1.json'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    if OUT.exists():
        raise ValueError('Summary already exists')
    pins = {str(Path(__file__).relative_to(ROOT)): sha(__file__)}
    def read(name):
        path = ROOT / name
        pins[name] = sha(path)
        return json.loads(path.read_text())
    def check(document):
        for key in ('source_hashes', 'source_sha256'):
            for name, digest in document.get(key, {}).items():
                path = Path(name) if Path(name).is_absolute() else ROOT / name
                assert sha(path) == digest, name
    def prefixes(values):
        for value in values:
            raw = Path(value['path']).read_bytes()
            length = value['prefix_bytes']
            assert type(length) is int and 0 < length <= len(raw)
            assert raw[:length].endswith(b'\n')
            assert hashlib.sha256(raw[:length]).hexdigest() == value['prefix_sha256']
    freeze = read('results/improvement-v1/C9-development-freeze-v1.json')
    check(freeze)
    previous = read('results/improvement-v1/C8-development-summary-v1.json')
    check(previous)
    prefixes(previous['native_source_prefix_pins'])
    rows = list(previous['rows'])
    assert len(rows) == 14
    assert {r['run_id'] for r in rows} == {r['run_id'] for r in freeze['historical_comparators']}
    native_pins = list(previous['native_source_prefix_pins'])
    for allocation in freeze['sequence']:
        run = allocation['run_id']
        base = 'results/' + run
        grade = read(base + '/grade.json')
        usage = read(base + '/usage.json')
        manifest = read(base + '/manifest.json')
        read(base + '/artifact-seal.json')
        pins[base + '/native-tools.jsonl'] = sha(ROOT / base / 'native-tools.jsonl')
        assert all(manifest[k] == allocation[k] for k in ('run_id', 'case_id', 'condition', 'repeat'))
        assert manifest['phase'] == 'control-probe-improvement-c9-v1'
        assert manifest['image_id'] == freeze['image_id']
        assert manifest['skill_hash'] == freeze['skill_hashes'][allocation['condition']]
        assert manifest['case_hash'] == freeze['case_hashes'][allocation['case_id']]
        assert manifest['evaluation_core'] == {'path': str(ROOT / 'results/improvement-v1/C9-development-freeze-v1.json'),
                                               'sha256': pins['results/improvement-v1/C9-development-freeze-v1.json']}
        assert manifest['model'] == 'gpt-6.1-sol' and manifest['effort'] == 'medium'
        assert grade['run_id'] == run
        assert grade['status'] in ('review_pending', 'evaluation_error'), 'Only original C9 outcomes supported'
        assert usage['native_completion_observed'] and len(usage['completions']) == 1
        assert usage['models'] and all(m == {'model': 'gpt-6.1-sol', 'effort': 'medium'} for m in usage['models'])
        pin = {'path': usage['native_source'], 'prefix_bytes': usage['source_bytes'],
               'prefix_sha256': usage['source_sha256']}
        prefixes([pin]); native_pins.append(pin)
        suffix = 'outcome' if grade['status'] == 'review_pending' else 'terminal'
        review_name = 'results/improvement-v1/' + allocation['case_id'] + '-C9-1-' + suffix + '-review-v1.json'
        review = read(review_name); check(review)
        assert review['run_id'] == run
        assert review['verdict'] in (('pass', 'PASS') if grade['status'] == 'review_pending' else ('fail',))
        if grade['status'] == 'review_pending':
            assert review['report_pass'] is True
        else:
            assert review['report_pass'] is False
            assert review['actual_attempt_disposition'] == 'evaluation_error: genuine transport boundary violation; first scoped repository command rejected expired original trajectory budget before implementation; no behavior grading or passing outcome'
        required = {base + '/' + name for name in ('grade.json', 'usage.json', 'manifest.json', 'artifact-seal.json', 'native-tools.jsonl')}
        assert required <= set(review['source_hashes'])
        counters = usage['usage']
        assert all(type(counters[k]) is int and counters[k] >= 0 for k in
                   ('input_tokens', 'cached_input_tokens', 'output_tokens', 'total_tokens'))
        assert counters['cached_input_tokens'] <= counters['input_tokens']
        completed = grade.get('behavior_pass') is True and grade.get('scope_pass') is True
        rows.append(dict(allocation, status='pass_after_independent_report_review' if completed else grade['status'],
            raw_grade_status=grade['status'], adjudicated_disposition=None,
            behavior_pass=grade.get('behavior_pass'), scope_pass=grade.get('scope_pass'),
            report_pass=review.get('report_pass') if grade['status'] == 'review_pending' else None, completed_task_pass=completed,
            native_reported_duration_seconds=sum(c['duration_ms'] / 1000 for c in usage['completions']),
            native_timestamp_elapsed_seconds=sum(c['completed_at'] - c['started_at'] for c in usage['completions']),
            dispatch_to_native_completion_seconds=max(c['completed_at'] for c in usage['completions']) - manifest['agent_started_at'],
            actor_wall_seconds=sum(c['duration_ms'] / 1000 for c in usage['completions']),
            input_tokens=counters['input_tokens'], cached_input_tokens=counters['cached_input_tokens'],
            uncached_input_tokens=counters['input_tokens'] - counters['cached_input_tokens'],
            output_tokens=counters['output_tokens'], total_tokens=counters['total_tokens'], actor_retries=0))
    assert len(rows) == 16 and len({r['run_id'] for r in rows}) == 16
    measures = ('actor_wall_seconds', 'input_tokens', 'cached_input_tokens',
                'uncached_input_tokens', 'output_tokens', 'total_tokens')
    totals = {condition: {m: sum(r[m] for r in rows if r['condition'] == condition) for m in measures}
              for condition in sorted({r['condition'] for r in rows})}
    report = {'status': 'adaptive_development_cohort_completed', 'rows': rows,
        'all_selected_attempts_so_far': len(rows),
        'valid_complete_task_passes_so_far': sum(r['completed_task_pass'] is True for r in rows),
        'raw_evaluation_error_records_preserved': sum(r['raw_grade_status'] == 'evaluation_error' for r in rows),
        'false_positive_records_with_separate_grade': sum(r.get('adjudicated_disposition') is not None for r in rows),
        'actual_evaluation_errors_so_far': sum(r['status'] == 'evaluation_error' for r in rows),
        'C9_totals': totals['C9'], 'condition_totals_all_allocated_attempts': totals,
        'C9_over_A_historical_ratios': None,
        'C9_over_C8_historical_ratios': None,
        'paired_performance_comparison_qualified': False,
        'timing_qualified': False,
        'superiority_proven': False, 'billable_currency_observed': False,
        'complete_final_cost': False, 'all_failures_and_waits_retained': True,
        'interpretation': 'Original D02 is an evaluation error before implementation with a forbidden send_message retained. Neither failed attempt cost nor waiting is excluded. C9 totals include both attempts but paired ratios are withheld because comparable completed software outcomes are missing. Native reported duration differs materially from timestamp elapsed on D02; both are retained and speed is unqualified. Actor interval excludes external grading/review/coordinator work. Historical controls, reused cases and single trials do not prove superiority.',
        'native_source_prefix_pins': native_pins, 'source_sha256': pins}
    with OUT.open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'C9_totals': totals['C9'], 'historical_A_ratios': report['C9_over_A_historical_ratios']}))

if __name__ == '__main__':
    main()
