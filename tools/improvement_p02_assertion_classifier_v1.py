"""Classify framework TestFailure events in an already closed machine trace.

Messages are diagnostic text, not exception type identities. Flutter's typed
isFailure field distinguishes TestFailure from ordinary execution exceptions.
"""
import json
from improvement_q04_verifier_v5 import machine, unique_object


def assertion_failure_names(log, expected_tests=24):
    closed = machine(log, expected_tests)
    if not closed['well_formed']:
        return set(), True
    names = set()
    ends = {}
    failures = []
    invalid = False
    tests = closed['tests']
    for line in log.splitlines():
        try:
            event = json.loads(line, object_pairs_hook=unique_object)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get('type') == 'testDone':
            ends[event['testID']] = event['result']
        elif event.get('type') == 'error':
            failures.append(event)
    for event in failures:
        if (event['isFailure'] is True and event['testID'] in tests
                and ends.get(event['testID']) == 'failure'):
            names.add(tests[event['testID']])
        else:
            invalid = True
    return names, invalid
