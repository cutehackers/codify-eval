import copy
import json
import unittest

import improvement_optional_result_classification_v1 as subject


def receipt(success=True):
    events = [{'type': 'testStart', 'test': {'id': 1, 'name': 'behavior'}},
              {'type': 'testDone', 'testID': 1, 'result': 'success' if success else 'failure', 'skipped': False},
              {'type': 'done', 'success': success}]
    log = '\n'.join(json.dumps(event) for event in events)
    checks = [{'inner_argv': command, 'exit_code': 0, 'stdout': '', 'stderr': ''}
              for command in subject.verifier.COMMANDS]
    checks[1].update(stdout=log, exit_code=0 if success else 1)
    return {'status': 'completed', 'first_error': None, 'removed': True,
            'source_unchanged': True, 'cleanup_errors': [],
            'expected_nonloading_tests': 1, 'checks': checks,
            'machine': subject.verifier.machine(log, 1), 'pass': success}


class Classification(unittest.TestCase):
    def test_closed_behavior_results(self):
        self.assertIs(subject.classify(receipt(), 1)['software_pass'], True)
        self.assertIs(subject.classify(receipt(False), 1)['software_pass'], False)
        for success in (True, False):
            self.assertIs(subject.classify(json.loads(json.dumps(receipt(success))), 1)['software_pass'], success)

    def test_infrastructure_never_becomes_product_failure(self):
        base = receipt(False)
        changes = [('status', 'evaluation_error'), ('removed', False),
                   ('source_unchanged', False), ('cleanup_errors', ['failed']),
                   ('first_error', {'message': 'deadline'}), ('expected_nonloading_tests', True)]
        for key, value in changes:
            value_receipt = copy.deepcopy(base); value_receipt[key] = value
            with self.subTest(key=key):
                self.assertIsNone(subject.classify(value_receipt, 1)['software_pass'])
        for index, code in [(0, 1), (1, 124), (1, 137), (2, 1)]:
            value_receipt = copy.deepcopy(base); value_receipt['checks'][index]['exit_code'] = code
            self.assertIsNone(subject.classify(value_receipt, 1)['software_pass'])

    def test_partial_and_forged_machine_rejected(self):
        for mutation in ['truncate', 'forge', 'bool_count', 'nan_count', 'bool_exit', 'command']:
            value = receipt(False)
            if mutation == 'truncate': value['checks'][1]['stdout'] = value['checks'][1]['stdout'].rsplit('\n', 1)[0]
            if mutation == 'forge': value['machine']['well_formed'] = False
            if mutation == 'bool_count': value['machine']['test_count'] = True
            if mutation == 'nan_count': value['machine']['test_count'] = float('nan')
            if mutation == 'bool_exit': value['checks'][1]['exit_code'] = True
            if mutation == 'command': value['checks'][1]['inner_argv'] = ['other']
            self.assertIsNone(subject.classify(value, 1)['software_pass'])

    def test_closed_loader_error_is_not_behavior_failure(self):
        value = receipt()
        events = [json.loads(line) for line in value['checks'][1]['stdout'].splitlines()]
        loader = [{'type': 'testStart', 'test': {'id': 2, 'name': 'loading file'}},
                  {'type': 'error', 'testID': 2, 'error': 'Compiler failed to load test file', 'isFailure': False},
                  {'type': 'testDone', 'testID': 2, 'result': 'error', 'skipped': False}]
        events = loader + events[:-1] + [{'type': 'done', 'success': False}]
        value['checks'][1].update(stdout='\n'.join(json.dumps(event) for event in events), exit_code=1)
        value['machine'] = subject.verifier.machine(value['checks'][1]['stdout'], 1)
        value['pass'] = False
        self.assertTrue(value['machine']['well_formed'])
        self.assertIsNone(subject.classify(value, 1)['software_pass'])

    def test_saved_multidigit_test_ids(self):
        value = receipt()
        events = []
        for identifier in (2, 10):
            events.extend([{'type': 'testStart', 'test': {'id': identifier, 'name': 'behavior'}},
                           {'type': 'testDone', 'testID': identifier, 'result': 'success', 'skipped': False}])
        events.append({'type': 'done', 'success': True})
        value['checks'][1]['stdout'] = '\n'.join(json.dumps(event) for event in events)
        value['expected_nonloading_tests'] = 2
        value['machine'] = subject.verifier.machine(value['checks'][1]['stdout'], 2)
        self.assertIs(subject.classify(json.loads(json.dumps(value)), 2)['software_pass'], True)


if __name__ == '__main__':
    unittest.main()
