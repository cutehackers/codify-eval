"""Error-close mock regressions; no actual allocation or cleanup qualification."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import improvement_question_failure_close_v1 as closer
import improvement_q01_dialogue_core_v1_probes as fixtures


class Probes(unittest.TestCase):
    def invoke(self, raw, terminal):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); run = 'control-probe-natural-question-v1-Q05-A-1'
            folder, out = root / 'runtime' / run, root / 'results' / run
            folder.mkdir(parents=True); out.mkdir(parents=True)
            source = root / 'actual-source.jsonl'; source.write_bytes(raw)
            binding = {'native_source': str(source), 'agent_path': fixtures.BINDING['agent_path'],
                       'native_session_id': fixtures.BINDING['actor_native_id'],
                       'parent_thread_id': fixtures.BINDING['parent_native_id']}
            (out / 'actor-binding.json').write_text(json.dumps(binding))
            metadata = {'run_id': run, 'started_at': 0, 'container': 'owned'}
            self.assertFalse((out / 'terminal-native.jsonl').exists())
            self.assertFalse((out / 'native-usage-v4.json').exists())
            with patch.object(closer, 'allocated_paths', return_value=(folder, out, metadata)), \
                    patch.object(closer, 'find_session', return_value=source), \
                    patch.object(closer.old, 'stop_owned', return_value={}) as stop, \
                    patch.object(closer.legacy.diagnostics, 'preserve_tmp', return_value={}), \
                    patch.object(closer.legacy, 'remove_owned', return_value={'removed': True}) as remove:
                value = closer.close(run, ValueError('source guard failed before collection'))
            self.assertEqual(value['actor_terminal_observed'], terminal)
            self.assertEqual((out / 'failure-native-prefix-v1.jsonl').read_bytes(), raw)
            if terminal:
                self.assertEqual(value['status'], 'evaluation_error')
                self.assertTrue(value['product_cleanup']['removed'])
                self.assertEqual((out / 'terminal-native.jsonl').read_bytes(), raw)
                self.assertTrue((out / 'grade.json').exists())
                self.assertIsNone(value['usage']['usage'])
                self.assertEqual(stop.call_count, 1)
                self.assertEqual(remove.call_count, 1)
            else:
                self.assertEqual(value['status'], 'awaiting_actor_terminal')
                self.assertFalse((out / 'grade.json').exists())
                self.assertTrue((out / 'failure-close-pending-v1.json').exists())
                self.assertEqual(stop.call_count, 0)
                self.assertEqual(remove.call_count, 0)
            return value

    def test_first_completed_only_no_collected_files_closes_and_keeps_null_cost(self):
        first, *_ = fixtures.fixture()
        self.invoke(fixtures.raw(first), True)

    def test_active_second_turn_does_not_stop_actor_or_container(self):
        first, _, actor, _, _ = fixtures.fixture()
        self.invoke(fixtures.raw(actor[:len(first) + 3]), False)

    def test_partial_native_preserved_without_fabricated_terminal_or_cost(self):
        first, *_ = fixtures.fixture()
        self.invoke(fixtures.raw(first) + b'{"unfinished":', False)

    def test_wrong_model_preserved_as_unqualified_not_repaired(self):
        first, *_ = fixtures.fixture()
        first[2]['payload']['model'] = 'deliberately-invalid-control'
        value = self.invoke(fixtures.raw(first), True)
        self.assertIn('qualified_model', value['usage']['metrics_unavailable'])
        self.assertEqual(value['usage']['models'][0]['model'], 'deliberately-invalid-control')


if __name__ == '__main__':
    unittest.main()
