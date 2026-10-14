"""Run a frozen private unittest suite and persist its normal completion.

No hostile-code isolation claim. Abrupt interpreter exit cannot complete this
runner. The outer helper separately fences private inputs and public scope.
"""
import json
from pathlib import Path
import sys
import unittest


def run(suite_path,result_path):
    target=Path(result_path)
    if target.exists():raise ValueError('Original test result cannot repeat')
    suite=unittest.defaultTestLoader.discover(suite_path,pattern='test_*.py')
    expected=suite.countTestCases()
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    value={'schema_version':1,'normal_runner_completion':True,'discovered':expected,
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skipped':len(result.skipped),'expected_failures':len(result.expectedFailures),
        'unexpected_successes':len(result.unexpectedSuccesses),'was_successful':result.wasSuccessful()}
    with target.open('x') as f:json.dump(value,f,sort_keys=True);f.write('\n')
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('private_suite_path unique_result_path required')
    raise SystemExit(run(sys.argv[1],sys.argv[2]))
