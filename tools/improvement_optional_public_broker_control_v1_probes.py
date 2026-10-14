"""Prelaunch controls of public transport driver, no Docker allocation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import improvement_optional_public_broker_control_v1 as driver


class PublicDriverControls(unittest.TestCase):
    def test_exact_exec_route_and_preserved_inner_failure(self):
        inner = {'exit_code': 7, 'stdout': '', 'stderr': 'original', 'output_complete': True}
        with patch.object(driver.broker, 'dispatch', return_value=({'status': 'ok', 'result': inner}, 0)) as dispatch:
            self.assertEqual(driver.transport('/run', 'worker1', 'cap', 'exit 7', 1), inner)
            dispatch.assert_called_once_with('/run', 'worker1', 'cap', 'exec', {'command': 'exit 7', 'seconds': 1})

    def test_failed_public_broker_is_not_successful_inner_process(self):
        with patch.object(driver.broker, 'dispatch', return_value=({'status': 'error', 'message': 'failed'}, 1)):
            with self.assertRaises(ValueError): driver.transport('/run', 'root', 'cap', 'x')

    def test_current_runtime_and_broker_reviews_required(self):
        self.assertEqual(driver.REVIEW.name, 'fresh-optional-runtime-prelaunch-review-v6.json')
        self.assertEqual(driver.BROKER_REVIEW.name, 'fresh-optional-public-broker-review-v3.json')
        self.assertEqual(driver.DRIVER_REVIEW.name, 'fresh-optional-public-broker-control-driver-review-v1.json')

    def test_conflicting_review_pins_cannot_mask_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source.py'; source.write_text('frozen')
            correct = driver.entity(source); wrong = dict(correct, sha256='0' * 64)
            files = []
            for index, pins in enumerate(({str(source): wrong}, {str(source): correct}, {str(source): correct})):
                p = root / f'review{index}.json'; p.write_text(json.dumps({'verdict': 'pass', 'issues': [], 'source_entities': pins})); files.append(p)
            with patch.object(driver, 'REVIEW', files[0]), patch.object(driver, 'DRIVER_REVIEW', files[1]), patch.object(driver, 'BROKER_REVIEW', files[2]):
                with self.assertRaises(ValueError): driver.freeze()


if __name__ == '__main__': unittest.main()
