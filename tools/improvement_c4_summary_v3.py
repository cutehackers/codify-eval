"""Recompute exploratory metrics from every frozen allocation, never cached totals."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    pins = {}
    native_prefix_pins = []
    pins[str(Path(__file__).relative_to(ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def read(relative):
        raw = (ROOT / relative).read_bytes()
        pins[relative] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    def check_pins(document):
        for field in ('source_hashes', 'source_sha256'):
            for name, digest in document.get(field, {}).items():
                path = Path(name) if Path(name).is_absolute() else ROOT / name
                assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name

    freeze = read('results/improvement-v1/C4-development-freeze-v1.json')
    check_pins(freeze)
    allocations = freeze['historical_comparators'] + freeze['sequence']
    assert len(allocations) == 10 and len({r['run_id'] for r in allocations}) == 10
    rows = []
    for allocation in allocations:
        run = allocation['run_id']
        base = f'results/{run}'
        grade = read(f'{base}/grade.json')
        usage = read(f'{base}/usage.json')
        read(f'{base}/artifact-seal.json')
        native = (ROOT / base / 'native-tools.jsonl').read_bytes()
        pins[f'{base}/native-tools.jsonl'] = hashlib.sha256(native).hexdigest()
        raw_source = Path(usage['native_source']).read_bytes()
        length = usage['source_bytes']
        assert isinstance(length, int) and length > 0 and len(raw_source) >= length
        prefix = raw_source[:length]
        assert prefix.endswith(b'\n')
        assert hashlib.sha256(prefix).hexdigest() == usage['source_sha256']
        native_prefix_pins.append({'path': usage['native_source'], 'prefix_bytes': length, 'prefix_sha256': usage['source_sha256']})
        assert usage['native_completion_observed'] and len(usage['completions']) == 1
        assert usage['models'] and all(m == {'model': 'gpt-6.1-sol', 'effort': 'medium'} for m in usage['models'])
        assert grade['run_id'] == run and grade['case_id'] == allocation['case_id']
        report = None
        if grade['status'] != 'evaluation_error':
            review = read(f'results/improvement-v1/{allocation["case_id"]}-{allocation["condition"]}-1-outcome-review-v1.json')
            check_pins(review)
            assert review['verdict'] == 'pass' and isinstance(review['report_pass'], bool)
            report = review['report_pass']
        passed = grade['behavior_pass'] is True and grade['scope_pass'] is True and report is True
        u = usage['usage']
        rows.append({**allocation, 'status': 'pass_after_independent_report_review' if passed else grade['status'],
                     'behavior_pass': grade['behavior_pass'], 'scope_pass': grade['scope_pass'],
                     'report_pass': report, 'completed_task_pass': passed,
                     'actor_wall_seconds': usage['completions'][0]['duration_ms'] / 1000,
                     'input_tokens': u['input_tokens'], 'cached_input_tokens': u['cached_input_tokens'],
                     'uncached_input_tokens': u['input_tokens'] - u['cached_input_tokens'],
                     'output_tokens': u['output_tokens'], 'total_tokens': u['total_tokens'],
                     'actor_retries': 0})
    metrics = ['actor_wall_seconds', 'input_tokens', 'cached_input_tokens', 'uncached_input_tokens', 'output_tokens', 'total_tokens']
    c4_rows = [r for r in rows if r['condition'] == 'C4']
    a_rows = [r for r in rows if r['condition'] == 'A']
    assert len(c4_rows) == len(a_rows) == 2
    assert {r['case_id'] for r in a_rows} == {r['case_id'] for r in c4_rows}
    totals = {k: sum(row[k] for row in c4_rows) for k in metrics}
    ratios = {k: totals[k] / sum(row[k] for row in a_rows) for k in metrics}
    result = {'status': 'adaptive_development_cohort_completed', 'rows': rows,
              'all_selected_attempts_so_far': len(rows),
              'valid_complete_task_passes_so_far': sum(r['completed_task_pass'] for r in rows),
              'actual_evaluation_errors_so_far': sum(r['status'] == 'evaluation_error' for r in rows),
              'C4_totals': totals, 'C4_over_A_historical_ratios': ratios,
              'condition_totals_all_allocated_attempts': {
                  condition: {k: sum(r[k] for r in rows if r['condition'] == condition) for k in metrics}
                  for condition in sorted({r['condition'] for r in rows})},
              'superiority_proven': False, 'billable_currency_observed': False,
              'all_failures_and_waits_retained': True,
              'interpretation': 'Two reused development cases per condition with one trial each and historical comparators are exploratory. Passing tests cannot establish quality/security superiority; token counts are not billable currency. The actual evaluation error remains in allocated attempt totals.',
              'runtime_tier': 'Dart unit and filesystem behavior via Flutter runner; no GUI/device/power-loss claim',
              'native_source_prefix_pins': native_prefix_pins, 'source_sha256': pins}
    destination = ROOT / 'results/improvement-v1/C4-development-summary-v3.json'
    with destination.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
