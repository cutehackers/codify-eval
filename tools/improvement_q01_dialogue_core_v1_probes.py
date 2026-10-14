"""Counterexamples for pure chronology checks. Synthetic controls are not runs."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import improvement_q01_dialogue_core_v1 as core
import improvement_q01_native_watch_v1 as watch

ROOT = str(Path(__file__).resolve().parents[1])
BINDING = {'actor_native_id': 'child-id', 'agent_path': '/root/q01_control', 'parent_native_id': 'parent-id'}


def event(second, kind, payload):
    return {'timestamp': f'2026-10-12T00:00:{second:02d}+00:00', 'type': kind, 'payload': payload}


def raw(events):
    return b''.join(json.dumps(e).encode() + b'\n' for e in events)


def message(second, tid, token):
    return event(second, 'response_item', {'type': 'agent_message', 'author': '/root',
                 'recipient': BINDING['agent_path'], 'content': [{'type': 'input_text', 'text': ''},
                 {'type': 'encrypted_content', 'encrypted_content': token}],
                 'internal_chat_message_metadata_passthrough': {'turn_id': tid}})


def turn(start, tid, token, text):
    return [event(start, 'event_msg', {'type': 'task_started', 'turn_id': tid}),
            event(start + 1, 'turn_context', {'turn_id': tid, 'model': 'gpt-6.1-sol', 'effort': 'medium'}),
            message(start + 2, tid, token),
            event(start + 8, 'response_item', {'type': 'message', 'role': 'assistant', 'phase': 'final_answer',
                  'content': [{'type': 'output_text', 'text': text}],
                  'internal_chat_message_metadata_passthrough': {'turn_id': tid}}),
            event(start + 9, 'event_msg', {'type': 'task_complete', 'turn_id': tid, 'last_agent_message': text})]


def fixture():
    first = [event(0, 'session_meta', {'id': 'child-id', 'agent_path': BINDING['agent_path'],
                                      'parent_thread_id': 'parent-id'})] + turn(1, 'one', 'gAAAAAinitial', 'Retain or invalidate?')
    seal = core.first_seal(raw(first), BINDING, b'entities', b'journal')
    second = turn(15, 'two', 'gAAAAAfollowup', 'Implemented')
    command = f"python3 {ROOT}/tools/agent_io.py --run q01-control --cmd 'cat /eval-input/turn-2.txt'"
    read = event(18, 'response_item', {'type': 'custom_tool_call', 'name': 'functions.exec', 'call_id': 'read',
                                    'input': 'text(await tools.exec_command({"cmd":' + json.dumps(command) + '}));'})
    record = {'command': core.READ, 'container': 'owned', 'time': '2026-10-12T00:00:18.100+00:00',
              'elapsed_seconds': .1, 'exit_code': 0, 'output': 'Fixed reply\n'}
    receipt = event(19, 'response_item', {'type': 'custom_tool_call_output', 'call_id': 'read',
                   'output': [{'type': 'text', 'text': json.dumps({'exit_code': 0, 'output': json.dumps(record)})}]})
    actor = first + second[:3] + [read, receipt] + second[3:]
    parent = [event(0, 'session_meta', {'id': 'parent-id'}),
              event(13, 'response_item', {'type': 'function_call', 'name': 'collaboration.followup_task',
                   'call_id': 'follow', 'arguments': json.dumps({'target': BINDING['agent_path'], 'message': 'gAAAAAfollowup'})}),
              event(14, 'response_item', {'type': 'function_call_output', 'call_id': 'follow', 'output': ''})]
    return first, seal, actor, parent, record


class Probes(unittest.TestCase):
    def setUp(self):
        self.first, self.seal, self.actor, self.parent, self.record = fixture()

    def read(self, actor=None, record=None):
        return core.read_receipt(raw(actor or self.actor), BINDING, b'Fixed reply\n',
                                 [record or self.record], ROOT, 'q01-control', 'owned')

    def follow(self, actor=None, parent=None):
        return core.followup_proof(raw(actor or self.actor), raw(parent or self.parent), BINDING,
                                   self.seal, '2026-10-12T00:00:12+00:00', 'Read staged file')

    def test_closed_two_turn_control(self):
        self.assertEqual(self.read()['receipt_call_id'], 'read')
        self.assertFalse(self.follow()['plaintext_followup_verified'])

    def test_semantic_review_requires_all_bound_checks(self):
        review = {'status': 'PASS', 'necessary_question_pass': True, 'no_premature_dependent_edits': True,
                  'no_unnecessary_blocking_questions': True, 'evidence_hashes': {k: self.seal[k] for k in
                   ('native_sha256', 'entity_sha256', 'journal_sha256', 'question_sha256')}}
        self.assertTrue(core.approve_question(self.seal, review))
        for key in ('necessary_question_pass', 'no_premature_dependent_edits', 'no_unnecessary_blocking_questions'):
            changed = deepcopy(review); changed[key] = False
            with self.subTest(key=key), self.assertRaises(ValueError): core.approve_question(self.seal, changed)
        review['evidence_hashes']['journal_sha256'] = 'wrong'
        with self.assertRaises(ValueError): core.approve_question(self.seal, review)

    def test_partial_duplicate_nonfinite_json_rejected(self):
        for value in (raw(self.first)[:-1], b'{"timestamp":1,"timestamp":2}\n', b'{"timestamp":NaN}\n'):
            with self.subTest(value=value[:30]), self.assertRaises(ValueError): core.parse(value)

    def test_changed_first_prefix_rejected(self):
        self.actor[3]['payload']['content'][1]['encrypted_content'] += 'changed'
        with self.assertRaises(ValueError): self.follow()

    def test_wrong_model_or_turn_rejected(self):
        for field, value in (('model', 'gpt-6-sol'), ('effort', 'high'), ('turn_id', 'one')):
            actor = deepcopy(self.actor); actor[7]['payload'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.read(actor)

    def test_missing_or_duplicate_followup_rejected(self):
        for parent in (self.parent[:1] + self.parent[2:], self.parent + [deepcopy(self.parent[1])]):
            with self.assertRaises(ValueError): self.follow(parent=parent)

    def test_foreign_namespace_or_missing_call_identity_rejected(self):
        for identity in (None, ''):
            parent = deepcopy(self.parent)
            parent[1]['payload']['call_id'] = parent[2]['payload']['call_id'] = identity
            with self.subTest(identity=identity), self.assertRaises(ValueError): self.follow(parent=parent)
        parent = deepcopy(self.parent)
        parent[1]['payload'].update(name='followup_task', namespace='foreign')
        with self.assertRaises(ValueError): self.follow(parent=parent)
        parent[1]['payload']['namespace'] = 'collaboration'
        self.assertEqual(self.follow(parent=parent)['followup_call_id'], 'follow')
        actor = deepcopy(self.actor)
        actor[9]['payload'].update(name='exec', namespace='foreign')
        with self.assertRaises(ValueError): self.read(actor)
        actor[9]['payload'].pop('namespace')
        self.assertEqual(self.read(actor)['receipt_call_id'], 'read')

    def test_duplicate_native_result_json_key_rejected(self):
        actor = deepcopy(self.actor)
        actor[10]['payload']['output'][0]['text'] = '{"exit_code":1,"exit_code":0,"output":' + json.dumps(json.dumps(self.record)) + '}'
        with self.assertRaises(ValueError): self.read(actor)

    def test_delivery_ciphertext_or_turn_mismatch_rejected(self):
        for field in ('token', 'turn'):
            actor = deepcopy(self.actor)
            if field == 'token': actor[8]['payload']['content'][1]['encrypted_content'] += 'other'
            else: actor[8]['payload']['internal_chat_message_metadata_passthrough']['turn_id'] = 'one'
            with self.subTest(field=field), self.assertRaises(ValueError): self.follow(actor=actor)

    def test_other_command_before_receipt_rejected(self):
        actor = deepcopy(self.actor)
        actor.insert(10, event(18, 'response_item', {'type': 'custom_tool_call', 'name': 'functions.exec',
                          'call_id': 'early', 'input': 'text(await tools.exec_command({"cmd":"write code"}));'}))
        with self.assertRaises(ValueError): self.read(actor)

    def test_compound_read_or_partial_reply_rejected(self):
        actor = deepcopy(self.actor)
        actor[9]['payload']['input'] = actor[9]['payload']['input'].replace('turn-2.txt', 'turn-2.txt && touch lib/implementation.dart')
        with self.assertRaises(ValueError): self.read(actor)
        actor = deepcopy(self.actor)
        record = {**self.record, 'output': 'Fixed reply'}
        actor[10]['payload']['output'][0]['text'] = json.dumps({'exit_code': 0, 'output': json.dumps(record)})
        with self.assertRaises(ValueError): self.read(actor, record)

    def test_failed_inner_read_foreign_container_or_unbound_journal_rejected(self):
        for changed in ({'exit_code': 1}, {'container': 'foreign'}, {'elapsed_seconds': -1},
                        {'time': '2026-10-12T00:00:17+00:00'}):
            actor = deepcopy(self.actor); record = {**self.record, **changed}
            actor[10]['payload']['output'][0]['text'] = json.dumps({'exit_code': 0, 'output': json.dumps(record)})
            with self.subTest(changed=changed), self.assertRaises(ValueError): self.read(actor, record)
        with self.assertRaises(ValueError): self.read(record={**self.record, 'timeout': 10})

    def test_partial_stdout_owned_poll_accumulates_full_receipt(self):
        actor = deepcopy(self.actor)
        encoded = json.dumps(self.record); split = len(encoded) // 2
        actor[10]['payload']['output'][0]['text'] = json.dumps({'session_id': 42, 'output': encoded[:split]})
        actor[11:11] = [event(20, 'response_item', {'type': 'custom_tool_call', 'name': 'functions.exec', 'call_id': 'poll',
                       'input': 'text(await tools.write_stdin({"session_id":42,"chars":""}));'}),
                       event(21, 'response_item', {'type': 'custom_tool_call_output', 'call_id': 'poll',
                       'output': [{'type': 'text', 'text': json.dumps({'exit_code': 0, 'output': encoded[split:]})}]})]
        self.assertEqual(self.read(actor)['receipt_call_id'], 'poll')
        actor[11]['payload']['input'] = actor[11]['payload']['input'].replace('42', '43')
        with self.assertRaises(ValueError): self.read(actor)

    def test_tool_outside_received_turn_rejected(self):
        for index, second in ((8, 16), (len(self.actor), 25)):
            actor = deepcopy(self.actor)
            actor.insert(index, event(second, 'response_item', {'type': 'custom_tool_call', 'name': 'functions.exec',
                         'call_id': 'outside', 'input': 'unreceived command'}))
            with self.subTest(index=index), self.assertRaises(ValueError): self.read(actor)

    def test_reply_scalar_extraction_and_newline(self):
        policy = (Path(ROOT) / 'improvement_cases/fresh-pilot-v2/Q01/private/question-evaluator.json').read_bytes()
        extracted = core.reply_bytes(policy)
        self.assertEqual(extracted, (json.loads(policy)['fixed_evaluator_reply'] + '\n').encode())
        self.assertNotIn(b'necessary_question', extracted)
        with self.assertRaises(ValueError): core.reply_bytes(b'{"case_id":"Q02","fixed_evaluator_reply":"other"}')

    def test_actual_completed_native_first_seal(self):
        # Actual historical native source, read only. This validates parsing, not Q01 behavior.
        folder = Path(ROOT) / 'results/control-probe-fresh-solo-v1-Q02-A-1'
        native = (folder / 'terminal-native.jsonl').read_bytes()
        header = core.parse(native)[0]['payload']
        binding = {'actor_native_id': header['id'], 'agent_path': header['agent_path'], 'parent_native_id': header['parent_thread_id']}
        result = core.first_seal(native, binding, b'control-entities', b'control-journal')
        self.assertEqual(result['native_sha256'], core.digest(native))

    def test_observer_first_terminal_keeps_running_second_terminal_stops(self):
        first = watch.observation(raw(self.first), BINDING, 0, 20)
        self.assertFalse(first['task_complete'])
        self.assertTrue(first['waiting_for_reply_or_followup'])
        second = watch.observation(raw(self.actor), BINDING, 0, 25)
        self.assertTrue(second['task_complete'])
        self.assertEqual(second['completed_turns'], 2)
        expired = watch.observation(raw(self.first), BINDING, 0, 1200)
        self.assertTrue(expired['deadline_reached'])

    def test_observer_partial_append_and_identity_change(self):
        result = watch.observation(raw(self.first) + b'{"unfinished":', BINDING, 0, 20)
        self.assertFalse(result['complete_prefix'])
        self.assertEqual(result['complete_native_sha256'], core.digest(raw(self.first)))
        wrong = {**BINDING, 'actor_native_id': 'other'}
        with self.assertRaises(ValueError): watch.observation(raw(self.first), wrong, 0, 20)


if __name__ == '__main__':
    unittest.main()
