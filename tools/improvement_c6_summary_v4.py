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

    freeze = read('results/improvement-v1/C6-development-freeze-v1.json')
    check_pins(freeze)
    allocations = freeze['historical_comparators'] + freeze['sequence']
    assert len(allocations) == 12 and len({r['run_id'] for r in allocations}) == 12
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
        manifest = read(f'{base}/manifest.json')
        assert all(manifest.get(k) == allocation[k] for k in ('run_id', 'case_id', 'condition', 'repeat'))
        assert manifest['model'] == 'gpt-6.1-sol' and manifest['effort'] == 'medium'
        assert grade['run_id'] == run
        raw_grade_status = grade['status']
        disposition = None
        if run == 'control-probe-improvement-c6-v1-D02-C6-1':
            assert grade['status'] == 'evaluation_error' and grade['reason'] == 'transport boundary violated'
            adjudication = read('results/improvement-v1/D02-C6-1-transport-adjudication-v1.json')
            check_pins(adjudication)
            assert adjudication['verdict'] == 'false_positive_proven' and len(adjudication['poll_proofs']) == len(grade['violations']) == 2
            plan = read('results/improvement-v1/D02-C6-1-derived-grade-freeze-v2.json')
            check_pins(plan)
            plan_review = read('results/improvement-v1/D02-C6-1-derived-grade-plan-review-v2.json')
            check_pins(plan_review)
            assert plan_review['verdict'] == 'pass' and plan['original_run_id'] == run
            derived = read('results/improvement-v1/D02-C6-1-derived-external-grade-v2.json')
            assert derived['original_run_id'] == run and derived['grading_id'] == plan['derivative_grading_id']
            assert derived['plan_sha256'] == pins['results/improvement-v1/D02-C6-1-derived-grade-freeze-v2.json']
            assert derived['plan_review_sha256'] == pins['results/improvement-v1/D02-C6-1-derived-grade-plan-review-v2.json']
            assert derived['actor_reexecuted'] is False and derived['canonical_grade_replaced'] is False and derived['original_files_and_sources_unchanged'] is True
            assert [c['command'] for c in derived['checks']] == ['flutter pub get --offline', 'flutter test --no-pub --machine', 'flutter analyze --no-pub']
            assert derived['behavior_pass'] == all(c['exit_code'] == 0 for c in derived['checks'])
            grade = {**derived, 'run_id': run, 'case_id': allocation['case_id']}
            disposition = 'two raw poll flags independently proven false-positive; original raw error and all costs retained, first derived external grade used'
        if grade['status'] == 'evaluation_error':
            assert grade.get('case_id', allocation['case_id']) == allocation['case_id']
            assert grade.get('behavior_pass') is None and grade.get('scope_pass') is None
            behavior = scope = None
        else:
            assert grade['case_id'] == allocation['case_id']
            behavior, scope = grade['behavior_pass'], grade['scope_pass']
            assert isinstance(behavior, bool) and isinstance(scope, bool)
        report = None
        if grade['status'] != 'evaluation_error':
            review_name = 'results/improvement-v1/D02-C6-1-derived-outcome-review-v2.json' if disposition else f'results/improvement-v1/{allocation["case_id"]}-{allocation["condition"]}-1-outcome-review-v1.json'
            review = read(review_name)
            check_pins(review)
            if disposition:
                assert review['original_run_id'] == run and review['derived_grading_id'] == plan['derivative_grading_id']
                required_review_pins = [
                    'results/improvement-v1/D02-C6-1-derived-external-grade-v2.json',
                    'results/improvement-v1/D02-C6-1-derived-grade-freeze-v2.json',
                    'results/improvement-v1/D02-C6-1-derived-grade-plan-review-v2.json',
                    'results/improvement-v1/D02-C6-1-transport-adjudication-v1.json',
                    *[f'{base}/{name}' for name in ['grade.json', 'manifest.json', 'usage.json', 'artifact-seal.json', 'turns.json', 'native-tools.jsonl']],
                    f'runtime/{run}/commands.jsonl', f'runtime/{run}/run.json',
                ]
                for name in required_review_pins:
                    assert review['source_hashes'][name] == pins.get(name, hashlib.sha256((ROOT / name).read_bytes()).hexdigest()), name
            assert review['verdict'] == 'pass' and isinstance(review['report_pass'], bool)
            report = review['report_pass']
        passed = behavior is True and scope is True and report is True
        u = usage['usage']
        rows.append({**allocation, 'status': 'pass_after_independent_report_review' if passed else grade['status'],
                     'raw_grade_status': raw_grade_status, 'adjudicated_disposition': disposition,
                     'behavior_pass': behavior, 'scope_pass': scope,
                     'report_pass': report, 'completed_task_pass': passed,
                     'actor_wall_seconds': usage['completions'][0]['duration_ms'] / 1000,
                     'input_tokens': u['input_tokens'], 'cached_input_tokens': u['cached_input_tokens'],
                     'uncached_input_tokens': u['input_tokens'] - u['cached_input_tokens'],
                     'output_tokens': u['output_tokens'], 'total_tokens': u['total_tokens'],
                     'actor_retries': 0, 'invalid_reason': grade.get('reason') if grade['status'] == 'evaluation_error' else None})
    metrics = ['actor_wall_seconds', 'input_tokens', 'cached_input_tokens', 'uncached_input_tokens', 'output_tokens', 'total_tokens']
    c6_rows = [r for r in rows if r['condition'] == 'C6']
    a_rows = [r for r in rows if r['condition'] == 'A']
    assert len(c6_rows) == len(a_rows) == 2
    assert {r['case_id'] for r in a_rows} == {r['case_id'] for r in c6_rows}
    totals = {k: sum(row[k] for row in c6_rows) for k in metrics}
    ratios = {k: totals[k] / sum(row[k] for row in a_rows) for k in metrics}
    result = {'status': 'adaptive_development_cohort_completed', 'rows': rows,
              'all_selected_attempts_so_far': len(rows),
              'valid_complete_task_passes_so_far': sum(r['completed_task_pass'] for r in rows),
              'raw_evaluation_error_records_preserved': sum(r['raw_grade_status'] == 'evaluation_error' for r in rows),
              'false_positive_records_with_separate_grade': sum(r['adjudicated_disposition'] is not None for r in rows),
              'actual_evaluation_errors_so_far': sum(r['status'] == 'evaluation_error' for r in rows),
              'C6_totals': totals, 'C6_over_A_historical_ratios': ratios,
              'condition_totals_all_allocated_attempts': {
                  condition: {k: sum(r[k] for r in rows if r['condition'] == condition) for k in metrics}
                  for condition in sorted({r['condition'] for r in rows})},
              'superiority_proven': False, 'billable_currency_observed': False,
              'all_failures_and_waits_retained': True,
              'interpretation': 'Two reused development cases per condition with one trial each and historical comparators are exploratory. Passing tests cannot establish quality/security superiority; token counts are not billable currency. The actual evaluation error remains in allocated attempt totals.',
              'runtime_tier': 'Dart unit and filesystem behavior via Flutter runner; no GUI/device/power-loss claim',
              'native_source_prefix_pins': native_prefix_pins, 'source_sha256': pins}
    destination = ROOT / 'results/improvement-v1/C6-development-summary-v4.json'
    with destination.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
