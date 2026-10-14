"""Pure Q01 chronology checks. No actor execution, staging or semantic grading.

This is retrospective eligibility evidence, not a preventive filesystem barrier.
The adapter must separately bind owned container identity, immutable artifacts,
observer continuity, original deadline and the registered transport audit.
"""
from datetime import datetime, timedelta
import hashlib
import json
import math
import re
import shlex

import improvement_composed_quote_origin_v7 as origin
from transport import OPTIONS, STRING, poll_options

VERSION = 'improvement-q01-dialogue-core-v1'
READ = 'cat /eval-input/turn-2.txt'


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON key')
        value[key] = item
    return value


def decode(value):
    def bad_constant(item):
        raise ValueError('Nonfinite JSON constant: ' + item)
    return json.loads(value, object_pairs_hook=unique, parse_constant=bad_constant)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def instant(value):
    require(isinstance(value, str), 'Missing native timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'Naive timestamp')
    return result


def parse(raw):
    require(isinstance(raw, bytes) and raw.endswith(b'\n'), 'Incomplete native prefix')
    events = [decode(line) for line in raw.splitlines()]
    require(bool(events), 'Empty native source')
    previous = None
    for event in events:
        require(isinstance(event, dict) and isinstance(event.get('payload'), dict), 'Malformed native event')
        current = instant(event.get('timestamp'))
        require(previous is None or previous <= current, 'Native timestamps out of order')
        previous = current
    return events


def turn_id(payload):
    return payload.get('turn_id') or payload.get('internal_chat_message_metadata_passthrough', {}).get('turn_id')


def route(payload, namespace, name):
    return ((payload.get('name') == name and payload.get('namespace') == namespace)
            or (payload.get('name') == namespace + '.' + name and payload.get('namespace') in (None, namespace))
            or (namespace == 'functions' and name == 'exec' and payload.get('type') == 'custom_tool_call'
                and payload.get('name') == 'exec' and payload.get('namespace') is None))


def final_text(payload):
    blocks = payload.get('content')
    require(isinstance(blocks, list) and bool(blocks), 'Missing final content')
    require(all(isinstance(b, dict) and b.get('type') == 'output_text' and isinstance(b.get('text'), str)
                for b in blocks), 'Unknown final content block')
    return ''.join(b['text'] for b in blocks)


def lifecycle(raw, binding, expected_turns):
    require(type(expected_turns) is int and expected_turns in (1, 2), 'Unsupported turn count')
    events = parse(raw)
    headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
    require(len(headers) == 1 and events[0].get('type') == 'session_meta', 'Ambiguous session header')
    header = headers[0]
    require(header.get('id') == binding['actor_native_id']
            and header.get('agent_path') == binding['agent_path']
            and header.get('parent_thread_id') == binding['parent_native_id'], 'Actor session identity changed')
    groups = {name: [] for name in ('start', 'context', 'incoming', 'final', 'complete')}
    for index, event in enumerate(events):
        p = event['payload']
        name = None
        if event.get('type') == 'turn_context':
            name = 'context'
            require(p.get('model') == 'gpt-6.1-sol' and p.get('effort') == 'medium', 'Model or reasoning changed')
            settings = p.get('collaboration_mode', {}).get('settings')
            if settings is not None:
                require(settings.get('model') == 'gpt-6.1-sol' and settings.get('reasoning_effort') == 'medium',
                        'Conflicting collaboration model settings')
        elif event.get('type') == 'event_msg' and p.get('type') in ('task_started', 'task_complete'):
            name = 'start' if p['type'] == 'task_started' else 'complete'
        elif event.get('type') == 'response_item':
            if p.get('type') == 'agent_message':
                name = 'incoming'
                require(p.get('author') == binding['agent_path'].rsplit('/', 1)[0]
                        and p.get('recipient') == binding['agent_path'], 'Incoming routing changed')
            elif p.get('type') == 'message' and p.get('role') == 'assistant' and (
                    p.get('channel') == 'final' or p.get('phase') == 'final_answer'):
                name = 'final'
        if name:
            groups[name].append((index, event))
    require(all(len(rows) == expected_turns for rows in groups.values()), 'Incomplete or additional turn lifecycle')
    ids, turns = set(), []
    last_end = -1
    for n in range(expected_turns):
        rows = [groups[name][n] for name in ('start', 'context', 'incoming', 'final', 'complete')]
        indexes = [i for i, _ in rows]
        require(last_end < indexes[0] and indexes == sorted(set(indexes)), 'Turn lifecycle ordering mismatch')
        ids_here = [turn_id(e['payload']) for _, e in rows]
        identity = ids_here[0]
        require(isinstance(identity, str) and bool(identity) and len(set(ids_here)) == 1 and identity not in ids,
                'Turn identity mismatch or reuse')
        ids.add(identity)
        text = final_text(rows[3][1]['payload'])
        require(rows[4][1]['payload'].get('last_agent_message') == text, 'Completion final text mismatch')
        turns.append({'turn_id': identity, 'start_index': indexes[0], 'incoming_index': indexes[2],
                      'final_index': indexes[3], 'complete_index': indexes[4], 'final_text': text,
                      'completed_at': rows[4][1]['timestamp']})
        last_end = indexes[4]
    for index, event in enumerate(events):
        if event.get('type') == 'response_item' and event['payload'].get('type') in (
                'function_call', 'custom_tool_call', 'function_call_output', 'custom_tool_call_output'):
            require(any(t['incoming_index'] < index < t['final_index'] for t in turns),
                    'Tool event outside an active received turn')
    return events, turns


def first_seal(raw, binding, entity_raw, journal_raw):
    _, turns = lifecycle(raw, binding, 1)
    return {'version': VERSION, 'binding': dict(binding), 'native_bytes': len(raw),
            'native_sha256': digest(raw), 'entity_sha256': digest(entity_raw),
            'journal_sha256': digest(journal_raw), 'question_sha256': digest(turns[0]['final_text'].encode()),
            'turn': turns[0], 'preventive_write_barrier': False}


def approve_question(seal, review):
    """Independent semantic review must inspect all edits, not just final wording."""
    require(review.get('status') == 'PASS', 'First-question semantic review did not pass')
    for key in ('necessary_question_pass', 'no_premature_dependent_edits', 'no_unnecessary_blocking_questions'):
        require(review.get(key) is True, 'Missing independent semantic check: ' + key)
    require(review.get('evidence_hashes') == {k: seal[k] for k in
            ('native_sha256', 'entity_sha256', 'journal_sha256', 'question_sha256')}, 'Question review evidence changed')
    return True


def reply_bytes(policy_raw):
    policy = decode(policy_raw)
    require(policy.get('case_id') == 'Q01', 'Wrong private reply policy')
    reply = policy.get('fixed_evaluator_reply')
    require(isinstance(reply, str) and bool(reply) and not reply.endswith('\n'), 'Malformed fixed reply')
    return (reply + '\n').encode('utf-8')


def delivery_token(payload):
    """Join actual modern content blocks without claiming ciphertext decryption."""
    blocks = payload.get('content')
    require(isinstance(blocks, list) and len(blocks) in (1, 2), 'Unknown delivery content')
    require(all(isinstance(b, dict) and b.get('type') in ('input_text', 'encrypted_content') for b in blocks),
            'Unknown delivery block')
    encrypted = [b.get('encrypted_content') for b in blocks if b.get('type') == 'encrypted_content']
    texts = [b.get('text') for b in blocks if b.get('type') == 'input_text']
    require(all(isinstance(t, str) for t in texts), 'Malformed delivery text')
    if encrypted:
        require(len(encrypted) == 1 and len(texts) <= 1 and isinstance(encrypted[0], str)
                and encrypted[0].startswith('gAAAAA'), 'Ambiguous encrypted delivery')
        return encrypted[0], False
    require(len(texts) == 1 and len(blocks) == 1, 'Ambiguous plaintext delivery')
    return texts[0], True


def followup_proof(actor_raw, parent_raw, binding, seal, staged_at, followup):
    require(actor_raw[:seal['native_bytes']] and digest(actor_raw[:seal['native_bytes']]) == seal['native_sha256'],
            'Preserved first prefix changed')
    events, turns = lifecycle(actor_raw, binding, 2)
    require(turns[0] == seal['turn'], 'First turn changed')
    parent = parse(parent_raw)
    headers = [e['payload'] for e in parent if e.get('type') == 'session_meta']
    require(len(headers) == 1 and headers[0].get('id') == binding['parent_native_id'], 'Wrong parent source')
    target = binding['agent_path']
    calls, outputs, parent_call_ids = [], {}, set()
    for i, e in enumerate(parent):
        p = e['payload']
        if p.get('type') in ('function_call', 'custom_tool_call'):
            identity = p.get('call_id')
            require(isinstance(identity, str) and bool(identity) and identity not in parent_call_ids,
                    'Missing or duplicate parent call identity')
            parent_call_ids.add(identity)
        if p.get('type') == 'function_call' and route(p, 'collaboration', 'followup_task'):
            args = decode(p['arguments']) if isinstance(p.get('arguments'), str) else p.get('arguments')
            require(isinstance(args, dict), 'Malformed parent followup arguments')
            if args.get('target') in (target, target.rsplit('/', 1)[-1]):
                calls.append((i, e, args))
        if p.get('type') in ('function_call_output', 'custom_tool_call_output'):
            identity = p.get('call_id')
            require(identity in parent_call_ids and identity not in outputs, 'Unmatched or duplicate parent output')
            outputs[identity] = (i, e)
    require(len(calls) == 1, 'Expected exactly one same-actor followup')
    ci, call, args = calls[0]
    receipt = outputs.get(call['payload'].get('call_id'))
    require(receipt is not None and receipt[0] > ci and receipt[1]['payload'].get('output') == '',
            'Missing successful native followup receipt')
    incoming = events[turns[1]['incoming_index']]
    token, readable = delivery_token(incoming['payload'])
    # The actual parent records the encrypted followup argument, not a separate
    # delivered agent_message. Child lifecycle already binds author and turn ID.
    require(args.get('message') == token, 'Native followup argument and delivered token differ')
    if readable:
        require(token == followup, 'Readable delivered followup differs from staged intent')
    require(instant(seal['turn']['completed_at']) < instant(staged_at) <= instant(call['timestamp'])
            <= instant(incoming['timestamp']), 'Reply delivery chronology mismatch')
    require(instant(call['timestamp']) <= instant(receipt[1]['timestamp']), 'Followup receipt precedes call')
    return {'followup_call_id': call['payload']['call_id'], 'second_turn_id': turns[1]['turn_id'],
            'actor_sha256': digest(actor_raw), 'parent_sha256': digest(parent_raw),
            'delivery_token_sha256': digest(token.encode()), 'encrypted_plaintext_decrypted': False,
            'plaintext_followup_verified': readable}


def exact_read(code, root, run_id):
    view = origin.inline_view(code, root, run_id) or code
    match = re.fullmatch(r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*('
                         + STRING + ')' + OPTIONS + r'\s*\}\s*\)\s*\)\s*;?\s*', view.strip())
    if not match:
        return False
    try:
        return shlex.split(decode(match.group(1))) == ['python3', root + '/tools/agent_io.py', '--run', run_id, '--cmd', READ]
    except ValueError:
        return False


def result_values(payload):
    output = payload.get('output')
    texts = [part.get('text') for part in output if isinstance(part, dict)] if isinstance(output, list) else [output]
    for text in texts:
        if isinstance(text, str) and text.lstrip().startswith('{'):
            value = decode(text)
            require(isinstance(value, dict), 'Malformed native tool result')
            yield value


def read_receipt(actor_raw, binding, expected_reply, command_records, root, run_id, container):
    events, turns = lifecycle(actor_raw, binding, 2)
    expected = expected_reply.decode('utf-8')
    pending, owned, output_chunks = None, {}, []
    for index, e in enumerate(events[turns[1]['incoming_index'] + 1:], turns[1]['incoming_index'] + 1):
        p = e['payload']
        kind, identity = p.get('type'), p.get('call_id')
        if kind in ('function_call', 'custom_tool_call'):
            code = p.get('input', p.get('arguments'))
            require(route(p, 'functions', 'exec') and isinstance(code, str), 'Unsupported pre-receipt tool')
            if pending is None:
                require(exact_read(code, root, run_id), 'First second-turn command is not the sole exact reply read')
                pending = (identity, e)
            else:
                opts = poll_options(code)
                require(opts is not None and opts['session_id'] in owned, 'Command before complete reply receipt')
                owned[opts['session_id']]['poll'] = identity
        elif kind in ('function_call_output', 'custom_tool_call_output'):
            require(pending is not None, 'Read output before invocation')
            is_origin = identity == pending[0]
            sid = next((s for s, v in owned.items() if v.get('poll') == identity), None)
            require(is_origin or sid is not None, 'Unowned reply poll output')
            values = list(result_values(p))
            require(len(values) == 1, 'Ambiguous native read result')
            value = values[0]
            require(isinstance(value.get('output'), str), 'Missing native read stdout')
            output_chunks.append(value['output'])
            if 'exit_code' not in value:
                new_sid = value.get('session_id', sid)
                require(type(new_sid) is int and new_sid > 0 and (is_origin or new_sid == sid), 'Unknown read session')
                if is_origin:
                    require(new_sid not in owned, 'Duplicate read session')
                    owned[new_sid] = {}
                continue
            require(type(value['exit_code']) is int and value['exit_code'] == 0, 'Reply read host execution failed')
            record = decode(''.join(output_chunks))
            require(isinstance(record, dict) and record in command_records, 'Native reply stdout not bound to broker journal')
            require(record.get('command') == READ and record.get('container') == container
                    and type(record.get('exit_code')) is int and record['exit_code'] == 0
                    and record.get('output') == expected, 'Complete successful fixed reply not received')
            elapsed = record.get('elapsed_seconds')
            require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0, 'Invalid broker duration')
            require(instant(pending[1]['timestamp']) <= instant(record['time'])
                    <= instant(record['time']) + timedelta(seconds=elapsed) <= instant(e['timestamp']), 'Broker receipt time mismatch')
            return {'read_call_id': pending[0], 'receipt_call_id': identity, 'receipt_index': index,
                    'received_at': e['timestamp'], 'reply_sha256': digest(expected_reply),
                    'journal_record_sha256': digest(json.dumps(record, sort_keys=True).encode()),
                    'preventive_write_barrier': False}
    raise ValueError('Missing complete native reply receipt')
