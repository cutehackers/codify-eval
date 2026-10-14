"""Qualified receipt metadata for private grading, without reply selection.

Returned contracts contain no test bodies or reference implementations. For
question tasks, selection still requires an independently authenticated delivery.
This catalog does not authorize that delivery or admit a model comparison.
"""
import improvement_baseline_case_catalog_v1 as public

ROOT = public.ROOT
require = public.require
encoded = public.encoded
qualified_public_contract = public.qualified_public_contract
declared_execution = public.declared_execution
SUMMARY = public.BASE / 'baseline-pilot-sdk-qualification-v2/summary-public.json'


def receipt_contract(observation):
    require(type(observation) is dict and observation.get('qualified') is True
            and observation.get('cleanup_removed') is True
            and observation.get('source_unchanged') is True
            and observation.get('behavior_failure') is False,
            'Successful qualified unchanged-source receipt required')
    name = observation['receipt_path']
    require(type(name) is str, 'Exact receipt path required')
    path = public.materializer.canonical(ROOT / name)
    require(path.is_relative_to(ROOT / 'runtime/independent-baseline-pilot-fixture-qualification-v2'),
            'Receipt outside qualified SDK trajectory')
    public.historical.control.reviewed_entity(path, observation['receipt_entity'])
    receipt = public.read(path)
    require(receipt.get('status') == 'completed' and receipt.get('pass') is True
            and receipt.get('removed') is True and receipt.get('source_unchanged') is True
            and receipt.get('first_error') is None and receipt.get('cleanup_errors') == [],
            'Original qualified receipt must be successful and removed')
    count = receipt.get('expected_nonloading_tests')
    machine = receipt.get('machine')
    require(type(count) is int and count > 0 and type(machine) is dict
            and machine.get('pass') is True and machine.get('well_formed') is True
            and type(machine.get('test_count')) is int and machine['test_count'] == count,
            'Exact positive nonloading machine test count required')
    checks = receipt.get('checks')
    require(type(checks) is list and len(checks) == 3,
            'Exactly three qualified SDK commands required')
    argv = []
    for check in checks:
        require(type(check) is dict and type(check.get('exit_code')) is int
                and check['exit_code'] == 0 and type(check.get('inner_argv')) is list
                and bool(check['inner_argv'])
                and all(type(arg) is str and bool(arg) for arg in check['inner_argv']),
                'Successful exact string-list SDK command required')
        argv.append(list(check['inner_argv']))
    public.historical.control.reviewed_entity(path, observation['receipt_entity'])
    return {'receipt_path': name, 'receipt_entity': observation['receipt_entity'],
            'expected_nonloading_tests': count, 'inner_argv': argv}


def qualified_receipt_contracts(case_id):
    qualified_public_contract(case_id)
    review = public.read(public.REVIEW)
    entity = review['evidence_entities'][str(SUMMARY.relative_to(ROOT))]
    public.historical.control.reviewed_entity(SUMMARY, entity)
    summary = public.read(SUMMARY)
    require(summary.get('executed') == 50 and summary.get('planned_executions') == 50
            and summary.get('all_plan_rows_executed_exactly_once') is True
            and summary.get('original_sources_unchanged') is True,
            'Complete original SDK qualification required')
    groups = {}
    for purpose, expected in (('starter_public', 1),
                              ('reference', 2 if case_id in ('B03', 'B04') else 1),
                              ('negative_reference', 1 if case_id in ('B03', 'B04') else 0)):
        selected = [row for row in summary['observations']
                    if row['case'] == case_id and row['purpose'] == purpose]
        require(len(selected) == expected, 'Exact qualified receipt membership required')
        groups[purpose] = [receipt_contract(row) for row in selected]
    public.historical.control.reviewed_entity(SUMMARY, entity)
    return {'case_id': case_id, 'summary_entity': entity,
            'public': groups['starter_public'][0],
            'private_reference_candidates': groups['reference'],
            'unresolved_negative_controls': groups['negative_reference'],
            'selected_private_reference': None,
            'private_grade_authorized': False, 'model_pilot_admitted': False}
