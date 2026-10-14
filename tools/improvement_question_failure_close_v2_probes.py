"""Error-close mock regressions; no actual allocation or cleanup qualification."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import improvement_question_failure_close_v2 as closer
import improvement_question_pilot_v4 as pilot
import improvement_q01_dialogue_core_v1_probes as fixtures


class Probes(unittest.TestCase):
    def invoke(self, raw, terminal, parent_raw=None, resume_raw=None, append_at_stop=None, via_grade=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); run = 'control-probe-natural-question-v1-Q05-A-1'
            folder, out = root / 'runtime' / run, root / 'results' / run
            folder.mkdir(parents=True); out.mkdir(parents=True)
            source = root / 'actual-source.jsonl'; source.write_bytes(raw)
            parent = root / 'parent.jsonl'
            parent.write_bytes(parent_raw if parent_raw is not None else fixtures.raw(fixtures.fixture()[3][:1]))
            binding = {'native_source': str(source), 'parent_source': str(parent), 'agent_path': fixtures.BINDING['agent_path'],
                       'native_session_id': fixtures.BINDING['actor_native_id'],
                       'parent_thread_id': fixtures.BINDING['parent_native_id']}
            (out / 'actor-binding.json').write_text(json.dumps(binding))
            metadata = {'run_id': run, 'started_at': 0, 'container': 'owned'}
            self.assertFalse((out / 'terminal-native.jsonl').exists())
            self.assertFalse((out / 'native-usage-v4.json').exists())
            with patch.object(closer, 'allocated_paths', return_value=(folder, out, metadata)), \
                    patch.object(closer, 'find_session', return_value=source), \
                    patch.object(closer.old, 'stop_owned', side_effect=(lambda _: source.write_bytes(append_at_stop)) if append_at_stop else None, return_value={}) as stop, \
                    patch.object(closer.legacy.diagnostics, 'preserve_tmp', return_value={}), \
                    patch.object(closer.legacy, 'remove_owned', return_value={'removed': True}) as remove:
                if via_grade:
                    with patch.object(pilot, 'ROOT', root), patch.object(pilot, 'paths', side_effect=ValueError('source guard failed before collection')):
                        value = pilot.grade(run)
                    self.assertEqual(value['first_error'], {'type': 'ValueError', 'message': 'source guard failed before collection'})
                else:
                    value = closer.close(run, ValueError('source guard failed before collection'))
                if resume_raw is not None:
                    source.write_bytes(resume_raw)
                    value = closer.close(run, RuntimeError('later preservation error'))
                    self.assertEqual(value['first_error']['type'], 'ValueError')
                    self.assertEqual(value['first_error']['message'], 'source guard failed before collection')
                    self.assertEqual(len(list(out.glob('failure-close-observation-v2-*.json'))), 2)
            self.assertEqual(value['actor_terminal_observed'], terminal)
            self.assertEqual((out / 'failure-native-prefix-v2.jsonl').read_bytes(), raw)
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
                self.assertTrue((out / 'failure-close-pending-v2.json').exists())
                self.assertEqual(stop.call_count, 1 if append_at_stop else 0)
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

    def test_wrapped_grade_before_collection_preserves_original_source_error(self):
        first, *_ = fixtures.fixture()
        self.invoke(fixtures.raw(first), True, via_grade=True)

    def test_successful_parent_followup_before_child_start_stays_pending(self):
        first, _, _, parent, _ = fixtures.fixture()
        self.invoke(fixtures.raw(first), False, fixtures.raw(parent))

    def test_unreceipted_parent_followup_stays_pending(self):
        first, _, _, parent, _ = fixtures.fixture()
        self.invoke(fixtures.raw(first), False, fixtures.raw(parent[:2]))

    def test_incoming_before_child_start_stays_pending(self):
        first, _, _, parent, _ = fixtures.fixture()
        self.invoke(fixtures.raw(first + [fixtures.message(15, 'two', 'gAAAAAfollowup')]), False, fixtures.raw(parent))

    def test_out_of_turn_tool_stays_pending(self):
        first, *_ = fixtures.fixture()
        call = fixtures.event(12, 'response_item', {'type': 'custom_tool_call', 'call_id': 'late', 'name': 'exec'})
        self.invoke(fixtures.raw(first + [call]), False)

    def test_unmatched_in_turn_tool_stays_pending(self):
        first, *_ = fixtures.fixture()
        first.insert(4, fixtures.event(6, 'response_item', {'type': 'custom_tool_call', 'call_id': 'open', 'name': 'exec'}))
        self.invoke(fixtures.raw(first), False)

    def test_closed_second_turn_requires_parent_token_and_receipt(self):
        _, _, actor, parent, _ = fixtures.fixture()
        self.invoke(fixtures.raw(actor), True, fixtures.raw(parent))
        parent[1]['payload']['arguments'] = json.dumps({'target': fixtures.BINDING['agent_path'], 'message': 'gAAAAAwrong'})
        self.invoke(fixtures.raw(actor), False, fixtures.raw(parent))

    def test_native_rewrite_does_not_replace_original_error(self):
        first, _, actor, _, _ = fixtures.fixture()
        changed = fixtures.raw(first).replace(b'Retain or invalidate?', b'Changed original')
        self.invoke(fixtures.raw(actor[:len(first)+3]), False, resume_raw=changed)

    def test_pending_resume_keeps_original_error(self):
        first, _, actor, _, _ = fixtures.fixture()
        active = fixtures.raw(actor[:len(first)+3])
        self.invoke(active, False, resume_raw=active)

    def test_append_during_stop_does_not_publish_terminal_or_remove(self):
        first, _, actor, _, _ = fixtures.fixture()
        self.invoke(fixtures.raw(first), False, append_at_stop=fixtures.raw(actor[:len(first)+3]))


if __name__ == '__main__':
    unittest.main()
