"""Synthetic failure-path regression controls. No evaluated actors or Docker."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import improvement_q01_dialogue_pilot_v1 as pilot
import improvement_q01_watch_supervisor_v1 as supervisor
from improvement_q01_dialogue_core_v1_probes import fixture, raw, BINDING


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class Probes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.folder, self.out = self.root / 'runtime' / 'control', self.root / 'results' / 'control'
        self.folder.mkdir(parents=True); self.out.mkdir(parents=True)
        self.repo = self.folder / 'repo'; (self.repo / 'lib').mkdir(parents=True)
        (self.repo / 'lib/implementation.dart').write_text('synthetic control')
        self.first, self.seal, self.actor, self.parent, self.record = fixture()
        self.source = self.root / 'actual-control-native.jsonl'; self.source.write_bytes(raw(self.actor))
        self.binding = {'agent_path': BINDING['agent_path'], 'native_session_id': BINDING['actor_native_id'],
                        'parent_thread_id': BINDING['parent_native_id'], 'native_source': str(self.source),
                        'parent_source': str(self.root / 'parent-native.jsonl')}
        write(self.out / 'actor-binding.json', self.binding)
        self.seal['actor_binding_sha256'] = pilot.legacy.sha(self.out / 'actor-binding.json')
        write(self.out / 'first-seal.json', self.seal)
        self.metadata = {'run_id': 'control', 'container': 'owned', 'container_id': 'owned-id',
                         'started_at': time.time(), 'status': 'collected', 'turns': [{}, {}], 'tool_audit': []}
        self.paths = patch.object(pilot, 'paths', return_value=(self.folder, self.out, self.metadata))
        self.paths.start()

    def tearDown(self):
        self.paths.stop(); self.tmp.cleanup()

    def test_turn2_abort_uses_preserved_initial_binding(self):
        def fake_abort(run, actor):
            return pilot.legacy.bind_actor(run, actor)
        with patch.object(pilot, 'find_session', return_value=self.source), \
             patch.object(pilot.legacy, 'bind_actor', side_effect=ValueError('Single-turn binder rejects turn2')), \
             patch.object(pilot.legacy, 'abort_deadline', side_effect=fake_abort):
            self.assertEqual(pilot.abort('control', BINDING['agent_path']), self.binding)

    def test_unsealed_failed_bootstrap_abort_does_not_requalify_read(self):
        (self.out / 'first-seal.json').unlink()
        failed = {**self.binding, 'failure_only': True, 'actual_public_request_read_verified': False}
        def fake_abort(run, actor):
            return pilot.legacy.bind_actor(run, actor)
        with patch.object(pilot, 'failure_only_binding', return_value=failed), \
             patch.object(pilot.legacy, 'bind_actor', side_effect=ValueError('Missing successful bootstrap')), \
             patch.object(pilot.legacy, 'abort_deadline', side_effect=fake_abort):
            value = pilot.abort('control', BINDING['agent_path'])
            self.assertFalse(value['actual_public_request_read_verified'])

    def test_header_only_failure_snapshot_preserves_unknown_usage(self):
        header = raw(self.actor[:1])
        value = pilot.failure_snapshot(header, BINDING['agent_path'], str(self.source))
        self.assertEqual(value['source_sha256'], pilot.core.digest(header))
        self.assertFalse(value['native_completion_observed'])
        self.assertIsNone(value['usage'])
        self.assertIn('token_usage', value['metrics_unavailable'])

    def test_terminal_protocol_failure_preserves_native_then_cleans(self):
        with patch.object(pilot, 'stop_owned', return_value={'finished_at': time.time()}), \
             patch.object(pilot, 'collect_stopped', side_effect=ValueError('Wrong first reply read')), \
             patch.object(pilot.legacy, 'owned_identity', return_value={'State': {'Running': False}}), \
             patch.object(pilot.legacy.diagnostics, 'preserve_tmp') as preserve, \
             patch.object(pilot.legacy, 'remove_owned', return_value={'removed': True, 'container_id': 'owned-id'}):
            result = pilot.collect('control', BINDING['agent_path'])
        self.assertEqual(result['status'], 'evaluation_error')
        self.assertTrue(result['product_cleanup']['removed'])
        self.assertTrue((self.out / 'terminal-native.jsonl').exists())
        usage = json.loads((self.out / 'native-usage-v4.json').read_bytes())
        self.assertEqual(usage['source_sha256'], pilot.legacy.sha(self.out / 'terminal-native.jsonl'))
        self.assertEqual(len(usage['completions']), 2)
        self.assertFalse(result['comparison_eligible'])
        preserve.assert_called_once()

    def test_nonterminal_collect_retains_actor_no_terminal_export(self):
        self.source.write_bytes(raw(self.first))
        with self.assertRaises(pilot.legacy.prior.ActorNotTerminal):
            pilot.collect('control', BINDING['agent_path'])
        self.assertFalse((self.out / 'terminal-native.jsonl').exists())
        self.assertFalse((self.out / 'grade.json').exists())

    def test_public_cleanup_failure_blocks_sequence_advancement(self):
        entities = pilot.solo.protected_tree(self.repo)
        write(self.out / 'protected-artifact-seal-v1.json', {'entities': entities})
        write(self.out / 'artifact-seal.json', {'files': pilot.legacy.digest_tree(self.repo)})
        write(self.out / 'prepared-base-v1.json', {'entities': entities})
        write(self.out / 'native-usage-v4.json', {'synthetic': True})
        write(self.out / 'product-timing.json', {'synthetic': True})
        bad = {'removed': False, 'cleanup_errors': ['Retained stopped verifier'], 'pass': False}
        with patch.object(pilot.legacy, 'owned_identity', return_value={'State': {'Running': False}}), \
             patch.object(pilot, 'ROOT', self.root), \
             patch.object(pilot, 'verify', return_value=bad), \
             patch.object(pilot.solo, 'complete_observation', return_value=False), \
             patch.object(pilot.legacy, 'remove_owned', return_value={'removed': True}), \
             patch.object(pilot.legacy, 'ROOT', self.root):
            result = pilot.grade('control')
            self.assertTrue(result['lifecycle_errors'])
            self.assertEqual(result['status'], 'evaluation_error')
            with self.assertRaises(AssertionError):
                pilot.legacy.next_allocation({'sequence': [{'run_id': 'control'}, {'run_id': 'next'}]})

    def test_supervisor_one_turn_question_failure_requires_native_closure(self):
        self.source.write_bytes(raw(self.first))
        write(self.out / 'launch-intent.json', {'started_at': time.time()})
        write(self.out / 'grade.json', {'status': 'fail', 'product_cleanup': {'removed': True}})
        write(self.out / 'native-usage-v4.json', {'native_completion_observed': True,
                                                'source_sha256': pilot.core.digest(raw(self.first))})
        with patch.object(supervisor.watcher, 'ROOT', self.root), \
             patch.object(supervisor, 'find_session', return_value=self.source):
            result = supervisor.supervise('control', BINDING['agent_path'])
        self.assertTrue(result['controller_closed'])
        self.assertFalse(result['task_complete'])

    def test_supervisor_status_file_without_matching_native_does_not_close(self):
        self.source.write_bytes(raw(self.first))
        write(self.out / 'launch-intent.json', {'started_at': 100})
        write(self.out / 'grade.json', {'status': 'fail', 'product_cleanup': {'removed': True}})
        write(self.out / 'native-usage-v4.json', {'native_completion_observed': True, 'source_sha256': 'wrong'})
        with patch.object(supervisor.watcher, 'ROOT', self.root), \
             patch.object(supervisor, 'find_session', return_value=self.source), \
             patch.object(supervisor.time, 'time', side_effect=[100, 100, 100, 100, 1301]), \
             patch.object(supervisor.time, 'sleep'):
            result = supervisor.supervise('control', BINDING['agent_path'])
        self.assertFalse(result['controller_closed'])
        self.assertTrue(result['deadline_reached'])
        self.assertEqual(len((self.out / 'root-observation-q01-v1.jsonl').read_text().splitlines()), 2)


if __name__ == '__main__':
    unittest.main()
