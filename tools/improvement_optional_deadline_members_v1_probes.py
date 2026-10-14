"""Synthetic aggregate checks. Allocation and interruption are not genuine."""
import copy
from datetime import datetime, timezone, timedelta
import json
import unittest

import improvement_optional_deadline_members_v1 as subject


def raw(events):
    return b''.join(json.dumps(event).encode() + b'\n' for event in events)


class DeadlineMembers(unittest.TestCase):
    def fixture(self, workers=2):
        start = datetime(2026, 10, 13, tzinfo=timezone.utc)
        def event(payload, seconds, kind='response_item'):
            return {'type': kind, 'timestamp': (start + timedelta(seconds=seconds)).isoformat(), 'payload': payload}
        paths = ['/root/product'] + ['/root/product/worker' + str(i + 1) for i in range(workers)]
        coordinator = raw([event({'id': 'controller'}, 0, 'session_meta')])
        sources = {}
        for index, path in enumerate(paths):
            parent = 'controller' if index == 0 else 'uuid0'
            header = {'id': 'uuid' + str(index), 'agent_path': path, 'parent_thread_id': parent,
                      'source': {'subagent': {'thread_spawn': {'parent_thread_id': parent, 'agent_path': path}}}}
            sources[path] = raw([event(header, 1, 'session_meta'),
                                 event({'model': 'gpt-6.1-sol', 'effort': 'medium'}, 2, 'turn_context')])
        config = {'run_id': 'runtime_uuid', 'started_at': start.timestamp(),
                  'deadline': start.timestamp() + 1200, 'model': 'gpt-6.1-sol', 'effort': 'medium'}
        proof = {'provided_allocation_joins_complete': True, 'pending_allocation_slots': [],
                 'observed_unbound_sources': [], 'root_path': paths[0], 'coordinator_native_id': 'controller',
                 'configuration_sha256': subject.membership.registry.sha(config),
                 'members': [{'agent_path': path, 'native_session_id': 'uuid' + str(i),
                              'raw_bytes': len(sources[path]), 'raw_sha256': subject.original.core.digest(sources[path])}
                             for i, path in enumerate(paths)]}
        commitment = subject.commit(config, proof, coordinator, sources, config['deadline'])
        suffix = []
        for index, path in enumerate(paths):
            cid = 'interrupt' + str(index)
            suffix.extend([event({'type': 'function_call', 'name': 'collaboration.interrupt_agent',
                                  'call_id': cid, 'arguments': json.dumps({'target': path})}, 1201 + 2 * index),
                           event({'type': 'function_call_output', 'call_id': cid,
                                  'output': json.dumps({'previous_status': 'running'})}, 1202 + 2 * index)])
        suffix.extend([event({'type': 'function_call', 'name': 'collaboration.list_agents',
                              'call_id': 'inventory', 'arguments': '{}'}, 1210),
                       event({'type': 'function_call_output', 'call_id': 'inventory',
                              'output': json.dumps({'agents': [{'agent_name': path, 'agent_status': {'interrupted': 'synthetic'}}
                                                               for path in paths]})}, 1211)])
        return config, proof, commitment, coordinator, sources, coordinator + raw(suffix), sources

    def test_whole_family_not_cleanup_authority(self):
        for count in (0, 1, 2):
            value = subject.verify(*self.fixture(count))
            self.assertTrue(value['whole_family_interruption_checks_pass'])
            self.assertFalse(value['cleanup_authorized'])
            self.assertFalse(value['actual_native_control_qualified'])

    def test_one_live_or_unknown_descendant_denies(self):
        for mutation in ('live', 'extra'):
            args = list(self.fixture()); events = subject.original.core.parse(args[5])
            inventory = json.loads(events[-1]['payload']['output'])
            if mutation == 'live': inventory['agents'][1]['agent_status'] = 'running'
            else: inventory['agents'].append({'agent_name': '/root/product/worker3', 'agent_status': 'running'})
            events[-1]['payload']['output'] = json.dumps(inventory); args[5] = raw(events)
            error = subject.original.ActorNotTerminal if mutation == 'live' else ValueError
            with self.subTest(mutation=mutation), self.assertRaises(error): subject.verify(*args)

    def test_missing_worker_interrupt_denies(self):
        args = list(self.fixture()); events = subject.original.core.parse(args[5])
        args[5] = raw([event for event in events if event['payload'].get('call_id') != 'interrupt1'])
        with self.assertRaises(ValueError): subject.verify(*args)

    def test_no_more_delivery_and_prefix_are_binding(self):
        for mutation in ('commitment', 'prefix', 'family'):
            args = list(self.fixture())
            if mutation == 'commitment': args[2]['no_more_delivery'] = False
            if mutation == 'prefix': args[3] += b'changed\n'
            if mutation == 'family': args[2]['member_prefixes'].pop('/root/product/worker1')
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): subject.verify(*args)

    def test_postcommit_message_and_unknown_allocation_deny(self):
        for name in ('send_message', 'spawn_agent'):
            args = list(self.fixture()); events = subject.original.core.parse(args[5])
            extra = copy.deepcopy(events[-1]); extra['payload'] = {
                'type': 'function_call', 'name': 'collaboration.' + name, 'call_id': 'late',
                'arguments': json.dumps({'target': '/root/product/worker1', 'message': 'late'})}
            args[5] = raw(events + [extra])
            with self.subTest(name=name), self.assertRaises(ValueError): subject.verify(*args)


if __name__ == '__main__':
    unittest.main()
