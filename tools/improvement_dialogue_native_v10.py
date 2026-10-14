"""Live same-session reply barrier. No semantic grading or fabricated delivery."""
import hashlib
import math
import json
import shlex
from datetime import datetime, timedelta
from pathlib import Path

from dialogue_control import native_command_records
from dialogue_schema import normalize
from transport import OPTIONS, STRING, poll_options, result_objects
from improvement_dialogue_literal_template_v1 import project
import re

SCRIPT = 'improvement_dialogue_io_v10.py'
READ = 'cat /eval-input/turn-2.txt'
MODEL = {'model': 'gpt-6.1-sol', 'effort': 'medium'}


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def parse(raw):
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete native prefix; observe the same session again')
    return [json.loads(line) for line in raw.splitlines()]


def wrapper(code, root, run_id):
    """Parse the exact outer broker. Inner command text cannot select the broker."""
    projected = project(code)
    if projected is not None:
        code = projected
    expression = r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*'
    end = OPTIONS + r'\s*\}\s*\)\s*\)\s*;?\s*'
    direct = re.fullmatch(expression + '(' + STRING + ')' + end, code.strip())
    prefix = f'python3 {root}/tools/{SCRIPT} --run {run_id} --cmd '
    if direct:
        command = json.loads(direct.group(1))
        if not command.startswith(prefix) or not re.fullmatch(r"(?:'[^']*'|\\'|\"'\")+", command[len(prefix):], re.S):
            return False
    else:
        template = re.fullmatch(r'const\s+(\w+)\s*=\s*`((?:\\.|[^`\\])*)`\s*;\s*(.*)', code.strip(), re.S)
        if not template or '${' in template.group(2):
            return False
        variable = re.escape(template.group(1))
        concat = re.fullmatch(expression + '(' + STRING + r'(?:\s*\+\s*' + STRING + r')?)\s*\+\s*' + variable +
                             r"\.replace\(\s*/'/g\s*,\s*(" + STRING + r')\s*\)\s*\+\s*(' + STRING + ')' + end, template.group(3), re.S)
        if not concat:
            return False
        actual_prefix = ''.join(json.loads(item.group()) for item in re.finditer(STRING, concat.group(1)))
        escape, suffix = (json.loads(concat.group(i)) for i in (2, 3))
        if actual_prefix != prefix + "'" or escape != "'\\''" or suffix != "'":
            return False
        command = prefix + "'transport_origin_marker'"
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return parts[:5] == ['python3', f'{root}/tools/{SCRIPT}', '--run', run_id, '--cmd'] and len(parts) == 6


def exact_read(code, root, run_id):
    projected = project(code)
    if projected is not None:
        code = projected
    expression = r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*'
    match = re.fullmatch(expression + '(' + STRING + ')' + OPTIONS + r'\s*\}\s*\)\s*\)\s*;?\s*', code.strip())
    if not match:
        return False
    return shlex.split(json.loads(match.group(1))) == [
        'python3', str(Path(root) / 'tools' / SCRIPT), '--run', run_id, '--cmd', READ]


def equivalent_bootstrap(code, expected):
    """Compare closed JSON literals, allowing harmless formatting only."""
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('Duplicate literal key')
            value[key] = item
        return value
    def literal(value):
        if not isinstance(value, str):
            return None
        match = re.fullmatch(r'\s*text\(\s*await\s+tools\.exec_command\(\s*(\{.*\})\s*\)\s*\)\s*;?\s*', value, re.DOTALL)
        if not match:
            return None
        try:
            options = json.loads(match.group(1), object_pairs_hook=unique)
        except (ValueError, TypeError):
            return None
        if not isinstance(options, dict) or set(options) != {'cmd', 'max_output_tokens'}:
            return None
        if not isinstance(options['cmd'], str) or type(options['max_output_tokens']) is not int:
            return None
        return options
    actual, approved = literal(code), literal(expected)
    return actual is not None and approved is not None and actual == approved


