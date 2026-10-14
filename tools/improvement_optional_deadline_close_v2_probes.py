"""Synthetic append checks. Real interrupted control is separately preserved."""
import copy
import json
import unittest

import improvement_optional_deadline_close_v2 as subject
from improvement_optional_deadline_members_v1_probes import DeadlineMembers, raw


class CoordinatorFence(unittest.TestCase):
    def fixture(self):
        return list(DeadlineMembers().fixture())

    def extended(self, original, name, arguments, output=None):
        events = subject.aggregate.original.core.parse(original)
        event = copy.deepcopy(events[-1])
        event['payload'] = {'type': 'function_call', 'name': name,
                            'arguments': json.dumps(arguments), 'call_id': 'observation_append'}
        events.append(event)
        if output is not None:
            receipt = copy.deepcopy(event)
            receipt['payload'] = {'type': 'function_call_output', 'call_id': 'observation_append',
                                  'output': json.dumps(output)}
            events.append(receipt)
        return raw(events)

    def fence(self, args, current):
        config, proof, committed, parent, prefixes, captured, sources = args
        return subject.coordinator_fence(config, proof, committed, parent, prefixes, captured, current, sources)

    def test_normal_observation_and_receipt_append_allowed(self):
        args = self.fixture()
        current = self.extended(args[5], 'functions.exec', {'input': 'observation'}, {'session_id': 123})
        self.assertTrue(self.fence(args, current)['whole_family_interruption_checks_pass'])

    def test_new_member_delivery_or_allocation_denied(self):
        for name, arguments in [('collaboration.followup_task', {'target': '/root/product', 'message': 'unsafe'}),
                                ('collaboration.send_message', {'target': '/root/product/worker1', 'message': 'unsafe'}),
                                ('collaboration.spawn_agent', {'task_name': 'unexpected'})]:
            args = self.fixture(); current = self.extended(args[5], name, arguments, {})
            with self.subTest(name=name), self.assertRaises(ValueError): self.fence(args, current)

    def test_current_inventory_can_change_only_to_terminal_family(self):
        for status in ('running', 'interrupted'):
            args = self.fixture()
            current = self.extended(args[5], 'collaboration.list_agents', {}, {'agents': [
                {'agent_name': '/root/product', 'agent_status': status},
                {'agent_name': '/root/product/worker1', 'agent_status': 'interrupted'},
                {'agent_name': '/root/product/worker2', 'agent_status': 'interrupted'}]})
            if status == 'running':
                with self.assertRaises(subject.aggregate.original.ActorNotTerminal): self.fence(args, current)
            else:
                self.assertTrue(self.fence(args, current)['whole_family_interruption_checks_pass'])

    def test_replaced_original_coordinator_denied(self):
        args = self.fixture()
        with self.assertRaises(ValueError): self.fence(args, args[5][1:])


if __name__ == '__main__':
    unittest.main()
