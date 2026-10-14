"""Synthetic counterexamples for J01 adapter changes, never product evidence."""
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import improvement_J01_solo_pilot_v1 as pilot
import improvement_J01_native_watch_v1 as watch
from improvement_q01_dialogue_core_v1_probes import fixture, raw, BINDING


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class Probes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder = self.root / 'runtime/control'
        self.out = self.root / 'results/control'
        self.repo = self.folder / 'repo'
        (self.repo / 'lib').mkdir(parents=True); (self.repo / 'test').mkdir(); self.out.mkdir(parents=True)
        (self.repo / 'lib/implementation.dart').write_text('fixture stub')
        self.case = self.root / 'case'
        (self.case / 'private').mkdir(parents=True)
        (self.case / 'private/acceptance_test.dart').write_text('synthetic oracle')
        write(self.case / 'metadata.json', {'scope': {'allowed_files': ['lib/implementation.dart']},
            'expected_total_test_count': 33, 'expected_private_test_count': 31,
            'private_acceptance': 'private/acceptance_test.dart'})
        self.metadata = {'run_id': 'control', 'container': 'owned', 'container_id': 'owned-id',
            'started_at': time.time(), 'status': 'collected', 'turns': [{}], 'tool_audit': []}
        write(self.folder / 'run.json', self.metadata)
        entities = pilot.protected_tree(self.repo)
        write(self.out / 'artifact-seal.json', {'files': pilot.legacy.digest_tree(self.repo)})
        write(self.out / 'protected-artifact-seal-v1.json', {'entities': entities,
            'native_artifact_seal_sha256': pilot.legacy.sha(self.out / 'artifact-seal.json')})
        write(self.out / 'prepared-base-v1.json', {'entities': entities})
        write(self.out / 'native-usage-v4.json', {'synthetic': True})
        write(self.out / 'product-timing.json', {'synthetic': True})
        self.patches = [patch.object(pilot, 'ROOT', self.root),
            patch.object(pilot, 'adapt', return_value={'case_id': 'J01'}),
            patch.object(pilot, 'case_directory', return_value=self.case),
            patch.object(pilot.legacy, 'bound', return_value=({}, self.metadata)),
            patch.object(pilot.legacy, 'owned_identity', return_value={'State': {'Running': False}})]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def test_plan_rejects_order_model_retry_and_cap_changes(self):
        plan = json.loads((Path(__file__).resolve().parents[1] /
            'results/improvement-v1/fresh-J01-solo-allocation-plan-v1.json').read_bytes())
        pilot.validate_plan(plan)
        for field, bad in [('model', 'wrong'), ('actor_retries', 1), ('participant_cap', 2),
                           ('user_turn_limit', 2), ('expected_full_tests', 2)]:
            other = copy.deepcopy(plan); other[field] = bad
            with self.subTest(field=field), self.assertRaises(AssertionError): pilot.validate_plan(other)
        other = copy.deepcopy(plan); other['sequence'].reverse()
        with self.assertRaises(AssertionError): pilot.validate_plan(other)

    def test_private_route_rejects_traversal_absolute_and_symlink(self):
        meta = {'private_acceptance': 'private/acceptance_test.dart'}
        self.assertEqual(pilot.acceptance_path(self.case, meta).read_text(), 'synthetic oracle')
        external = self.root / 'external.dart'; external.write_text('secret')
        (self.case / 'private/linked.dart').symlink_to(external)
        for name in ('../external.dart', str(external), 'private/linked.dart'):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                pilot.acceptance_path(self.case, {'private_acceptance': name})

    def test_public_cleanup_failure_blocks_private_and_next_allocation(self):
        bad = {'removed': False, 'pass': False}
        with patch.object(pilot, 'verify', return_value=bad) as verify, \
             patch.object(pilot, 'complete_observation', return_value=False), \
             patch.object(pilot.legacy, 'remove_owned', return_value={'removed': True}), \
             patch.object(pilot.legacy, 'ROOT', self.root):
            result = pilot.grade('control')
            self.assertEqual(result['status'], 'evaluation_error')
            self.assertTrue(result['lifecycle_errors']); self.assertEqual(verify.call_count, 1)
            with self.assertRaises(AssertionError):
                pilot.legacy.next_allocation({'sequence': [{'run_id': 'control'}, {'run_id': 'next'}]})

    def test_removed_public_with_cleanup_error_still_blocks_private(self):
        bad = {'removed': True, 'pass': True, 'cleanup_errors': ['inspect receipt error']}
        with patch.object(pilot, 'verify', return_value=bad) as verify, \
             patch.object(pilot, 'complete_observation', return_value=True), \
             patch.object(pilot.legacy, 'remove_owned', return_value={'removed': True}):
            result = pilot.grade('control')
        self.assertEqual(result['status'], 'evaluation_error')
        self.assertFalse(result['comparison_eligible']); self.assertEqual(verify.call_count, 1)

    def test_private_oracle_routed_after_product_cleanup_genuine_failure_retained(self):
        removed = []
        def cleanup(metadata):
            removed.append(True); return {'removed': True}
        def verify(source, output, deadline, expected_tests):
            if expected_tests == 2:
                self.assertFalse(removed)
                self.assertFalse((source / 'test/acceptance_test.dart').exists())
                return {'removed': True, 'pass': True, 'machine': {'pass': True}}
            self.assertEqual(expected_tests, 33); self.assertEqual(removed, [True])
            self.assertEqual((source / 'test/acceptance_test.dart').read_text(), 'synthetic oracle')
            return {'removed': True, 'pass': False, 'machine': {'pass': False}}
        with patch.object(pilot, 'verify', side_effect=verify), \
             patch.object(pilot, 'complete_observation', return_value=True), \
             patch.object(pilot.legacy, 'remove_owned', side_effect=cleanup):
            result = pilot.grade('control')
        self.assertEqual(result['status'], 'review_pending')
        self.assertFalse(result['behavior_pass']); self.assertFalse(result['software_pass'])
        self.assertIsNone(result['overall_pass'])

    def test_terminal_bad_bootstrap_preserves_raw_cost_then_owned_cleanup(self):
        first = fixture()[0]; source = self.root / 'native.jsonl'; source.write_bytes(raw(first))
        (self.out / 'native-usage-v4.json').unlink()
        observed = {'source_sha256': pilot.legacy.sha(source), 'native_completion_observed': True,
            'completions': [{}], 'usage': {'total_tokens': 123}, 'native_session_id': 'child-id'}
        def fail(run, actor):
            self.assertEqual((self.out / 'precollection-terminal-native.jsonl').read_bytes(), raw(first))
            self.assertEqual(json.loads((self.out / 'precollection-native-usage-v4.json').read_bytes())['usage']['total_tokens'], 123)
            raise ValueError('Invalid bootstrap read')
        with patch.object(pilot, 'find_session', return_value=source), \
             patch.object(pilot, 'snapshot', return_value=observed), \
             patch.object(pilot, 'collect_normal', side_effect=fail), \
             patch.object(pilot.dialogue, 'failure_only_binding', return_value={'failure_only': True}), \
             patch.object(pilot.dialogue, 'paths', return_value=(self.folder, self.out, self.metadata)), \
             patch.object(pilot.legacy.diagnostics, 'preserve_tmp'), \
             patch.object(pilot.legacy, 'remove_owned', return_value={'removed': True}):
            result = pilot.collect('control', BINDING['agent_path'])
        self.assertEqual(result['status'], 'evaluation_error'); self.assertFalse(result['comparison_eligible'])
        self.assertTrue(result['product_cleanup']['removed'])
        self.assertEqual((self.out / 'terminal-native.jsonl').read_bytes(), raw(first))

    def test_nonterminal_collect_keeps_same_actor_no_cleanup(self):
        source = self.root / 'native.jsonl'; source.write_bytes(raw(fixture()[0]))
        with patch.object(pilot, 'find_session', return_value=source), \
             patch.object(pilot, 'snapshot', return_value={'native_completion_observed': False}), \
             patch.object(pilot.legacy, 'remove_owned') as cleanup:
            with self.assertRaises(AssertionError): pilot.collect('control', BINDING['agent_path'])
            cleanup.assert_not_called()
        self.assertFalse((self.out / 'precollection-terminal-native.jsonl').exists())

    def test_one_turn_observer_closes_and_rejects_two_turn_or_wrong_model(self):
        first, _, two, _, _ = fixture()
        value = watch.observation(raw(first), BINDING, 100, 110)
        self.assertTrue(value['task_complete']); self.assertFalse(value['waiting_for_reply_or_followup'])
        with self.assertRaises(ValueError): watch.observation(raw(two), BINDING, 100, 110)
        bad = copy.deepcopy(first); bad[2]['payload']['model'] = 'wrong'
        with self.assertRaises(ValueError): watch.observation(raw(bad), BINDING, 100, 110)
        self.assertTrue(watch.observation(raw(first), BINDING, 100, 1300)['deadline_reached'])

    def test_entity_modes_and_unlisted_directory_change_rejected(self):
        original = pilot.protected_tree(self.repo)
        (self.repo / 'lib/implementation.dart').chmod(0o755)
        self.assertFalse(pilot.scope_changes(original, pilot.protected_tree(self.repo), ['lib/implementation.dart'])[1])
        (self.repo / 'unrequested').mkdir()
        self.assertFalse(pilot.scope_changes(original, pilot.protected_tree(self.repo), ['lib/implementation.dart'])[1])


if __name__ == '__main__': unittest.main()