def audit(events, metadata, root, require_closed=False):
    """Closed literal wrapper/poll routes. Unknown native tools fail qualification."""
    calls, owned, violations = {}, {}, []
    seen_calls, seen_outputs, seen_sessions = set(), set(), set()
    call_times, session_receipt_times = {}, {}
    qualified_results = set()
    for event in events:
        p = event.get('payload', {})
        kind, call_id = p.get('type'), p.get('call_id')
        if kind in {'function_call', 'custom_tool_call'}:
            if not isinstance(call_id, str) or not call_id or call_id in seen_calls:
                violations.append({'call_id': call_id, 'reason': 'missing or duplicate native call identity'})
                continue
            seen_calls.add(call_id)
            call_times[call_id] = instant(event['timestamp'])
            name = p.get('name')
            code = p.get('input', p.get('arguments', ''))
            if not isinstance(code, str) or name not in {'exec', 'functions.exec'}:
                violations.append({'call_id': call_id, 'reason': 'unsupported tool route'})
                continue
            options = poll_options(code)
            if options and options['session_id'] in owned:
                if call_times[call_id] < session_receipt_times[options['session_id']]:
                    violations.append({'call_id': call_id, 'reason': 'poll precedes actual session receipt'})
                calls[call_id] = ('poll', options['session_id'])
            elif not calls and equivalent_bootstrap(code, metadata.get('bootstrap_code')):
                calls[call_id] = ('bootstrap', None)
            elif wrapper(code, root, metadata['run_id']):
                calls[call_id] = ('wrapper', None)
            else:
                violations.append({'call_id': call_id, 'reason': 'unproven wrapper or poll'})
        elif kind in {'function_call_output', 'custom_tool_call_output'}:
            if call_id not in seen_calls or call_id in seen_outputs:
                violations.append({'call_id': call_id, 'reason': 'unmatched or duplicate native output identity'})
                continue
            seen_outputs.add(call_id)
            if instant(event['timestamp']) < call_times[call_id]:
                violations.append({'call_id': call_id, 'reason': 'native output precedes its actual invocation'})
            mode, sid = calls.get(call_id, (None, None))
            if mode not in {'bootstrap', 'wrapper', 'poll'}:
                continue
            values = list(result_objects(p))
            if len(values) != 1:
                violations.append({'call_id': call_id, 'reason': 'unknown native tool result'})
                continue
            value = values[0]
            terminal_result = type(value.get('exit_code')) is int and isinstance(value.get('output'), str)
            running_result = type(value.get('session_id')) is int and value['session_id'] > 0 and 'exit_code' not in value and isinstance(value.get('output'), str)
            polling_result = mode == 'poll' and 'exit_code' not in value and isinstance(value.get('output'), str) and value.get('session_id') in {None, sid}
            if terminal_result or running_result or polling_result:
                qualified_results.add(call_id)
            if mode in {'bootstrap', 'wrapper'} and type(value.get('session_id')) is int and 'exit_code' not in value:
                sid_new = value['session_id']
                if sid_new <= 0:
                    violations.append({'call_id': call_id, 'reason': 'nonpositive native session identity'})
                if sid_new in seen_sessions:
                    violations.append({'call_id': call_id, 'reason': 'native session identity reused'})
                seen_sessions.add(sid_new)
                owned[sid_new] = call_id
                session_receipt_times[sid_new] = instant(event['timestamp'])
            if mode == 'poll':
                session_receipt_times[sid] = instant(event['timestamp'])
                if value.get('session_id') not in {None, sid} or not isinstance(value.get('output'), str):
                    violations.append({'call_id': call_id, 'reason': 'poll identity/result mismatch'})
                if type(value.get('exit_code')) is int:
                    owned.pop(sid, None)
    if require_closed:
        for call_id in sorted(seen_calls - seen_outputs):
            violations.append({'call_id': call_id, 'reason': 'terminal native call has no output'})
        for call_id, (mode, _) in calls.items():
            if mode in {'bootstrap', 'wrapper', 'poll'} and call_id in seen_outputs and call_id not in qualified_results:
                violations.append({'call_id': call_id, 'reason': 'terminal tool result is unqualified'})
        for session_id in sorted(owned):
            violations.append({'session_id': session_id, 'reason': 'terminal poll session remains open'})
    return violations


