"""Adversarial closure probes. Mocked product operations, no native qualification."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import improvement_deadline_authority_v3_probes as parent_probe
import improvement_question_deadline_close_v1 as close


def raw(events):
    return b''.join(json.dumps(e).encode() + b'\n' for e in events)


class Probes(unittest.TestCase):
    def setUp(self):
        self.builder = parent_probe.Probes()
        self.started = close.core.instant('2026-10-11T23:40:29Z').timestamp()
        self.metadata = {'run_id': 'synthetic', 'started_at': self.started, 'container': 'owned'}
        self.binding = {'run_id': 'synthetic', 'parent_thread_id': 'root-native',
                        'agent_path': '/root/control', 'native_session_id': 'child-native',
                        'native_source': '/synthetic/child', 'parent_source': '/synthetic/parent'}
        self.prefix = raw(self.builder.base()[:1])
        self.parent = raw(self.builder.base() + self.builder.inventory('interrupted'))
        self.child = raw([
            {'type': 'session_meta', 'timestamp': '2026-10-12T00:00:29Z', 'payload': {
                'id': 'child-native', 'agent_path': '/root/control', 'parent_thread_id': 'root-native'}},
            {'type': 'response_item', 'timestamp': '2026-10-12T00:00:29Z',
             'payload': {'type': 'agent_message'}},
        ])
        self.value = close.commitment(self.metadata, self.binding, self.prefix, self.child, self.started + 1200)

    def gate(self, **updates):
        args = dict(metadata=self.metadata, binding=self.binding, child_raw=self.child,
                    parent_raw=self.parent, value=self.value, committed_parent=self.prefix, committed_child=self.child)
        args.update(updates)
        return close.evidence_gate(**args)

    def test_valid_base_uses_original_deadline_and_separate_cleanup_authority(self):
        result = self.gate()
        self.assertIs(result['cleanup_authorized'], True)
        self.assertIs(result['terminal_inventory']['cleanup_authorized'], False)
        self.assertEqual(result['started_at'], self.started)

    def test_early_commit_rejected(self):
        with self.assertRaises(AssertionError):
            close.commitment(self.metadata, self.binding, self.prefix, self.child, self.started + 1199)

    def test_binding_or_clock_replacement_rejected(self):
        self.gate()
        for field, value in [('run_id', 'other'), ('original_deadline', self.started + 1201), ('no_more_delivery', False)]:
            with self.subTest(field=field), self.assertRaises(AssertionError):
                self.gate(value=dict(self.value, **{field: value}))

    def test_commit_cannot_reuse_prior_interrupt(self):
        self.gate()
        value = close.commitment(self.metadata, self.binding, self.parent, self.child, self.started + 1203)
        with self.assertRaises(AssertionError):
            self.gate(value=value, committed_parent=self.parent)

    def test_delivery_between_commit_and_interrupt_rejected(self):
        self.gate()
        events = self.builder.base()
        events[1:1] = self.builder.pair('followup_task', {'target': '/root/control', 'message': 'synthetic'}, '', 'delivery', 29)
        with self.assertRaisesRegex(AssertionError, 'Delivery after commitment'):
            self.gate(parent_raw=raw(events + self.builder.inventory('interrupted')))

    def test_child_uuid_replacement_rejected(self):
        self.gate()
        events = close.core.parse(self.child)
        events[0]['payload']['id'] = 'other'
        with self.assertRaises(AssertionError): self.gate(child_raw=raw(events))

    def test_parent_prefix_mutation_rejected(self):
        self.gate()
        with self.assertRaisesRegex(AssertionError, 'Parent no longer extends'):
            self.gate(parent_raw=self.parent.replace(b'root-native', b'other-native'))

    def test_same_uuid_child_rewrite_before_authorize_rejected(self):
        self.gate()
        events = close.core.parse(self.child)
        events[1]['payload']['rewritten'] = True
        with self.assertRaisesRegex(AssertionError, 'Child no longer extends'):
            self.gate(child_raw=raw(events))

    def test_latest_running_stale_terminal_and_missing_receipt_rejected(self):
        self.gate()
        events = self.builder.base() + self.builder.inventory('interrupted')
        for later in [self.builder.inventory('running', 'latest', 34), self.builder.inventory('interrupted', 'latest', 34)[:1]]:
            with self.subTest(later=later), self.assertRaises(close.parser.ActorNotTerminal):
                self.gate(parent_raw=raw(events + later))

    def test_fence_rejects_child_append_or_new_authority(self):
        expected = self.gate()
        changed = dict(expected, actor_native_bytes=expected['actor_native_bytes'] + 1)
        with patch.object(close, 'current', return_value=(changed, self.child, self.parent)):
            with self.assertRaisesRegex(AssertionError, 'authority changed'):
                close.fence(Path('/synthetic'), self.metadata, self.binding, expected)

    def run_close(self, failing_fence=None, tamper=None):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            (out / close.AUTHORITY).write_text(json.dumps(self.gate()))
            (out / 'actor-binding.json').write_text(json.dumps(self.binding))
            (out / close.COMMIT).write_text(json.dumps(self.value))
            (out / close.COMMIT_PARENT).write_bytes(self.prefix)
            (out / close.COMMIT_CHILD).write_bytes(self.child)
            calls = []
            def check(*args):
                calls.append('fence')
                if failing_fence == calls.count('fence'):
                    raise AssertionError('synthetic source changed')
                return self.child, self.parent
            def stop(*args): calls.append('stop')
            def preserve(*args): calls.append('preserve')
            def remove(*args):
                calls.append('remove')
                return {'removed': True, 'finished_at': self.started + 1210}
            observed = {'source_sha256': close.core.digest(self.child), 'native_completion_observed': False,
                        'usage': None}
            with patch.object(close, 'paths', return_value=(out, out, self.metadata)), \
                 patch.object(close.time, 'time', return_value=self.started + 1211), \
                 patch.object(close, 'bind', return_value=(out, self.binding)), \
                 patch.object(close, 'fence', side_effect=check), \
                 patch.object(close.normal.old, 'failure_snapshot', return_value=observed), \
                 patch.object(close.normal.old, 'stop_owned', side_effect=stop), \
                 patch.object(close.legacy.diagnostics, 'preserve_tmp', side_effect=preserve), \
                 patch.object(close.legacy, 'remove_owned', side_effect=remove):
                value = close.close('synthetic', '/root/control')
            if failing_fence is None:
                self.assertIs(close.verify_closed(out, self.metadata)['deadline_cleanup_evidence_verified'], True)
                if tamper:
                    if tamper == 'parent':
                        (out / 'deadline-post-removal-parent-v1.jsonl').write_bytes(self.parent + raw(self.builder.inventory('running', 'new', 34)))
                    else:
                        changed = json.loads((out / 'grade.json').read_bytes())
                        changed['lifecycle_errors'] = [{'type': 'synthetic', 'message': 'unresolved'}]
                        (out / 'grade.json').write_text(json.dumps(changed))
                    with self.assertRaises((AssertionError, close.parser.ActorNotTerminal)):
                        close.verify_closed(out, self.metadata)
            return value, calls, (out / 'deadline-closure.json').exists()

    def test_cleanup_has_fences_around_stop_and_remove(self):
        value, calls, receipt = self.run_close()
        self.assertEqual(calls, ['fence', 'fence', 'stop', 'fence', 'preserve', 'fence', 'remove', 'fence'])
        self.assertTrue(receipt)
        self.assertFalse(value['complete_final_cost'])
        self.assertFalse(value['usage']['native_completion_observed'])
        self.assertEqual(value['lifecycle_errors'], [])

    def test_changed_authority_after_stop_prevents_remove(self):
        value, calls, receipt = self.run_close(failing_fence=3)
        self.assertIn('stop', calls)
        self.assertNotIn('remove', calls)
        self.assertFalse(receipt)
        self.assertEqual(len(value['lifecycle_errors']), 1)

    def test_post_removal_fence_failure_is_preserved_not_passed(self):
        value, calls, receipt = self.run_close(failing_fence=5)
        self.assertIn('remove', calls)
        self.assertFalse(receipt)
        self.assertEqual(len(value['lifecycle_errors']), 1)

    def test_next_allocation_rejects_stale_authority_and_lifecycle_errors(self):
        self.run_close(tamper='parent')
        self.run_close(tamper='lifecycle')

    def test_stage_rejected_after_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            out = root / 'results' / 'synthetic'
            out.mkdir(parents=True)
            with patch.object(close, 'ROOT', root):
                close.require_delivery_open('synthetic')
                (out / close.COMMIT_PARENT).write_bytes(self.prefix)
                (out / close.COMMIT_CHILD).write_bytes(self.child)
                with self.assertRaisesRegex(AssertionError, 'no more delivery'):
                    close.require_delivery_open('synthetic')


if __name__ == '__main__':
    unittest.main()
