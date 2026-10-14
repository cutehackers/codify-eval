"""Observer/producer closure integration controls. Mocks are not native qualification."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import improvement_question_watch_v6 as watch
import improvement_q01_dialogue_core_v1_probes as fixtures


class Probes(unittest.TestCase):
    def invoke(self, status, usage_name='native-usage-v4.json', removed=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); out = root / 'results' / 'control'; out.mkdir(parents=True)
            raw = fixtures.raw(fixtures.fixture()[0]); source = root / 'actor.jsonl'; source.write_bytes(raw)
            (out / 'launch-intent.json').write_text(json.dumps({'started_at': 0}))
            (out / 'grade.json').write_text(json.dumps({'status': status, 'product_cleanup': {'removed': removed}}))
            (out / usage_name).write_text(json.dumps({'native_completion_observed': True, 'source_sha256': watch.core.digest(raw)}))
            # A wrong contract must not close at first observation. The second
            # mocked observation ends this probe rather than waiting1200s.
            rows = [{'task_complete': True, 'deadline_reached': False}, {'task_complete': True, 'deadline_reached': True}]
            with patch.object(watch, 'ROOT', root), patch.object(watch, 'find_session', return_value=source), \
                    patch.object(watch.time, 'time', return_value=20), patch.object(watch.time, 'sleep') as sleep, \
                    patch.object(watch, 'observation', side_effect=rows):
                value = watch.supervise('control', fixtures.BINDING['agent_path'])
            return value, sleep.call_count

    def test_actual_usage_v4_contract_closes_after_product_cleanup(self):
        for status in ['review_pending', 'public_verified', 'grading_private', 'evaluation_error']:
            with self.subTest(status=status):
                value, sleeps = self.invoke(status)
                self.assertTrue(value['controller_closed'])
                self.assertEqual(sleeps, 0)

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
