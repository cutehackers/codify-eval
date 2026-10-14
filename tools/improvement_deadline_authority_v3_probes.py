"""Adversarial parent-ledger checks only, never native qualification."""
import json
import unittest
from copy import deepcopy

import improvement_deadline_authority_v3 as helper


class Probes(unittest.TestCase):
    binding = {'parent_thread_id': 'root-native', 'agent_path': '/root/control'}

    def event(self, payload, second):
        return {'type': 'response_item', 'timestamp': f'2026-10-12T00:00:{second:02d}Z', 'payload': payload}

    def pair(self, name, arguments, output, identity, second):
        return [self.event({'type': 'function_call', 'name': 'collaboration.' + name,
                            'arguments': json.dumps(arguments), 'call_id': identity}, second),
                self.event({'type': 'function_call_output', 'output': json.dumps(output), 'call_id': identity}, second + 1)]

    def base(self):
        return [{'type': 'session_meta', 'timestamp': '2026-10-12T00:00:29Z', 'payload': {'id': 'root-native'}}] + self.pair(
            'interrupt_agent', {'target': '/root/control'}, {'previous_status': 'running'}, 'interrupt', 30)

    def inventory(self, status, identity='inventory', second=32, arguments=None):
        return self.pair('list_agents', {} if arguments is None else arguments,
                         {'agents': [{'agent_name': '/root/control', 'agent_status': status}]}, identity, second)

    def run_authority(self, events):
        raw = b''.join(json.dumps(e).encode() + b'\n' for e in events)
        return helper.authority(raw, self.binding, helper.core.instant('2026-10-12T00:00:30Z').timestamp())

    def test_interrupt_receipt_kind_must_match_function_call(self):
        events = self.base() + self.inventory({'completed': 'synthetic'})
        self.assertIs(self.run_authority(events)['cleanup_authorized'], False)
        events[2]['payload']['type'] = 'custom_tool_call_output'
        with self.assertRaisesRegex(ValueError, 'Interrupt receipt type mismatch'):
            self.run_authority(events)

    def test_inventory_receipt_kind_must_match_function_call(self):
        events = self.base() + self.inventory({'completed': 'synthetic'})
        self.assertIs(self.run_authority(events)['cleanup_authorized'], False)
        events[-1]['payload']['type'] = 'custom_tool_call_output'
        with self.assertRaisesRegex(ValueError, 'Inventory receipt type mismatch'):
            self.run_authority(events)

    def test_latest_terminal_does_not_authorize_cleanup(self):
        result = self.run_authority(self.base() + self.inventory({'completed': 'synthetic'}))
        self.assertEqual(result['terminal_poll_call_id'], 'inventory')
        self.assertIs(result['cleanup_authorized'], False)

    def test_stale_terminal_then_running_is_pending(self):
        events = self.base() + self.inventory({'completed': 'synthetic'}) + self.inventory('running', 'latest', 34)
        with self.assertRaises(helper.ActorNotTerminal): self.run_authority(events)

    def test_later_terminal_replaces_prior_running(self):
        events = self.base() + self.inventory('running') + self.inventory({'completed': 'synthetic'}, 'latest', 34)
        self.assertEqual(self.run_authority(events)['terminal_poll_call_id'], 'latest')

    def test_resume_and_message_after_interrupt_rejected(self):
        for name in ('followup_task', 'send_message'):
            events = self.base() + self.inventory({'completed': 'synthetic'}) + self.pair(name, {'target': '/root/control', 'message': 'synthetic'}, {}, 'resume', 34)
            with self.subTest(name=name), self.assertRaises(ValueError): self.run_authority(events)

    def test_delivery_while_interrupt_receipt_pending_rejected(self):
        base = self.base()
        events = base[:2] + self.pair('followup_task', {'target': '/root/control', 'message': 'synthetic'}, {}, 'resume', 30) + base[2:] + self.inventory({'completed': 'synthetic'})
        with self.assertRaises(ValueError): self.run_authority(events)

    def test_latest_unreceipted_or_filtered_inventory_denied(self):
        closed = self.base() + self.inventory({'completed': 'synthetic'})
        with self.assertRaises(helper.ActorNotTerminal): self.run_authority(closed + self.inventory('running', 'latest', 34)[:1])
        with self.assertRaises(ValueError): self.run_authority(closed + self.inventory({'completed': 'synthetic'}, 'latest', 34, {'path_prefix': '/root'}))

    def test_duplicate_receipt_and_actor_inventory_denied(self):
        events = self.base() + self.inventory({'completed': 'synthetic'})
        with self.assertRaises(ValueError): self.run_authority(events + [events[-1]])
        modified = deepcopy(events)
        value = json.loads(modified[-1]['payload']['output']); value['agents'] *= 2
        modified[-1]['payload']['output'] = json.dumps(value)
        with self.assertRaises(ValueError): self.run_authority(modified)

    def test_unknown_status_and_new_interrupt_without_current_inventory_denied(self):
        with self.assertRaises(helper.ActorNotTerminal): self.run_authority(self.base() + self.inventory({'interrupted': True}))
        events = self.base() + self.inventory({'completed': 'synthetic'}) + self.pair('interrupt_agent', {'target': '/root/control'}, {'previous_status': 'running'}, 'new', 34)
        with self.assertRaises(helper.ActorNotTerminal): self.run_authority(events)


if __name__ == '__main__': unittest.main()
