"""Actor-free native delivery boundary probes; original evidence is unchanged."""
import json
import unittest
from datetime import timedelta
from collect import find_session
import improvement_optional_lifecycle_v5 as v

PATH = '/root/optional_development_v2_o02_c0_1'

class DeliveryTiming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = find_session(PATH).read_bytes()
        cls.child = find_session(PATH + '/worker1').read_bytes()
        cls.events = [json.loads(line) for line in cls.raw.splitlines()]
        header = cls.events[0]['payload']
        cls.binding = {'agent_path': PATH, 'actor_native_id': header['id'],
                       'parent_native_id': header['parent_thread_id']}
        cls.index = next(i for i, e in enumerate(cls.events)
                         if e['payload'].get('type') == 'agent_message'
                         and e['payload'].get('author') == PATH + '/worker1')

    def check(self, events):
        raw = b''.join(json.dumps(e).encode() + b'\n' for e in events)
        return v.lifecycle(raw, self.binding, 1, {PATH + '/worker1': self.child})

    def test_actual_adjacent_one_millisecond(self):
        _, turns = v.lifecycle(self.raw, self.binding, 1, {PATH + '/worker1': self.child})
        self.assertEqual(len(turns), 1)

    def test_zero_tick(self):
        events = json.loads(json.dumps(self.events))
        events[self.index - 1]['timestamp'] = events[self.index]['timestamp']
        self.check(events)

    def test_beyond_tick_and_reverse_denied(self):
        for milliseconds in (2, -1, 1000):
            events = json.loads(json.dumps(self.events))
            instant = v.instant(events[self.index]['timestamp']) - timedelta(milliseconds=milliseconds)
            events[self.index - 1]['timestamp'] = instant.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
            with self.assertRaises(ValueError): self.check(events)

    def test_trigger_and_metadata_denied(self):
        for payload in ({'trigger_turn': True}, {'trigger_turn': False, 'extra': 1}):
            events = json.loads(json.dumps(self.events))
            events[self.index - 1]['payload'] = payload
            with self.assertRaises(ValueError): self.check(events)

    def test_payload_and_recipient_denied(self):
        for key, value in [('recipient', '/root/other'), ('content', [{'type': 'input_text', 'text': 'forged'}])]:
            events = json.loads(json.dumps(self.events))
            events[self.index]['payload'][key] = value
            with self.assertRaises(ValueError): self.check(events)

    def test_creation_clock_denied(self):
        events = json.loads(json.dumps(self.events))
        events[self.index]['payload']['internal_chat_message_metadata_passthrough']['create_time'] += 1
        with self.assertRaises(ValueError): self.check(events)

if __name__ == '__main__': unittest.main()
