"""Live same-session reply barrier. No semantic grading or fabricated delivery."""
import hashlib
import json
import shlex
from datetime import datetime
from pathlib import Path

from dialogue_control import native_command_records
from transport import OPTIONS, STRING, poll_options, result_objects, wrapper_origin
import re

SCRIPT = 'improvement_dialogue_io_v1.py'
READ = 'cat /eval-input/turn-2.txt'
MODEL = {'model': 'gpt-6.1-sol', 'effort': 'medium'}


def parse(raw):
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete native prefix; observe the same session again')
    return [json.loads(line) for line in raw.splitlines()]


def wrapper(code, root, run_id):
    return SCRIPT in code and wrapper_origin(code.replace(SCRIPT, 'agent_io.py'), root, run_id)


def exact_read(code, root, run_id):
    expression = r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*'
    match = re.fullmatch(expression + '(' + STRING + ')' + OPTIONS + r'\s*\}\s*\)\s*\)\s*;?\s*', code.strip())
    if not match:
        return False
    return shlex.split(json.loads(match.group(1))) == [
        'python3', str(Path(root) / 'tools' / SCRIPT), '--run', run_id, '--cmd', READ]


def audit(events, metadata, root):
    """Closed literal wrapper/poll routes. Unknown native tools fail qualification."""
    calls, owned, violations = {}, {}, []
    for event in events:
        p = event.get('payload', {})
        kind, call_id = p.get('type'), p.get('call_id')
        if kind in {'function_call', 'custom_tool_call'}:
            name = p.get('name')
            code = p.get('input', p.get('arguments', ''))
            if not isinstance(code, str) or name not in {'exec', 'functions.exec'}:
                violations.append({'call_id': call_id, 'reason': 'unsupported tool route'})
                continue
            options = poll_options(code)
            if options and options['session_id'] in owned:
                calls[call_id] = ('poll', options['session_id'])
            elif code.strip() == metadata.get('bootstrap_code'):
                calls[call_id] = ('bootstrap', None)
            elif wrapper(code, root, metadata['run_id']):
                calls[call_id] = ('wrapper', None)
            else:
                violations.append({'call_id': call_id, 'reason': 'unproven wrapper or poll'})
        elif kind in {'function_call_output', 'custom_tool_call_output'}:
            mode, sid = calls.get(call_id, (None, None))
            if mode not in {'wrapper', 'poll'}:
                continue
            values = list(result_objects(p))
            if len(values) != 1:
                violations.append({'call_id': call_id, 'reason': 'unknown native tool result'})
                continue
            value = values[0]
            if mode == 'wrapper' and type(value.get('session_id')) is int and 'exit_code' not in value:
                owned[value['session_id']] = call_id
            if mode == 'poll':
                if value.get('session_id') not in {None, sid} or not isinstance(value.get('output'), str):
                    violations.append({'call_id': call_id, 'reason': 'poll identity/result mismatch'})
                if type(value.get('exit_code')) is int:
                    owned.pop(sid, None)
    return violations


def reply_barrier(actor_raw, parent_raw, metadata, staged, command_records, root):
    """Require actual parent routing and complete native stdout before writes."""
    events, parent = parse(actor_raw), parse(parent_raw)
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
    dispatches, returns = [], {}
    for event in parent:
        q = event.get('payload', {})
        if q.get('type') == 'function_call' and q.get('name', '').split('.')[-1] == 'followup_task':
            args = q.get('arguments', {})
            args = json.loads(args) if isinstance(args, str) else args
            if args.get('target') in {metadata['agent_path'], metadata['agent_path'].rsplit('/', 1)[-1]}:
                dispatches.append((event, args))
        if q.get('type') == 'function_call_output':
            if q.get('call_id') in returns:
                raise ValueError('Duplicate parent receipt')
            returns[q.get('call_id')] = event
    if len(dispatches) != 1:
        raise ValueError('Expected exactly one parent followup')
    dispatch, args = dispatches[0]
    returned = returns.get(dispatch['payload']['call_id'])
    if returned is None or returned['payload'].get('output') != '' or args.get('message') != p.get('message'):
        raise ValueError('Missing successful same-session dispatch receipt')
    if not first_ends[0]['timestamp'] < dispatch['timestamp'] <= message['timestamp'] <= returned['timestamp']:
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
                    reads[q['call_id']] = q['call_id']
                else:
                    options = poll_options(code)
                    if options and options['session_id'] in owned:
                        reads[q['call_id']] = owned[options['session_id']]
        elif q.get('type') in {'function_call_output', 'custom_tool_call_output'} and q.get('call_id') in reads:
            for value in result_objects(q):
                if type(value.get('session_id')) is int and 'exit_code' not in value:
                    owned[value['session_id']] = reads[q['call_id']]
            if any(record in candidates for record in native_command_records(q)):
                return {'read_receipt_call_id': q['call_id'], 'actor_native_prefix_bytes': len(actor_raw),
                        'actor_native_prefix_sha256': hashlib.sha256(actor_raw).hexdigest(),
                        'parent_native_prefix_bytes': len(parent_raw), 'parent_native_prefix_sha256': hashlib.sha256(parent_raw).hexdigest(),
                        'followup_call_id': dispatch['payload']['call_id'], 'same_session': True}
    raise ValueError('Complete native reply-read receipt not yet observed')
