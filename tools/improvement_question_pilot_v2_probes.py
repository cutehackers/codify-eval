"""Regression probes for adapter resolver, preflight cleanup and allocation gate.

Mocks exercise controller error paths. They are not native/container qualification.
"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import improvement_question_pilot_v2 as pilot


class Probes(unittest.TestCase):
    def test_preparation_resolver_assignment_does_not_recurse(self):
        with patch.object(pilot.preparation, 'case_directory', pilot.case_directory):
            self.assertEqual(pilot.preparation.case_directory('Q05'),
                             pilot.ROOT / 'improvement_cases/fresh-question-cohort-v2/Q05')
            self.assertEqual(pilot.case_directory('Q06'),
                             pilot.ROOT / 'improvement_cases/fresh-question-cohort-v2/Q06')

    def test_unregistered_case_is_rejected(self):
        with self.assertRaises(AssertionError): pilot.case_directory('Q01')

    def test_preflight_failure_preserves_raw_cost_and_owned_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); run = 'schema-cleanup-control'
            folder, out = root / 'runtime' / run, root / 'results' / run
            folder.mkdir(parents=True); out.mkdir(parents=True)
            raw = b'controller_mock_native_prefix\n'
            metadata = {'run_id': run, 'phase': pilot.PHASE, 'started_at': 0}
            (folder / 'run.json').write_text(json.dumps(metadata))
            (out / 'actor-binding.json').write_text('{}')
            (out / 'terminal-native.jsonl').write_bytes(raw)
            usage = {'source_sha256': pilot.core.digest(raw), 'native_completion_observed': True,
                     'usage': {'total_tokens': 7}}
            (out / 'native-usage-v4.json').write_text(json.dumps(usage))
            with patch.object(pilot, 'ROOT', root), \
                    patch.object(pilot, 'grade_original', side_effect=ValueError('preflight fault')), \
                    patch.object(pilot.legacy, 'owned_identity', return_value={'State': {'Running': False}}), \
                    patch.object(pilot.legacy, 'remove_owned', return_value={'removed': True}) as remove:
                value = pilot.grade(run)
            self.assertEqual(value['status'], 'evaluation_error')
            self.assertEqual(value['usage'], usage)
            self.assertTrue(value['product_cleanup']['removed'])
            self.assertEqual((out / 'terminal-native.jsonl').read_bytes(), raw)
            self.assertEqual(remove.call_count, 1)

    def test_pending_private_grading_blocks_next_allocation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / 'results' / 'first'; out.mkdir(parents=True)
            sequence = {'sequence': [{'run_id': 'first'}, {'run_id': 'second'}]}
            with patch.object(pilot.legacy, 'ROOT', root):
                for status in ('public_verified', 'grading_private'):
                    (out / 'grade.json').write_text(json.dumps({'status': status}))
                    with self.subTest(status=status), self.assertRaises(AssertionError):
                        pilot.legacy.next_allocation(sequence)

    def test_retained_grader_error_blocks_next_allocation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / 'results' / 'first'; out.mkdir(parents=True)
            (out / 'grade.json').write_text(json.dumps({
                'status': 'evaluation_error', 'product_cleanup': {'removed': True},
                'lifecycle_errors': [{'type': 'PublicVerifierCleanupUnproven'}]}))
            with patch.object(pilot.legacy, 'ROOT', root), self.assertRaises(AssertionError):
                pilot.legacy.next_allocation({'sequence': [{'run_id': 'first'}, {'run_id': 'second'}]})


if __name__ == '__main__':
    unittest.main()
