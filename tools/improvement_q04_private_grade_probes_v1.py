"""Synthetic receipt classification regressions; no model or Docker evidence."""
import copy
import hashlib
import json
from pathlib import Path

from improvement_q04_private_grade_v1 import qualified_outcome
from improvement_q04_verifier_v5 import COMMANDS, machine


def receipt(failure=False):
    events = []
    for i in range(8):
        events.append({'type': 'testStart', 'test': {'id': i, 'name': 'synthetic ' + str(i)}})
        if failure and i == 7:
            events.append({'type': 'error', 'testID': i, 'error': 'synthetic assertion failed', 'isFailure': True})
        events.append({'type': 'testDone', 'testID': i, 'result': 'failure' if failure and i == 7 else 'success', 'skipped': False})
    events.append({'type': 'done', 'success': not failure})
    return {'status': 'completed', 'removed': True, 'source_unchanged': True,
            'checks': [{'inner_argv': list(argv), 'exit_code': 1 if failure and index == 1 else 0}
                       for index, argv in enumerate(COMMANDS)],
            'machine': machine('\n'.join(json.dumps(event) for event in events), 8)}


def main():
    cases = []
    def check(label, row, status, behavior, software):
        actual = qualified_outcome(row)
        expected = {'status': status, 'observed_behavior_pass': behavior,
                    'observed_software_checks_pass': software, 'overall_pass': None}
        assert actual == expected, (label, actual, expected)
        cases.append({'case': label, 'pass': True, 'outcome': actual})
    check('genuine_closed_eight_success', receipt(), 'review_pending', True, True)
    check('genuine_closed_eight_assertion_failure', receipt(True), 'review_pending', False, False)
    row = receipt(); row['checks'][2]['exit_code'] = 1
    check('analyzer_failure_keeps_behavior_distinct', row, 'review_pending', True, False)
    mutations = [
        ('nonterminal', lambda r: r.update(status='evaluation_error')),
        ('unremoved', lambda r: r.update(removed=False)),
        ('source_changed', lambda r: r.update(source_unchanged=False)),
        ('incomplete_machine', lambda r: r['machine'].update(well_formed=False)),
        ('wrong_test_count', lambda r: r['machine'].update(test_count=7)),
        ('missing_machine', lambda r: r.pop('machine')),
        ('missing_check', lambda r: r['checks'].pop()),
        ('wrong_actual_check', lambda r: r['checks'][1].update(inner_argv=['echo', 'pass'])),
        ('boolean_exit', lambda r: r['checks'][1].update(exit_code=False)),
        ('dependency_failure', lambda r: r['checks'][0].update(exit_code=1)),
        ('test_timeout', lambda r: r['checks'][1].update(exit_code=124)),
        ('test_killed', lambda r: r['checks'][1].update(exit_code=137)),
        ('analyzer_timeout', lambda r: r['checks'][2].update(exit_code=124)),
        ('untyped_machine_verdict', lambda r: r['machine'].update(pass_=None, **{'pass': None})),
    ]
    for label, mutate in mutations:
        row = copy.deepcopy(receipt(True)); mutate(row)
        check(label, row, 'evaluation_error', None, None)
    root = Path(__file__).resolve().parents[1]
    names = [Path(__file__).resolve(), root / 'tools/improvement_q04_private_grade_v1.py', root / 'tools/improvement_q04_verifier_v5.py']
    value = {'status': 'pass', 'tests_run': len(cases), 'cases': cases,
             'source_hashes': {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in names},
             'actual_actor_allocated': False, 'actual_docker_lifecycle_qualified': False,
             'launch_qualified': False, 'superiority_proven': False}
    with (root / 'results/improvement-v1/Q04-private-grade-probes-v1.json').open('x') as stream:
        json.dump(value, stream, indent=2)
    print(json.dumps({'status': 'pass', 'tests_run': len(cases)}))


if __name__ == '__main__':
    main()
