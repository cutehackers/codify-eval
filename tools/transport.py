"""Qualify read-only polling only when its wrapper origin is proven."""
import json
import re
import shlex

STRING = r'"(?:\\.|[^"\\])*"'
OPTIONS = r'(?:\s*,\s*"?(?:max_output_tokens|yield_time_ms)"?\s*:\s*\d+)*\s*,?'


def wrapper_origin(code, root, run_id):
    """Recognize literal wrapper calls; unsupported JavaScript fails closed."""
    expression = r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*'
    end = OPTIONS + r'\s*\}\s*\)\s*\)\s*;?\s*'
    direct = re.fullmatch(expression + '(' + STRING + ')' + end, code.strip())
    command = None
    if direct:
        command = json.loads(direct.group(1))
        prefix = f'python3 {root}/tools/agent_io.py --run {run_id} --cmd '
        if not command.startswith(prefix) or not re.fullmatch(r"(?:'[^']*'|\\'|\"'\")+", command[len(prefix):], re.S):
            return False
    else:
        template = re.fullmatch(r'const\s+(\w+)\s*=\s*`((?:\\.|[^`\\])*)`\s*;\s*(.*)',
                                code.strip(), re.S)
        if not template or '${' in template.group(2):
            return False
        variable = re.escape(template.group(1))
        concat = re.fullmatch(expression + '(' + STRING + r'(?:\s*\+\s*' + STRING + r')?)\s*\+\s*' + variable +
                             r"\.replace\(\s*/'/g\s*,\s*(" + STRING + r')\s*\)\s*\+\s*(' +
                             STRING + ')' + end, template.group(3), re.S)
        if not concat:
            return False
        prefix = ''.join(json.loads(item.group()) for item in re.finditer(STRING, concat.group(1)))
        escape, suffix = (json.loads(concat.group(i)) for i in (2, 3))
        if prefix != f"python3 {root}/tools/agent_io.py --run {run_id} --cmd '" or escape != "'\\''" or suffix != "'":
            return False
        command = prefix + 'transport_origin_marker' + suffix
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return parts[:5] == ['python3', f'{root}/tools/agent_io.py', '--run', run_id, '--cmd'] and len(parts) == 6


def poll_options(code):
    match = re.fullmatch(r'text\s*\(\s*await\s+tools\.write_stdin\s*\(\s*(\{[^{}]*\})\s*\)\s*\)\s*;?',
                         code.strip(), re.S)
    if not match:
        return None
    body = re.sub(r'(?<!["\w])([A-Za-z_]\w*)\s*:', r'"\1":', match.group(1))
    body = re.sub(r",\s*\}", '}', body.replace("''", '""'))
    try:
        options = json.loads(body)
    except ValueError:
        return None
    if set(options) - {'session_id', 'chars', 'yield_time_ms', 'max_output_tokens'}:
        return None
    if type(options.get('session_id')) is not int or options.get('chars', '') != '':
        return None
    if any(type(options[key]) is not int or options[key] < 0
           for key in ('yield_time_ms', 'max_output_tokens') if key in options):
        return None
    return options


def result_objects(payload):
    output = payload.get('output', [])
    texts = [part.get('text', '') for part in output if isinstance(part, dict)] if isinstance(output, list) else [output]
    for text in texts:
        if not isinstance(text, str):
            continue
        try:
            value = json.loads(text)
        except ValueError:
            continue
        if isinstance(value, dict):
            yield value


def audit_transport(events, metadata, root):
    violations, polls, calls, owned = [], [], {}, {}
    for event in events:
        payload = event.get('payload', {})
        kind = payload.get('type')
        call_id = payload.get('call_id')
        if kind in {'function_call', 'custom_tool_call'}:
            name = payload.get('name', '')
            code = str(payload.get('arguments', payload.get('input', '')))
            options = poll_options(code) if name in {'functions.exec', 'exec'} else None
            if options is not None and options['session_id'] in owned:
                origin = owned[options['session_id']]
                proof = {'session_id': options['session_id'], 'origin_call_id': origin,
                         'poll_call_id': call_id, 'empty_stdin': True}
                polls.append(proof)
                calls[call_id] = ('poll', options['session_id'])
                continue
            if name in {'functions.exec', 'exec'} and code.strip() == metadata.get('bootstrap_code'):
                calls[call_id] = ('bootstrap', None)
                continue
            reason = None
            if name not in {'functions.exec', 'exec'} or 'agent_io.py' not in code:
                reason = 'tool call bypasses scoped transport'
            elif any(word in code for word in ['tools.view_image', 'tools.web__', 'tools.mcp__',
                                               'tools.apply_patch', 'tools.write_stdin']):
                reason = 'additional unscoped tool access'
            if reason:
                violations.append({'tool': name, 'arguments': code, 'reason': reason})
                continue
            # Legacy wrapper audit remains unchanged. Only proven forms can own a pollable session.
            calls[call_id] = ('wrapper' if wrapper_origin(code, root, metadata['run_id']) else 'unproven', None)
        elif kind in {'function_call_output', 'custom_tool_call_output'}:
            origin_kind, session_id = calls.get(call_id, (None, None))
            if origin_kind not in {'wrapper', 'poll'}:
                continue
            results = list(result_objects(payload))
            if origin_kind == 'poll' and (len(results) != 1 or
                    not ('output' in results[0] and 'wall_time_seconds' in results[0]) or
                    not (type(results[0].get('exit_code')) is int or results[0].get('session_id') == session_id)):
                violations.append({'tool': 'write_stdin', 'reason': 'poll output provenance unavailable'})
                continue
            for result in results:
                returned = result.get('session_id')
                if (origin_kind == 'wrapper' and len(results) == 1 and type(returned) is int and returned > 0
                        and 'output' in result and 'wall_time_seconds' in result and 'exit_code' not in result):
                    owned[returned] = call_id
                if origin_kind == 'poll':
                    if returned is not None and returned != session_id:
                        violations.append({'tool': 'write_stdin', 'reason': 'poll returned a different session'})
                    if type(result.get('exit_code')) is int:
                        owned.pop(session_id, None)
    return violations, polls
