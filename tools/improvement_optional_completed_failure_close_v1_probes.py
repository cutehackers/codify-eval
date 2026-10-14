"""Effect-order probes only. Native authority is mocked, never claimed genuine."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import improvement_optional_completed_failure_close_v1 as subject


class FailureCloseOrder(unittest.TestCase):
    def invoke(self, mutation=None):
        row = subject.inputs.sequence()[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); folder = root / 'runtime' / row['run_id']
            (folder / 'native-dispatch/intents').mkdir(parents=True)
            (folder / 'native-observer').mkdir()
            state = {'run_id': '0123456789abcdef0123456789abcdef', 'started_at': 1000, 'deadline': 2200}
            configuration = {**state, 'case_id': row['case_id'], 'condition': row['condition']}
            snapshot = {'state': {'configuration': configuration, 'workers': {}}}
            dispatch_configuration = {'root_path': row['actor_path'], 'coordinator_id': 'coordinator',
                                      'run_id': state['run_id'], 'configuration_sha256': subject.original.runtime.registry.sha(configuration),
                                      'runtime_configuration_sha256': 'runtime_hash'}
            if mutation == 'wrong_actor': dispatch_configuration['root_path'] = '/root/other'
            if mutation == 'wrong_controller': dispatch_configuration['coordinator_id'] = 'other'
            (folder / 'native-dispatch/configuration.json').write_text(json.dumps(dispatch_configuration))
            dispatch = {'intent': {'agent_path': row['actor_path']}, 'provision': {'mock': True}}
            (folder / 'native-dispatch/intents/root.json').write_text(json.dumps(dispatch))
            actor = root / 'actor.jsonl'; actor.write_text('original member\n')
            parent = root / 'parent.jsonl'
            parent.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': 'coordinator'},
                                          'timestamp': '2026-10-13T00:00:00Z'}) + '\n')
            order = []
            def verify(*args):
                order.append('authority')
                if mutation == 'unknown': raise ValueError('member live or unknown')
                if mutation == 'append_before': actor.write_text(actor.read_text() + 'late\n')
                return {'usage': None, 'normal_terminal_failure_gate_pass': True}
            def failure(*args): order.append('preserve')
            def cleanup(*args):
                order.append('cleanup')
                if mutation == 'cleanup': raise ValueError('archive failed')
                if mutation == 'append_after': actor.write_text(actor.read_text() + 'late\n')
                return {'jobs': {'root': {'status': 'removed'}}}
            with patch.object(subject.inputs, 'ROOT', root), \
                    patch.object(subject.original.runtime, 'load', return_value=state), \
                    patch.object(subject.gate.original.membership, 'reservation_prefix', return_value=snapshot), \
                    patch.object(subject.original.broker, 'original', side_effect=lambda p: Path(p).read_bytes()), \
                    patch.object(subject.native_dispatch, 'runtime_identity', return_value='runtime_hash'), \
                    patch.object(subject, 'find_session', return_value=actor), \
                    patch.object(subject.gate, 'verify', side_effect=verify), \
                    patch.object(subject.original.runtime, 'failure', side_effect=failure), \
                    patch.object(subject.original.runtime, 'cleanup', side_effect=cleanup):
                result = subject.close(row, parent, 'inventory', {'type': 'OriginalFailure', 'message': 'original'})
            preserved = json.loads((folder / 'completed-failure-close-v1/intent.json').read_bytes())
            self.assertEqual(preserved['first_error'], result['first_error'])
            self.assertIsNone(result['software_pass'])
            self.assertFalse(result['comparison_admitted'])
            return result, order

    def test_completed_authority_precedes_owned_preservation_cleanup(self):
        result, order = self.invoke()
        self.assertEqual(order, ['authority', 'preserve', 'cleanup'])
        self.assertEqual(result['status'], 'preserved_completed_failure')

    def test_unknown_or_append_before_authority_denies_effects(self):
        for mutation in ('unknown', 'append_before'):
            result, order = self.invoke(mutation)
            self.assertEqual(order, ['authority'])
            self.assertFalse(result['owned_cleanup_verified'])
            self.assertNotEqual(result['status'], 'preserved_completed_failure')

    def test_wrong_actor_and_controller_deny_effects(self):
        for mutation in ('wrong_actor', 'wrong_controller'):
            result, order = self.invoke(mutation)
            self.assertEqual(order, [])
            self.assertFalse(result['owned_cleanup_verified'])

    def test_cleanup_error_or_late_append_never_closes(self):
        for mutation in ('cleanup', 'append_after'):
            result, order = self.invoke(mutation)
            self.assertEqual(order, ['authority', 'preserve', 'cleanup'])
            self.assertEqual(result['status'], 'closure_incomplete')
            self.assertIn('closure_error', result)


if __name__ == '__main__':
    unittest.main()
