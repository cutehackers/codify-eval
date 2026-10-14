"""Preserve all historical attempts and append source-bound C8 observations."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/improvement-v1/C8-development-summary-v1.json'

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
    freeze = read('results/improvement-v1/C8-development-freeze-v1.json')
    check(freeze)
    previous = read('results/improvement-v1/C6-development-summary-v4.json')
    check(previous)
    prefixes(previous['native_source_prefix_pins'])
    rows = list(previous['rows'])
    assert len(rows) == 12
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
        assert manifest['phase'] == 'control-probe-improvement-c8-v1'
        assert manifest['image_id'] == freeze['image_id']
        assert manifest['skill_hash'] == freeze['skill_hashes'][allocation['condition']]
        assert manifest['case_hash'] == freeze['case_hashes'][allocation['case_id']]
        assert manifest['evaluation_core'] == {'path': str(ROOT / 'results/improvement-v1/C8-development-freeze-v1.json'),
                                               'sha256': pins['results/improvement-v1/C8-development-freeze-v1.json']}
        assert manifest['model'] == 'gpt-6.1-sol' and manifest['effort'] == 'medium'
        assert grade['run_id'] == run
        assert grade['status'] == 'review_pending', 'Only these two original, non-adjudicated C8 outcomes are supported'
        assert usage['native_completion_observed'] and len(usage['completions']) == 1
        assert usage['models'] and all(m == {'model': 'gpt-6.1-sol', 'effort': 'medium'} for m in usage['models'])
        pin = {'path': usage['native_source'], 'prefix_bytes': usage['source_bytes'],
               'prefix_sha256': usage['source_sha256']}
        prefixes([pin]); native_pins.append(pin)
        review_name = 'results/improvement-v1/' + allocation['case_id'] + '-C8-1-outcome-review-v1.json'
        review = read(review_name); check(review)
        assert review['run_id'] == run and review['verdict'] in ('pass', 'PASS')
        assert review['report_pass'] is True
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
            report_pass=True, completed_task_pass=completed,
            actor_wall_seconds=sum(c['duration_ms'] / 1000 for c in usage['completions']),
            input_tokens=counters['input_tokens'], cached_input_tokens=counters['cached_input_tokens'],
            uncached_input_tokens=counters['input_tokens'] - counters['cached_input_tokens'],
            output_tokens=counters['output_tokens'], total_tokens=counters['total_tokens'], actor_retries=0))
    assert len(rows) == 14 and len({r['run_id'] for r in rows}) == 14
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
        'C8_totals': totals['C8'], 'condition_totals_all_allocated_attempts': totals,
        'C8_over_A_historical_ratios': {m: totals['C8'][m] / totals['A'][m] for m in measures},
        'C8_over_C6_historical_ratios': {m: totals['C8'][m] / totals['C6'][m] for m in measures},
        'superiority_proven': False, 'billable_currency_observed': False,
        'complete_final_cost': False, 'all_failures_and_waits_retained': True,
        'interpretation': 'Two reused cases per condition, one trial and historical controls are exploratory. Actor interval excludes external review/grading/coordinator work and is not full end-to-end wall. Quality/security superiority and money savings are unproven.',
        'native_source_prefix_pins': native_pins, 'source_sha256': pins}
    with OUT.open('x') as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({'C8_totals': totals['C8'], 'historical_A_ratios': report['C8_over_A_historical_ratios']}))

if __name__ == '__main__':
    main()
