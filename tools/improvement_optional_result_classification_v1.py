"""Classify completed grader evidence without converting infrastructure to failure.

No allocation, cleanup, admission or native lifecycle authority is granted here.
Compilation failures require separately authenticated product diagnostics. An
incomplete machine stream alone cannot distinguish compilation from infra.
"""
import json

import improvement_q04_verifier_v5 as verifier


def classify(receipt, expected_tests=24):
    unknown = {'software_pass': None, 'classification': 'evaluation_error'}
    if (type(expected_tests) is not int or expected_tests <= 0
            or receipt.get('status') != 'completed'
            or receipt.get('first_error') is not None
            or receipt.get('removed') is not True
            or receipt.get('source_unchanged') is not True
            or receipt.get('cleanup_errors') != []
            or receipt.get('artifact_errors', []) != []
            or type(receipt.get('expected_nonloading_tests')) is not int
            or receipt.get('expected_nonloading_tests') != expected_tests):
        return unknown
    checks = receipt.get('checks')
    if not isinstance(checks, list) or len(checks) != 3:
        return unknown
    for check, command in zip(checks, verifier.COMMANDS):
        if (not isinstance(check, dict) or check.get('inner_argv') != command
                or type(check.get('exit_code')) is not int
                or not isinstance(check.get('stdout'), str)
                or not isinstance(check.get('stderr'), str)):
            return unknown
    # Only closed semantic test failures are qualified automatically. Pubget,
    # compiler/analyzer failures and timeouts require a separate diagnosis.
    if checks[0]['exit_code'] != 0 or checks[2]['exit_code'] != 0:
        return unknown
    machine = verifier.machine(checks[1]['stdout'], expected_tests)
    def encoded(value):
        # JSON object keys are strings on disk. Normalize before sorting so
        # multi-digit test IDs have the same order before and after saving.
        normalized = json.loads(json.dumps(value, allow_nan=False))
        return json.dumps(normalized, sort_keys=True, separators=(',', ':'), allow_nan=False)
    try:
        identical_machine = encoded(receipt.get('machine')) == encoded(machine)
    except (TypeError, ValueError):
        return unknown
    if not identical_machine or not machine['well_formed']:
        return unknown
    if machine['pass'] and checks[1]['exit_code'] == 0 and receipt.get('pass') is True:
        return {'software_pass': True, 'classification': 'software_pass'}
    if (not machine['pass'] and checks[1]['exit_code'] == 1
            and receipt.get('pass') is False):
        events = []
        for line in checks[1]['stdout'].splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                events.append(event)
        # A loader/compiler error can coexist with a closed test stream. Only
        # assertion failures attached to nonloading behavioral tests qualify.
        behavior = set(machine['tests'])
        failures = [event for event in events if event.get('type') == 'testDone'
                    and event.get('result') != 'success']
        errors = [event for event in events if event.get('type') == 'error']
        if (failures and all(event['testID'] in behavior and event['result'] == 'failure' for event in failures)
                and all(event.get('isFailure') is True and event.get('testID') in behavior for event in errors)):
            return {'software_pass': False, 'classification': 'software_failure'}
    return unknown
