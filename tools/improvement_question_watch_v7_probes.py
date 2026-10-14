"""Observer/producer closure integration controls. Mocks are not native qualification."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import improvement_question_watch_v7 as watch
import improvement_q01_dialogue_core_v1_probes as fixtures


class Probes(unittest.TestCase):
    def invoke(self, status, usage_name='native-usage-v4.json', removed=True, removed_at=20, clock=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); out = root / 'results' / 'control'; out.mkdir(parents=True)
            raw = fixtures.raw(fixtures.fixture()[0]); source = root / 'actor.jsonl'; source.write_bytes(raw)
            (out / 'launch-intent.json').write_text(json.dumps({'started_at': 0}))
            (out / 'grade.json').write_text(json.dumps({'status': status, 'product_cleanup': {'removed': removed, 'finished_at': removed_at}}))
            (out / usage_name).write_text(json.dumps({'native_completion_observed': True, 'source_sha256': watch.core.digest(raw)}))
            # A wrong contract must not close at first observation. The second
            # mocked observation ends this probe rather than waiting1200s.
            rows = [{'task_complete': True, 'deadline_reached': False}, {'task_complete': True, 'deadline_reached': True}]
            with patch.object(watch, 'ROOT', root), patch.object(watch, 'find_session', return_value=source), \
                    patch.object(watch.time, 'time', side_effect=clock, return_value=20), patch.object(watch.time, 'sleep') as sleep, \
                    patch.object(watch, 'observation', side_effect=rows):
                value = watch.supervise('control', fixtures.BINDING['agent_path'])
            return value, sleep.call_count

    def test_actual_usage_v4_contract_closes_after_product_cleanup(self):
        for status in ['review_pending', 'public_verified', 'grading_private', 'evaluation_error']:
            with self.subTest(status=status):
                value, sleeps = self.invoke(status)
                self.assertTrue(value['controller_closed'])
                self.assertEqual(sleeps, 0)

    def test_sample_start_before_removal_has_later_proven_completion(self):
        value, sleeps = self.invoke('review_pending', removed_at=22, clock=[20, 20, 20, 20.1, 25])
        self.assertEqual(value['observation_started_at'], 20)
        self.assertEqual(value['product_cleanup_finished_at'], 22)
        self.assertEqual(value['observation_completed_at'], 25)
        self.assertEqual(value['source_read_completed_at'], 20.1)
        self.assertEqual(len(value['grade_sha256']), 64)
        self.assertEqual(len(value['usage_sha256']), 64)
        self.assertEqual(sleeps, 0)

    def test_slow_verification_cannot_hide_completion_cadence(self):
        with self.assertRaisesRegex(ValueError, 'completion clock or cadence'):
            self.invoke('review_pending', removed_at=22, clock=[20, 20, 20, 20.1, 31])

    def test_cleanup_after_sample_completion_cannot_close(self):
        with self.assertRaisesRegex(ValueError, 'cleanup completion timestamp unproven'):
            self.invoke('review_pending', removed_at=26, clock=[20, 20, 20, 20.1, 25])

    def test_unknown_cleanup_timestamp_cannot_close(self):
        with self.assertRaisesRegex(ValueError, 'cleanup completion timestamp unproven'):
            self.invoke('review_pending', removed_at=None)

    def test_wrong_usage_filename_cannot_close_observer(self):
        value, sleeps = self.invoke('review_pending', 'native-usage-v5.json')
        self.assertFalse(value.get('controller_closed', False))
        self.assertEqual(sleeps, 1)

    def test_native_completion_without_product_cleanup_cannot_close(self):
        value, sleeps = self.invoke('review_pending', removed=False)
        self.assertFalse(value['controller_closed'])
        self.assertEqual(sleeps, 1)

if __name__ == '__main__':
    unittest.main()