def reply_barrier(actor_raw, parent_raw, metadata, staged, command_records, root):
    """Require actual parent routing and complete native stdout before writes."""
    events, mappings = normalize(parse(actor_raw))
    parent = parse(parent_raw)
    prefix = actor_raw[:staged['first_native_bytes']]
    if hashlib.sha256(prefix).hexdigest() != staged['first_native_sha256']:
        raise ValueError('First native prefix changed')
    headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
    if len(headers) != 1 or headers[0].get('id') != metadata['actor_native_id'] or headers[0].get('agent_path') != metadata['agent_path']:
        raise ValueError('Actor identity changed')
    contexts = [(i, e['payload']) for i, e in enumerate(events) if e.get('type') == 'turn_context']
    if len(contexts) != 2 or any({k: p.get(k) for k in MODEL} != MODEL for _, p in contexts):
        raise ValueError('Expected two qualified native contexts')
    incoming = [(i, e) for i, e in enumerate(events) if e.get('payload', {}).get('type') == 'agent_message']
    if len(incoming) != 2:
        raise ValueError('Expected same-session second incoming request')
    first = parse(prefix)
    first_ends = [e for e in first if e.get('payload', {}).get('type') == 'task_complete']
    if len(first_ends) != 1 or contexts[1][0] < len(first):
        raise ValueError('Followup preceded the preserved first completion')
    index, message = incoming[1]
    p = message['payload']
    parent_path = metadata['agent_path'].rsplit('/', 1)[0]
    if not contexts[1][0] < index or p.get('recipient') != metadata['agent_path'] or p.get('author') != parent_path:
        raise ValueError('Followup routing mismatch')
    if p.get('internal_chat_message_metadata_passthrough', {}).get('turn_id') != contexts[1][1].get('turn_id'):
        raise ValueError('Followup turn mismatch')
    parent_headers = [e['payload'] for e in parent if e.get('type') == 'session_meta']
    if len(parent_headers) != 1 or parent_headers[0].get('id') != headers[0].get('parent_thread_id'):
        raise ValueError('Wrong actual parent native source')
    dispatches, returns, parent_calls = [], {}, set()
    for parent_index, event in enumerate(parent):
        q = event.get('payload', {})
        if q.get('type') in {'function_call', 'custom_tool_call'}:
            identity = q.get('call_id')
            if not isinstance(identity, str) or not identity or identity in parent_calls:
                raise ValueError('Missing or duplicate parent call identity')
            parent_calls.add(identity)
        if q.get('type') == 'function_call' and q.get('name') in {'followup_task', 'collaboration.followup_task'}:
            args = q.get('arguments', {})
            args = json.loads(args) if isinstance(args, str) else args
            if args.get('target') in {metadata['agent_path'], metadata['agent_path'].rsplit('/', 1)[-1]}:
                dispatches.append((parent_index, event, args))
        if q.get('type') in {'function_call_output', 'custom_tool_call_output'}:
            if q.get('call_id') not in parent_calls or q.get('call_id') in returns:
                raise ValueError('Duplicate parent receipt')
            returns[q.get('call_id')] = (parent_index, event)
    if len(dispatches) != 1:
        raise ValueError('Expected exactly one parent followup')
    dispatch_index, dispatch, args = dispatches[0]
    receipt = returns.get(dispatch['payload']['call_id'])
    returned = receipt[1] if receipt else None
    if receipt and receipt[0] <= dispatch_index:
        raise ValueError('Parent receipt precedes dispatch in native source')
    if returned is None or returned['payload'].get('output') != '' or args.get('message') != p.get('message'):
        raise ValueError('Missing successful same-session dispatch receipt')
    if (not instant(first_ends[0]['timestamp']) < instant(dispatch['timestamp']) <= instant(message['timestamp'])
            or not instant(dispatch['timestamp']) <= instant(returned['timestamp'])):
        raise ValueError('Dispatch chronology mismatch')
    if datetime.fromisoformat(dispatch['timestamp'].replace('Z', '+00:00')).timestamp() < staged['staged_at']:
        raise ValueError('Followup dispatched before reply staging')
    if not isinstance(p.get('message'), str):
        raise ValueError('Missing native followup token')
    if p['message'].startswith('gAAAAA') is False and p['message'] != staged['followup']:
        raise ValueError('Readable followup differs from staged request')
    if audit(events, metadata, root):
        raise ValueError('Unknown actor tool route; write barrier stays closed')
    expected = staged['reply_utf8']
    candidates = [r for r in command_records if r.get('run_id') == metadata['run_id'] and r.get('container_id') == staged['reply_container_id'] and r.get('phase') == 'reply_read' and r.get('command') == READ and r.get('exit_code') == 0 and r.get('output') == expected]
    reads, owned = {}, {}
    for event in events[index + 1:]:
        q = event.get('payload', {})
        if q.get('type') in {'function_call', 'custom_tool_call'}:
            code = q.get('input', q.get('arguments', ''))
            if q.get('name') in {'exec', 'functions.exec'} and isinstance(code, str):
                if exact_read(code, root, metadata['run_id']):
                    reads[q['call_id']] = (q['call_id'], event['timestamp'])
                else:
                    options = poll_options(code)
                    if options and options['session_id'] in owned:
                        reads[q['call_id']] = owned[options['session_id']]
        elif q.get('type') in {'function_call_output', 'custom_tool_call_output'} and q.get('call_id') in reads:
            for value in result_objects(q):
                if type(value.get('session_id')) is int and 'exit_code' not in value:
                    owned[value['session_id']] = reads[q['call_id']]
                if type(value.get('exit_code')) is int:
                    owned.pop(value.get('session_id'), None)
                    # Terminal polls may omit their session id.
                    code_origin = reads[q['call_id']]
                    owned = {sid: origin for sid, origin in owned.items() if origin != code_origin}
            original_call_id, original_time = reads[q['call_id']]
            if not instant(message['timestamp']) <= instant(original_time) <= instant(event['timestamp']):
                raise ValueError('Native read receipt preceded its call or followup')
            matching = [record for record in native_command_records(q) if record in candidates]
            for record in matching:
                started = datetime.fromisoformat(record['time'])
                called = datetime.fromisoformat(original_time.replace('Z', '+00:00'))
                received = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                elapsed = record.get('elapsed_seconds')
                if type(elapsed) not in {int, float} or not math.isfinite(elapsed) or elapsed < 0:
                    raise ValueError('Missing or invalid broker completion duration')
                if not called <= started <= started + timedelta(seconds=elapsed) <= received:
                    raise ValueError('Broker read start outside actual native call/receipt interval')
            if matching:
                return {'read_receipt_call_id': q['call_id'], 'actor_native_prefix_bytes': len(actor_raw),
                        'actor_native_prefix_sha256': hashlib.sha256(actor_raw).hexdigest(),
                        'parent_native_prefix_bytes': len(parent_raw), 'parent_native_prefix_sha256': hashlib.sha256(parent_raw).hexdigest(),
                        'followup_call_id': dispatch['payload']['call_id'], 'same_session': True,
                        'native_message_normalization': mappings, 'encrypted_plaintext_decrypted': False}
    raise ValueError('Complete native reply-read receipt not yet observed')
