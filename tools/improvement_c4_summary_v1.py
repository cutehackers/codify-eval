"""Derived exploratory summary, preserving canonical grades and all attempts."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    pins = {}

    def read(relative):
        path = ROOT / relative
        raw = path.read_bytes()
        pins[relative] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    freeze = read('results/improvement-v1/C4-development-freeze-v1.json')
    for name, digest in freeze['source_hashes'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    history = read('results/improvement-v1/development-cohort-v2-summary.json')
    c3 = read('results/improvement-v1/C3-development-summary-v1.json')
    rows = []
    for allocation in freeze['sequence']:
        run = allocation['run_id']
        base = f'results/{run}'
        grade = read(f'{base}/grade.json')
        usage = read(f'{base}/usage.json')
        read(f'{base}/artifact-seal.json')
        native = ROOT / base / 'native-tools.jsonl'
        pins[f'{base}/native-tools.jsonl'] = hashlib.sha256(native.read_bytes()).hexdigest()
        review = read(f'results/improvement-v1/{allocation["case_id"]}-C4-1-outcome-review-v1.json')
        for field in ('source_hashes', 'source_sha256'):
            for name, digest in review.get(field, {}).items():
                path = Path(name) if Path(name).is_absolute() else ROOT / name
                assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
        assert review['verdict'] == 'pass' and isinstance(review['report_pass'], bool)
        assert grade['run_id'] == run and grade['case_id'] == allocation['case_id']
        assert usage['native_completion_observed']
        assert len(usage['completions']) == 1
        assert usage['models'] and all(m == {'model': 'gpt-6.1-sol', 'effort': 'medium'} for m in usage['models'])
        u = usage['usage']
        passed = grade['behavior_pass'] is True and grade['scope_pass'] is True and review['report_pass']
        rows.append({**allocation, 'status': 'pass_after_independent_report_review' if passed else grade['status'],
                     'behavior_pass': grade['behavior_pass'], 'scope_pass': grade['scope_pass'],
                     'report_pass': review['report_pass'], 'completed_task_pass': passed,
                     'actor_wall_seconds': usage['completions'][0]['duration_ms'] / 1000,
                     'input_tokens': u['input_tokens'], 'cached_input_tokens': u['cached_input_tokens'],
                     'uncached_input_tokens': u['input_tokens'] - u['cached_input_tokens'],
                     'output_tokens': u['output_tokens'], 'total_tokens': u['total_tokens'],
                     'actor_retries': 0})
    metrics = ['actor_wall_seconds', 'input_tokens', 'cached_input_tokens', 'uncached_input_tokens', 'output_tokens', 'total_tokens']
    totals = {k: sum(row[k] for row in rows) for k in metrics}
    a_rows = [r for r in history['rows'] if r['condition'] == 'A']
    assert {r['case_id'] for r in a_rows} == {r['case_id'] for r in rows} and len(a_rows) == len(rows)
    ratios = {k: totals[k] / sum(row[k] for row in a_rows) for k in metrics}
    result = {'status': 'adaptive_development_cohort_completed', 'rows': rows,
              'all_selected_attempts_so_far': c3['all_selected_attempts_so_far'] + len(rows),
              'valid_complete_task_passes_so_far': c3['valid_complete_task_passes_so_far'] + sum(r['completed_task_pass'] for r in rows),
              'actual_evaluation_errors_so_far': c3['actual_evaluation_errors_so_far'] + sum(r['status'] == 'evaluation_error' for r in rows),
              'C4_totals': totals, 'C4_over_A_historical_ratios': ratios,
              'superiority_proven': False, 'billable_currency_observed': False,
              'all_C4_failures_and_waits_retained': True,
              'interpretation': 'Two reused development cases with one trial each and historical comparators are exploratory. Passing tests cannot establish quality/security superiority, and token counts are not billable currency.',
              'runtime_tier': 'Dart unit and filesystem behavior via Flutter runner; no GUI/device/power-loss claim',
              'source_sha256': pins}
    destination = ROOT / 'results/improvement-v1/C4-development-summary-v1.json'
    with destination.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
