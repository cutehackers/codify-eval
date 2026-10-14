"""Effect-order stubs plus actual-gate retained-source append replay probes."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import improvement_optional_completed_failure_close_v2 as subject


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
                events = subject.gate.original.inventory.core.parse(args[4])
                if len([e for e in events if e['type'] == 'session_meta']) != 1:
                    raise ValueError('Ambiguous coordinator header')
                if mutation == 'unknown': raise ValueError('member live or unknown')
                if mutation == 'append_before' or (mutation == 'append_during_reverify' and order.count('authority') == 2):
                    actor.write_text(actor.read_text() + 'late\n')
                return {'usage': {'preserved_tokens': 7}, 'normal_terminal_failure_gate_pass': True}
            def failure(*args): order.append('preserve')
            def cleanup(*args):
                order.append('cleanup')
                if mutation == 'cleanup': raise ValueError('archive failed')
                if mutation == 'append_after': actor.write_text(actor.read_text() + 'late\n')
                if mutation in ('tool_return', 'delivery', 'parent_replace', 'truncated', 'metadata'):
                    event = {'type': 'response_item', 'timestamp': '2026-10-13T00:00:01Z',
                             'payload': {'type': 'custom_tool_call_output', 'call_id': 'async', 'output': 'done'}}
                    if mutation == 'delivery':
                        event['payload'] = {'type': 'function_call', 'namespace': 'collaboration',
                                            'name': 'send_message', 'call_id': 'late',
                                            'arguments': json.dumps({'target': row['actor_path'], 'message': 'again'})}
                    if mutation == 'metadata': event = {'type': 'session_meta', 'timestamp': event['timestamp'], 'payload': {'id': 'other'}}
                    if mutation == 'parent_replace': parent.write_text('replacement\n')
                    elif mutation == 'truncated': parent.write_text(parent.read_text() + '{')
                    else: parent.write_text(parent.read_text() + json.dumps(event) + '\n')
                if mutation == 'dispatch_config':
                    (folder / 'native-dispatch/configuration.json').write_text('{}')
                if mutation == 'dispatch_intent':
                    (folder / 'native-dispatch/intents/root.json').write_text('{}')
                if mutation == 'dispatch_new':
                    (folder / 'native-dispatch/intents/unknown.json').write_text('{}')
                return {'jobs': {'root': {'status': 'retained' if mutation == 'cleanup_pending' else 'removed'}}}
            with patch.object(subject.inputs, 'ROOT', root), \
                    patch.object(subject.original.runtime, 'load', return_value=state), \
                    patch.object(subject.gate.original.membership, 'reservation_prefix', side_effect=lambda *a:
                        {'changed': True} if mutation == 'registry' and 'cleanup' in order else snapshot), \
                    patch.object(subject.original.broker, 'original', side_effect=lambda p: Path(p).read_bytes()), \
                    patch.object(subject.native_dispatch, 'runtime_identity', return_value='runtime_hash'), \
                    patch.object(subject, 'find_session', return_value=actor), \
                    patch.object(subject.gate, 'verify', side_effect=verify), \
                    patch.object(subject.original.runtime, 'failure', side_effect=failure), \
                    patch.object(subject.original.runtime, 'cleanup', side_effect=cleanup):
                result = subject.close(row, parent, 'inventory', {'type': 'OriginalFailure', 'message': 'original'})
            preserved = json.loads((folder / 'completed-failure-close-v2/intent.json').read_bytes())
            self.assertEqual(preserved['first_error'], result['first_error'])
            self.assertIsNone(result['software_pass'])
            self.assertFalse(result['comparison_admitted'])
            if 'authority' in order and mutation != 'unknown':
                self.assertEqual(result['usage'], {'preserved_tokens': 7})
            return result, order

    def test_completed_authority_precedes_owned_preservation_cleanup(self):
        result, order = self.invoke()
        self.assertEqual(order, ['authority', 'authority', 'preserve', 'cleanup', 'authority'])
        self.assertEqual(result['status'], 'preserved_completed_failure')

    def test_unknown_or_append_before_authority_denies_effects(self):
        for mutation in ('unknown', 'append_before'):
            result, order = self.invoke(mutation)
            self.assertEqual(order, ['authority'])
            self.assertFalse(result['owned_cleanup_verified'])
            self.assertNotEqual(result['status'], 'preserved_completed_failure')

    def test_member_mutation_during_full_gate_denies_cleanup(self):
        result, order = self.invoke('append_during_reverify')
        self.assertEqual(order, ['authority', 'authority'])
        self.assertEqual(result['status'], 'closure_incomplete')
        self.assertFalse(result['owned_cleanup_verified'])

    def test_wrong_actor_and_controller_deny_effects(self):
        for mutation in ('wrong_actor', 'wrong_controller'):
            result, order = self.invoke(mutation)
            self.assertEqual(order, [])
            self.assertFalse(result['owned_cleanup_verified'])

    def test_cleanup_error_or_late_append_never_closes(self):
        for mutation in ('cleanup', 'append_after'):
            result, order = self.invoke(mutation)
            self.assertEqual(order, ['authority', 'authority', 'preserve', 'cleanup'])
            self.assertEqual(result['status'], 'closure_incomplete')
            self.assertIn('closure_error', result)

    def test_legitimate_async_tool_return_append_closes(self):
        result, order = self.invoke('tool_return')
        self.assertEqual(result['status'], 'preserved_completed_failure')
        self.assertEqual(order, ['authority', 'authority', 'preserve', 'cleanup', 'authority'])

    def test_parent_and_dispatch_mutations_deny_completion(self):
        for mutation in ('delivery', 'parent_replace', 'truncated', 'metadata',
                         'dispatch_config', 'dispatch_intent', 'dispatch_new', 'registry', 'cleanup_pending'):
            with self.subTest(mutation=mutation):
                result, order = self.invoke(mutation)
                self.assertEqual(result['status'], 'closure_incomplete')
                self.assertFalse(result['owned_cleanup_verified'])
                self.assertIn('closure_error', result)


class ActualGateAppend(unittest.TestCase):
    """Replay genuine retained sources with the actual gate; no cleanup effects."""
    def invoke(self, mutation=None):
        from improvement_optional_completed_failure_gate_v1_probes import arguments
        args = arguments('one_worker')
        parent = args['coordinator_raw']
        stamp = subject.gate.original.inventory.core.parse(parent)[-1]['timestamp']
        pending = {'type': 'response_item', 'timestamp': stamp, 'payload': {
            'type': 'custom_tool_call', 'name': 'exec', 'call_id': 'async_close_v2',
            'input': 'text("closure observation")'}}
        parent += json.dumps(pending).encode() + b'\n'
        args['commitment'].update(parent_sha256=subject.hashlib.sha256(parent).hexdigest(), parent_bytes=len(parent))
        payload = {'type': 'custom_tool_call_output', 'call_id': 'async_close_v2', 'output': 'done'}
        event = {'type': 'response_item', 'timestamp': stamp, 'payload': payload}
        if mutation in ('delivery', 'spawn'):
            payload.update(type='function_call', namespace='collaboration',
                           name='spawn_agent' if mutation == 'spawn' else 'send_message',
                           arguments=json.dumps({'target': args['root_intent']['agent_path'],
                                                 'message': 'again', 'task_name': 'late'}))
        if mutation == 'metadata': event = {'type': 'session_meta', 'timestamp': stamp, 'payload': {'id': 'other'}}
        if mutation == 'model_context': event = {'type': 'turn_context', 'timestamp': stamp,
                                                'payload': {'model': 'other', 'effort': 'medium'}}
        if mutation == 'commitment': args['commitment']['no_more_delivery'] = False
        if mutation == 'orphan': payload['call_id'] = 'missing_call'
        current = parent + json.dumps(event).encode() + b'\n'
        if mutation == 'replace': current = b'{}\n'
        if mutation == 'truncate': current = parent + b'{'
        if mutation == 'live_inventory':
            events = subject.gate.original.inventory.core.parse(parent)
            for e in events:
                p = e['payload']
                if p.get('call_id') == args['inventory_call_id'] and p.get('type') == 'function_call_output':
                    result = json.loads(p['output'])
                    for member in result['agents']:
                        if member['agent_name'] == args['root_intent']['agent_path']:
                            member['agent_status'] = {'running': None}
                    p['output'] = json.dumps(result)
            parent = b''.join(json.dumps(e).encode() + b'\n' for e in events)
            current = parent
            args['commitment'].update(parent_sha256=subject.hashlib.sha256(parent).hexdigest(), parent_bytes=len(parent))
        rows = {'root': {'intent': args['root_intent']},
                **{job: {'intent': intent} for job, intent in args['worker_intents'].items()}}
        sources = {args['root_intent']['agent_path']: args['root_raw'], **args['worker_raw_by_path']}
        proof = subject.coordinator_fence(args['config'], {'state': args['state']}, rows,
            args['provision'], args['registry_folder'], args['locators'], args['inventory_call_id'],
            args['commitment'], parent, current, sources)
        self.assertEqual(proof['original_no_more_delivery_commitment']['parent_bytes'], len(current))
        self.assertEqual(proof['original_no_more_delivery_commitment']['member_paths'], args['commitment']['member_paths'])
        self.assertIsNone(proof['software_pass'])
        return proof

    def test_actual_gate_accepts_tool_return_append(self):
        self.assertTrue(self.invoke()['normal_terminal_failure_gate_pass'])

    def test_actual_gate_denies_mutations(self):
        for mutation in ('delivery', 'spawn', 'metadata', 'replace', 'truncate', 'live_inventory',
                         'model_context', 'commitment', 'orphan'):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.invoke(mutation)


if __name__ == '__main__':
    unittest.main()
