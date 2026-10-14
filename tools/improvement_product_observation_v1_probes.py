"""Actual fixed-image compilation control and adversarial receipt probes."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import improvement_product_observation_v1 as observation
from prepare import ROOT


class Probes(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads((ROOT / 'runtime/protocol-probes/fresh-question-product-compile-error-v1/verification/receipt.json').read_bytes())
        self.sealed = deepcopy(self.receipt['source_before'])

    def classify(self, value=None, sealed=None):
        return observation.classify(self.receipt if value is None else value, 8,
                                    self.sealed if sealed is None else sealed, ['lib/implementation.dart'])

    def test_actual_compile_failure_is_software_failure_behavior_unknown(self):
        result = self.classify()
        self.assertTrue(result['complete_software_observation'])
        self.assertIs(result['software_pass'], False)
        self.assertIsNone(result['behavior_pass'])
        self.assertFalse(result['behavior_observed'])
        self.assertEqual(result['compiler_defects'][0]['source_sha256'], self.sealed['lib/implementation.dart']['sha256'])

    def test_cleanup_and_source_and_image_errors_stay_unknown(self):
        for key, value in [('removed', False), ('source_unchanged', False),
                           ('status', 'evaluation_error'), ('image_id', 'other'),
                           ('cleanup_errors', [{'reason': 'leaked'}])]:
            receipt = deepcopy(self.receipt); receipt[key] = value
            with self.subTest(key=key): self.assertFalse(self.classify(receipt)['complete_software_observation'])

    def test_timeout_dependency_failure_or_missing_commands_stay_unknown(self):
        for index, code in [(0, 1), (1, 124), (2, 137), (2, 0)]:
            receipt = deepcopy(self.receipt); receipt['checks'][index]['exit_code'] = code
            with self.subTest(index=index, code=code): self.assertFalse(self.classify(receipt)['complete_software_observation'])
        receipt = deepcopy(self.receipt); receipt['checks'].pop()
        self.assertFalse(self.classify(receipt)['complete_software_observation'])

    def test_changed_source_or_nonmatching_diagnostic_stays_unknown(self):
        sealed = deepcopy(self.sealed); sealed['lib/implementation.dart']['sha256'] = '0' * 64
        self.assertFalse(self.classify(sealed=sealed)['complete_software_observation'])
        receipt = deepcopy(self.receipt)
        receipt['checks'][2]['stdout'] = receipt['checks'][2]['stdout'].replace('lib/implementation.dart', 'lib/other.dart')
        self.assertFalse(self.classify(receipt)['complete_software_observation'])

    def test_truncated_or_missing_terminal_machine_stays_unknown(self):
        receipt = deepcopy(self.receipt)
        receipt['checks'][1]['stdout'] = '\n'.join(receipt['checks'][1]['stdout'].splitlines()[:-1])
        self.assertFalse(self.classify(receipt)['complete_software_observation'])


if __name__ == '__main__':
    unittest.main()
