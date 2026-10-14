"""Mocked authority / real file-fence ordering, not native qualification."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import improvement_optional_deadline_close_v2 as subject


class DeadlineCloseOrder(unittest.TestCase):
    def invoke(self, mutation=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); folder = root / 'runtime' / subject.CONTROL
            (folder / 'native-dispatch').mkdir(parents=True)
            output = folder / 'deadline-close-v1'; output.mkdir()
            actor_path = subject.CONTROL_ACTOR
            parent = root / 'parent.jsonl'; parent.write_text('original parent\n')
            actor = root / 'actor.jsonl'; actor.write_text('original member\n')
            (folder / 'native-dispatch/configuration.json').write_text('original dispatch\n')
            (output / 'coordinator.jsonl').write_bytes(parent.read_bytes())
            (output / 'root.jsonl').write_bytes(actor.read_bytes())
            commitment = {'member_prefixes': {actor_path: {}}, 'no_more_delivery': True}
            (output / 'commitment.json').write_text(json.dumps(commitment))
            config = {'started_at': 1000, 'deadline': 2200}
            snapshot = {'original_registry': True}
            order = []
            def capture(folder_arg, coordinator_arg, destination):
                order.append('capture')
                (destination / 'dispatch-configuration.json').write_text('original dispatch\n')
                return config, snapshot, {}, parent.read_bytes(), {actor_path: actor.read_bytes()}, {actor_path: str(actor)}
            def authority(*args):
                order.append('authority')
                if mutation == 'live': raise subject.aggregate.original.ActorNotTerminal('live member')
                if mutation == 'append_before': actor.write_text(actor.read_text() + 'late\n')
                return {'whole_family_interruption_checks_pass': True}
            def cleanup(*args):
                order.append('cleanup')
                if mutation == 'archive': raise ValueError('archive failure')
                if mutation == 'append_after': actor.write_text(actor.read_text() + 'late\n')
                return {'jobs': {'root': {'status': 'removed'}}}
            with patch.object(subject.inputs, 'ROOT', root), \
                    patch.object(subject, 'capture_family', side_effect=capture), \
                    patch.object(subject.aggregate, 'verify', side_effect=authority), \
                    patch.object(subject, 'coordinator_fence'), \
                    patch.object(subject.aggregate.membership, 'reservation_prefix', return_value=snapshot), \
                    patch.object(subject.original.audit.cost, 'usage_members', return_value={'unknown_usage_paths': [actor_path]}), \
                    patch.object(subject.original.runtime, 'failure'), \
                    patch.object(subject.original.runtime, 'cleanup', side_effect=cleanup):
                value = subject.close(folder, parent)
            self.assertEqual(json.loads((output / 'current-v2/outcome.json').read_bytes()), value)
            self.assertIsNone(value['software_pass'])
            self.assertFalse(value['comparison_admitted'])
            return value, order

    def test_all_member_authority_precedes_cleanup(self):
        value, order = self.invoke()
        self.assertEqual(order, ['capture', 'authority', 'cleanup'])
        self.assertEqual(value['status'], 'preserved_interrupted_failure')
        self.assertEqual(value['original_deadline'], 2200)

    def test_live_or_late_append_prevents_cleanup(self):
        for mutation in ('live', 'append_before'):
            value, order = self.invoke(mutation)
            self.assertEqual(order, ['capture', 'authority'])
            self.assertFalse(value['owned_cleanup_verified'])

    def test_failed_archive_or_late_append_never_closes(self):
        for mutation in ('archive', 'append_after'):
            value, order = self.invoke(mutation)
            self.assertEqual(order, ['capture', 'authority', 'cleanup'])
            self.assertEqual(value['status'], 'closure_incomplete')
            self.assertIn('closure_error', value)

    def test_unknown_namespace_denied_before_effects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with patch.object(subject.inputs, 'ROOT', root):
                with self.assertRaises(ValueError): subject.identity(root / 'runtime/unknown')
                with self.assertRaises(ValueError): subject.identity(root / subject.CONTROL)


if __name__ == '__main__':
    unittest.main()
