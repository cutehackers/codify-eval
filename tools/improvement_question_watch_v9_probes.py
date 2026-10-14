"""Deadline closure observer integration. Pure/mocked checks, not native proof."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import improvement_question_watch_v9 as watch
import improvement_q01_dialogue_core_v1_probes as fixtures


class Probes(unittest.TestCase):
    def setup_files(self, root):
        out = root / 'results/control'; out.mkdir(parents=True)
        runtime = root / 'runtime/control'; runtime.mkdir(parents=True)
        raw = fixtures.raw(fixtures.fixture()[0])
        source = root / 'actor.jsonl'; source.write_bytes(raw)
        binding = fixtures.BINDING
        (runtime / 'run.json').write_text(json.dumps({'started_at': 0}))
        (out / 'launch-intent.json').write_text(json.dumps({'started_at': 0}))
        (out / 'actor-binding.json').write_text(json.dumps({
            'native_session_id': binding['actor_native_id'], 'parent_thread_id': binding['parent_native_id'],
            'agent_path': binding['agent_path']}))
        return out, source, raw

    def test_interrupted_usage_closes_only_with_complete_cleanup_contract(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); out, _, raw = self.setup_files(root)
            grade = {'started_at': 0, 'product_cleanup': {'removed': True}}
            usage = {'native_completion_observed': False, 'source_sha256': watch.core.digest(raw)}
            with patch.object(watch, 'ROOT', root), patch.object(watch.deadline_close, 'verify_closed', return_value={}) as verify:
                self.assertTrue(watch.deadline_closed(out, 'control', fixtures.BINDING, raw, grade, usage))
                verify.assert_called_once()
            with patch.object(watch, 'ROOT', root), patch.object(watch.deadline_close, 'verify_closed', side_effect=AssertionError('missing seal')):
                with self.assertRaisesRegex(AssertionError, 'missing seal'):
                    watch.deadline_closed(out, 'control', fixtures.BINDING, raw, grade, usage)

    def test_missing_cleanup_or_usage_cannot_close(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            self.assertFalse(watch.deadline_closed(out, 'control', {}, b'', {'product_cleanup': {'removed': False}}, {}))
            self.assertFalse(watch.deadline_closed(out, 'control', {}, b'', {'product_cleanup': {'removed': True}}, None))

    def test_changed_clock_identity_and_raw_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); out, _, raw = self.setup_files(root)
            grade = {'started_at': 0, 'product_cleanup': {'removed': True}}
            usage = {'source_sha256': watch.core.digest(raw)}
            with patch.object(watch, 'ROOT', root):
                for binding, changed_grade, changed_usage in [
                    (fixtures.BINDING, dict(grade, started_at=1), usage),
                    (dict(fixtures.BINDING, actor_native_id='other'), grade, usage),
                    (fixtures.BINDING, grade, {'source_sha256': 'other'})]:
                    with self.subTest(binding=binding), self.assertRaises(ValueError):
                        watch.deadline_closed(out, 'control', binding, raw, changed_grade, changed_usage)

    def test_supervisor_keeps_original_clock_after_deadline_until_cleanup(self):
        self.invoke_completion(1210, 0)

    def test_verification_completed_after_cleanup_observation_limit_expires(self):
        self.invoke_completion(1370, 15)

    def invoke_completion(self, close_at, verification_seconds):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); out, source, raw = self.setup_files(root)
            grade = {'started_at': 0, 'status': 'fail', 'deadline_aborted': True,
                     'product_cleanup': {'removed': True, 'finished_at': 1201}}
            (out / 'grade.json').write_text(json.dumps(grade))
            (out / 'native-usage-v4.json').write_text(json.dumps({'source_sha256': watch.core.digest(raw), 'native_completion_observed': False}))
            # Actual producer loop is sampled every10s. Controller closes on the
            # first post-deadline sample, never extending the product deadline.
            now = {'value': 20}
            def tick(): return now['value']
            def sleep(seconds): now['value'] += seconds
            checks = []
            def deadline(out, run, binding, raw, grade, usage):
                checks.append(now['value'])
                ready = now['value'] >= close_at
                if ready: now['value'] += verification_seconds
                return ready
            def observe(raw, binding, started, current, authority):
                return {'task_complete': False, 'deadline_reached': current >= 1200}
            with patch.object(watch, 'ROOT', root), patch.object(watch, 'find_session', return_value=source), \
                 patch.object(watch.time, 'time', side_effect=tick), patch.object(watch.time, 'sleep', side_effect=sleep), \
                 patch.object(watch, 'deadline_closed', side_effect=deadline), patch.object(watch, 'observation', side_effect=observe):
                value = watch.supervise('control', fixtures.BINDING['agent_path'])
            if close_at + verification_seconds > 1380:
                self.assertFalse(value['controller_closed'])
                self.assertTrue(value['cleanup_observation_expired'])
            else:
                self.assertTrue(value['controller_closed'])
            self.assertEqual(value['observation_completed_at'], close_at + verification_seconds)
            self.assertEqual(value['product_cleanup_finished_at'], 1201)
            self.assertIn(1200, checks)
            supervisor = json.loads((out / 'observer-supervisor-v9.json').read_bytes())
            self.assertEqual(supervisor['product_deadline'], 1200)
            self.assertFalse(supervisor['product_clock_extended'])

    def test_cleanup_observation_timeout_does_not_claim_actor_terminal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); out, source, raw = self.setup_files(root)
            now = {'value': 20}
            def tick(): return now['value']
            def sleep(seconds): now['value'] += seconds
            with patch.object(watch, 'ROOT', root), patch.object(watch, 'find_session', return_value=source), \
                 patch.object(watch.time, 'time', side_effect=tick), patch.object(watch.time, 'sleep', side_effect=sleep), \
                 patch.object(watch, 'observation', side_effect=lambda *a: {'task_complete': False, 'deadline_reached': now['value'] >= 1200}):
                value = watch.supervise('control', fixtures.BINDING['agent_path'])
            self.assertTrue(value['cleanup_observation_expired'])
            self.assertFalse(value.get('controller_closed', False))
            self.assertFalse(value['task_complete'])
            self.assertEqual(value['observation_completed_at'], 1380)


if __name__ == '__main__': unittest.main()
