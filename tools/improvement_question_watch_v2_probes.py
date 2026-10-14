"""Adaptive observer probes including preserved genuine native format controls.

No actor allocations. These do not prove continuous startup/cleanup observation.
"""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import improvement_question_watch_v2 as watch
import improvement_q01_dialogue_core_v1_probes as fixtures


class Probes(unittest.TestCase):
    def setUp(self):
        self.first, self.seal, self.actor, self.parent, self.record = fixtures.fixture()
        self.binding = fixtures.BINDING

    def authority(self, turns):
        return {**self.binding, 'original_started_at': 0, 'expected_turns': turns,
                'branch': 'no_question' if turns == 1 else 'relevant_question'}

    def test_first_final_awaits_classification_without_second_turn_requirement(self):
        value = watch.observation(fixtures.raw(self.first), self.binding, 0, 20, None)
        self.assertIsNone(value['expected_turns'])
        self.assertTrue(value['awaiting_semantic_review'])
        self.assertFalse(value['task_complete'])

    def test_no_question_single_actual_turn(self):
        value = watch.observation(fixtures.raw(self.first), self.binding, 0, 20, self.authority(1))
        self.assertTrue(value['task_complete'])
        self.assertFalse(value['awaiting_semantic_review'])

    def test_reply_branch_remains_pending_until_second_completion(self):
        value = watch.observation(fixtures.raw(self.first), self.binding, 0, 20, self.authority(2))
        self.assertFalse(value['task_complete'])
        self.assertTrue(value['waiting_for_reply_or_followup'])
        value = watch.observation(fixtures.raw(self.actor), self.binding, 0, 25, self.authority(2))
        self.assertTrue(value['task_complete'])

    def test_no_second_turn_without_branch_authority(self):
        with self.assertRaises(ValueError):
            watch.observation(fixtures.raw(self.actor), self.binding, 0, 25, None)

    def test_no_question_cannot_admit_second_turn(self):
        with self.assertRaises(ValueError):
            watch.observation(fixtures.raw(self.actor), self.binding, 0, 25, self.authority(1))

    def test_authority_identity_clock_and_type_mismatch(self):
        for key, value in (('actor_native_id', 'other'), ('parent_native_id', 'other'),
                           ('agent_path', '/root/other'), ('original_started_at', 1),
                           ('expected_turns', True), ('expected_turns', 3)):
            authority = self.authority(1); authority[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                watch.observation(fixtures.raw(self.first), self.binding, 0, 20, authority)

    def test_partial_append_does_not_invent_completion(self):
        raw = fixtures.raw(self.first) + b'{"unfinished":'
        value = watch.observation(raw, self.binding, 0, 20, None)
        self.assertFalse(value['complete_prefix'])
        self.assertEqual(value['complete_native_sha256'], watch.core.digest(fixtures.raw(self.first)))

    def test_missing_final_or_completion_never_forms_closed_lifecycle(self):
        missing = deepcopy(self.first); del missing[-2]
        with self.assertRaises(ValueError):
            watch.observation(fixtures.raw(missing), self.binding, 0, 20, self.authority(1))
        missing = self.first[:-1]
        self.assertFalse(watch.observation(fixtures.raw(missing), self.binding, 0, 20, self.authority(1))['task_complete'])

    def test_genuine_historical_single_turn_format_control(self):
        folder = watch.ROOT / 'results/control-probe-fresh-J01-solo-v1-J01-C15-1'
        raw = (folder / 'terminal-native.jsonl').read_bytes()
        header = watch.core.parse(raw)[0]['payload']
        binding = {'actor_native_id': header['id'], 'agent_path': header['agent_path'],
                   'parent_native_id': header['parent_thread_id']}
        authority = {**binding, 'original_started_at': 0, 'expected_turns': 1, 'branch': 'no_question'}
        value = watch.observation(raw, binding, 0, 20, authority)
        self.assertTrue(value['task_complete'])
        self.assertEqual(value['completed_turns'], 1)

    def test_genuine_historical_two_turn_format_control(self):
        folder = watch.ROOT / 'results/control-probe-fresh-Q01-dialogue-v1-Q01-C15-1'
        raw = (folder / 'terminal-native.jsonl').read_bytes()
        header = watch.core.parse(raw)[0]['payload']
        binding = {'actor_native_id': header['id'], 'agent_path': header['agent_path'],
                   'parent_native_id': header['parent_thread_id']}
        authority = {**binding, 'original_started_at': 0, 'expected_turns': 2, 'branch': 'relevant_question'}
        value = watch.observation(raw, binding, 0, 20, authority)
        self.assertTrue(value['task_complete'])
        self.assertEqual(value['completed_turns'], 2)


if __name__ == '__main__':
    unittest.main()
