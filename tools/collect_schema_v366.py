"""Frozen-registration-gated String.raw and scoped prefix presentation compatibility.

Only an in-memory classifier view changes. Native source is never evaluated or
rewritten. The frozen transport auditor continues to own every provenance rule.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import collect
import copy
import collect_schema_v364 as prior
import transport
from prepare import ROOT

VERSION = 'software-raw-template-collection-v3.6.6'
MANIFEST = ROOT / 'results/frozen-software-raw-template-collection-v3.6.6.json'
REQUIRED_PINS = {'tools/collect_schema_v366.py', 'tools/collect_schema_v366_probes.py', 'tools/collect_schema.py', 'tools/transport.py', 'tools/collect.py',
                 'tools/grade.py', 'tools/dialogue_control.py', 'tools/dialogue_schema.py',
                 'tools/prepare.py', 'tools/finalize.py', 'docs/spec.md',
                 'results/frozen-core-v3.6.json', 'results/frozen-native-schema-v3.6.1.json',
                 'results/frozen-escaped-template-collection-v3.6.2.json',
                 'results/frozen-software-gui-transport-v3.6.3.json',
                 'results/frozen-software-cohort-launch-v3.6.3.json',
                 'results/software-raw-template-revision-plan-v3.6.6.json',
                 'results/software-raw-template-origin-review-v3.6.6.json'}
REQUIRED_PINS |= {'tools/collect_schema_v364.py', 'tools/collect_schema_v364_probes.py',
                  'results/frozen-software-poll-presentation-v3.6.4.json',
                  'results/software-raw-template-independent-review-v3.6.6.json',
                  'results/software-raw-template-qualification-v3.6.6.json'}
ORIGINAL_WRAPPER_ORIGIN = transport.wrapper_origin
ORIGINAL_AUDIT = transport.audit_transport
ORIGINAL_COLLECT_AUDIT = collect.audit_transport
TEMPLATE = re.compile(r'const\s+(\w+)\s*=\s*`((?:\\.|[^`\\])*)`\s*;\s*(.*)', re.S)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def escaped_template_view(code):
    """Convert odd-backslash escaped dollars in only the initial template body."""
    match = TEMPLATE.fullmatch(code.strip())
    if not match:
        return code, 0
    body = match.group(2)
    count = 0
    pieces = []
    cursor = 0
    for interpolation in re.finditer(r'\$\{', body):
        position = interpolation.start()
        backslashes = 0
        while position - backslashes > 0 and body[position - backslashes - 1] == '\\':
            backslashes += 1
        if backslashes % 2 == 0:
            return code, 0
        # Consume the final escape slash, retaining paired slashes before it.
        pieces.append(body[cursor:position - 1] + r'\u0024{')
        cursor = interpolation.end()
        count += 1
    if not count:
        return code, 0
    pieces.append(body[cursor:])
    stripped = code.strip()
    return stripped[:match.start(2)] + ''.join(pieces) + stripped[match.end(2):], count



RAW_TEMPLATE = re.compile(r'const\s+([A-Za-z_$][\w$]*)\s*=\s*String\.raw`((?:\\[\s\S]|[^`\\])*)`\s*;\s*(.*)', re.S)


def raw_template_view(code, root, run_id, saved_prefix=None):
    """Static raw literal + exact scoped prefix. Never evaluate JavaScript.

    String.raw retains every escape slash, escaped backtick and escaped dollar.
    JS normalizes literal CR/CRLF to LF even for raw template strings.
    Only the one no-substitution tagged template and exact shell quote operation
    are admitted. A prior prefix is local to this chronological audit invocation.
    """
    prefix = f"python3 {root}/tools/agent_io.py --run {run_id} --cmd "
    direct = re.fullmatch(r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*load\(\s*"prefix"\s*\)\s*\+\s*(' + transport.STRING + ')' + transport.OPTIONS + r'\s*\}\s*\)\s*\)\s*;?\s*', code.strip())
    if direct and saved_prefix == prefix:
        host = prefix + json.loads(direct.group(1))
        view = 'text(await tools.exec_command({cmd:' + json.dumps(host, ensure_ascii=False) + '}));'
        if ORIGINAL_WRAPPER_ORIGIN(view, root, run_id):
            raw = shlex.split(host)[-1]
            return view, {'raw_literal_sha256': hashlib.sha256(raw.encode()).hexdigest(),
                          'raw_literal': raw, 'exact_six_scoped_host_argv': shlex.split(host),
                          'prefix_store_in_call': False, 'prefix_load_in_call': True,
                          'literal_family': 'direct-json-suffix'}, saved_prefix
    match = RAW_TEMPLATE.fullmatch(code.strip())
    if not match:
        return code, None, saved_prefix
    body = match.group(2)
    for dollar in re.finditer(r'\$\{', body):
        pos = dollar.start(); slashes = 0
        while pos > slashes and body[pos - slashes - 1] == "\\": slashes += 1
        if slashes % 2 == 0:
            return code, None, None
    raw = body.replace('\r\n', '\n').replace('\r', '\n')
    rest = match.group(3)
    prefix = f"python3 {root}/tools/agent_io.py --run {run_id} --cmd "
    stored = re.match(r'store\(\s*("(?:\\.|[^"\\])*")\s*,\s*("(?:\\.|[^"\\])*")\s*\)\s*;\s*', rest)
    store_seen = False
    if stored:
        if json.loads(stored.group(1)) != 'prefix' or json.loads(stored.group(2)) != prefix:
            return code, None, None
        saved_prefix = prefix; store_seen = True; rest = rest[stored.end():]
    expression = r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*'
    end = transport.OPTIONS + r'\s*\}\s*\)\s*\)\s*;?\s*'
    first = r'(?:(?:' + transport.STRING + r')(?:\s*\+\s*' + transport.STRING + r')?|load\(\s*"prefix"\s*\)\s*\+\s*' + transport.STRING + r')'
    method = r"(?:\.replace\(\s*/'/g\s*,|\.replaceAll\(\s*\"'\"\s*,)"
    call = re.fullmatch(expression + '(' + first + r')\s*\+\s*' + re.escape(match.group(1)) + method + r'\s*(' + transport.STRING + r')\s*\)\s*\+\s*(' + transport.STRING + ')' + end, rest, re.S)
    if not call:
        return code, None, None
    lead = call.group(1)
    loads = lead.startswith('load')
    if loads and saved_prefix != prefix:
        return code, None, None
    literals = [json.loads(m.group()) for m in re.finditer(transport.STRING, lead)]
    host_prefix = saved_prefix + literals[-1] if loads else ''.join(literals)
    replacement, suffix = json.loads(call.group(2)), json.loads(call.group(3))
    if host_prefix != prefix + "'" or replacement != "'\\''" or suffix != "'":
        return code, None, None
    host = host_prefix + raw.replace("'", replacement) + suffix
    view = 'text(await tools.exec_command({cmd:' + json.dumps(host, ensure_ascii=False) + '}));'
    if not ORIGINAL_WRAPPER_ORIGIN(view, root, run_id):
        return code, None, None
    proof = {'raw_literal_sha256': hashlib.sha256(raw.encode()).hexdigest(),
             'raw_literal': raw, 'exact_six_scoped_host_argv': shlex.split(host),
             'prefix_store_in_call': store_seen, 'prefix_load_in_call': loads,
             'literal_family': 'String.raw-no-substitution'}
    return view, proof, saved_prefix


def classifier_view(code):
    # Context-free compatibility remains exactly the frozen v364 behavior.
    return prior.classifier_view(code)


def wrapper_origin(code, root, run_id):
    return prior.wrapper_origin(code, root, run_id)


PARSER_RUNTIME = {
    'path': '/Users/junhyounglee/.hermes/node/bin/node',
    'sha256': '18e387c90ab8a8400183e8bdd396376e1e875b91b4c874b894dcade7b35bf572',
    'version': 'v22.23.2',
    'arguments': ['--input-type=module', '--check'],
}


def verify_parser_runtime():
    path = Path(PARSER_RUNTIME['path'])
    if not path.is_absolute() or digest(path) != PARSER_RUNTIME['sha256']:
        raise ValueError('Frozen parse-only runtime binary changed')
    result = subprocess.run([str(path), '--version'], capture_output=True, text=True, timeout=5)
    if result.returncode != 0 or result.stdout.strip() != PARSER_RUNTIME['version']:
        raise ValueError('Frozen parse-only runtime version changed')
    return dict(PARSER_RUNTIME)


def compile_failure_candidate(code, root, run_id, saved):
    """Bounded wrapper shape plus independent compile rejection, without execution."""
    prefix = f'python3 {root}/tools/agent_io.py --run {run_id} --cmd '
    if saved != prefix:
        return None
    initial = re.match(r'const\s+([A-Za-z_$][\w$]*)\s*=\s*String\.raw`', code.strip())
    if not initial:
        return None
    # The first and last delimiters bound only a candidate. Parse rejection is
    # mandatory because inner unescaped delimiters cannot establish a JS literal.
    closing = code.strip().rfind('`')
    if closing < initial.end():
        return None
    suffix = code.strip()[closing + 1:]
    projected = code.strip()[:initial.end()] + 'compile_failure' + '`' + suffix
    _, wrapper, _ = raw_template_view(projected, root, run_id, saved)
    if (not wrapper or wrapper['prefix_store_in_call'] or not wrapper['prefix_load_in_call']
            or re.findall(r'\btools\.([A-Za-z_$][\w$]*)', code) != ['exec_command']
            or len(re.findall(r'\btools\b', code)) != 1
            or re.search(r'(?<![\w.])(?:store|eval|Function)\s*\(|(?:globalThis|Reflect)\s*[.\[]', code)
            or len(re.findall(r'(?<![\w.])load\s*\(', code)) != 1):
        return None
    parser = verify_parser_runtime()
    result = subprocess.run([parser['path'], *parser['arguments']], input=code,
                            capture_output=True, text=True, timeout=5)
    if result.returncode != 1 or 'SyntaxError:' not in result.stderr or result.stdout:
        return None
    return {'parser': {**parser, 'exit_code': result.returncode, 'stderr': result.stderr,
                       'execution': False},
            'code_sha256': hashlib.sha256(code.encode()).hexdigest(),
            'successful': False, 'command_executed': False, 'owned_session_id': None}


def authenticated_compile_failure(payload):
    output = payload.get('output')
    return (isinstance(output, list) and len(output) == 2
            and all(isinstance(p, dict) and set(p) == {'type', 'text'}
                    and p['type'] == 'input_text' and isinstance(p['text'], str) for p in output)
            and re.fullmatch(r'Script failed\nWall time 0(?:\.0+)? seconds\nOutput:\n', output[0]['text']) is not None
            and re.fullmatch(r'Script error:\nSyntaxError: [^\n]+', output[1]['text']) is not None
            and not list(transport.result_objects(payload)))


def classifier_events(events, metadata, root, unsuccessful_tool_attempts=None):
    """Copy public records, preserving proven compile failures separately."""
    copied = copy.deepcopy(events); saved = None; pending = None; proofs = []
    pending_compile = None; omitted = set(); unresolved = set()
    counts = {}
    for event in copied:
        payload = event.get('payload', {})
        if payload.get('type') in {'function_call', 'custom_tool_call', 'function_call_output', 'custom_tool_call_output'}:
            identity = (payload.get('call_id'), payload.get('type') in {'function_call_output', 'custom_tool_call_output'})
            counts[identity] = counts.get(identity, 0) + 1
    for index, event in enumerate(copied):
        payload = event.get('payload', {}); kind = payload.get('type'); cid = payload.get('call_id')
        if kind not in {'function_call', 'custom_tool_call', 'function_call_output', 'custom_tool_call_output'}:
            continue
        prior_unresolved = bool(unresolved)
        if kind in {'function_call', 'custom_tool_call'}:
            unresolved.add(cid)
        else:
            unresolved.discard(cid)
        if pending_compile:
            failed_id, prior_prefix, prior_index, failed_proof = pending_compile
            pending_compile = None
            if (kind in {'function_call_output', 'custom_tool_call_output'} and cid == failed_id
                    and counts.get((cid, False)) == counts.get((cid, True)) == 1
                    and authenticated_compile_failure(payload)):
                saved = prior_prefix; omitted.update({prior_index, index})
                if unsuccessful_tool_attempts is not None:
                    unsuccessful_tool_attempts.append({'call_id': cid, **failed_proof,
                        'authenticated_output': copy.deepcopy(payload['output']),
                        'output_sha256': hashlib.sha256(json.dumps(payload['output'], sort_keys=True).encode()).hexdigest(),
                        'prefix_state_preserved': True, 'original_native_records_mutated': False})
                continue
            saved = None
        if kind in {'function_call_output', 'custom_tool_call_output'}:
            if pending and cid == pending[0]:
                results = list(transport.result_objects(payload))
                if (len(results) == 1 and 'output' in results[0] and 'wall_time_seconds' in results[0]
                        and (type(results[0].get('exit_code')) is int or
                             type(results[0].get('session_id')) is int and results[0]['session_id'] > 0)):
                    saved = pending[1]
                pending = None
            continue
        code = str(payload.get('arguments', payload.get('input', '')))
        if payload.get('name') not in {'exec', 'functions.exec'}:
            saved = None; pending = None; continue
        view, proof, candidate = raw_template_view(code, root, metadata['run_id'], saved)
        if proof:
            key = 'arguments' if 'arguments' in payload else 'input'
            payload[key] = view
            proofs.append({'call_id': cid, **proof,
                           'original_code_sha256': hashlib.sha256(code.encode()).hexdigest(),
                           'classifier_view_sha256': hashlib.sha256(view.encode()).hexdigest()})
            if proof['prefix_store_in_call']:
                saved = None; pending = (cid, candidate)
        elif not (prior.wrapper_origin(code, root, metadata['run_id'])
                  or transport.poll_options(code) is not None
                  or code.strip() == metadata.get('bootstrap_code')):
            failed = compile_failure_candidate(code, root, metadata['run_id'], saved) if not pending and not prior_unresolved else None
            if failed:
                pending_compile = (cid, saved, index, failed)
            saved = None; pending = None
    return [e for i, e in enumerate(copied) if i not in omitted], proofs


def audit_transport(events, metadata, root):
    view, _ = classifier_events(events, metadata, root)
    violations, polls = ORIGINAL_AUDIT(view, metadata, root)
    originals = {e.get('payload', {}).get('call_id'): e.get('payload', {}) for e in events
                 if e.get('payload', {}).get('type') in {'function_call', 'custom_tool_call'}}
    replacements = {str(e['payload'].get('arguments', e['payload'].get('input', ''))):
                    str(originals[e['payload'].get('call_id')].get('arguments', originals[e['payload'].get('call_id')].get('input', '')))
                    for e in view if e.get('payload', {}).get('type') in {'function_call', 'custom_tool_call'}}
    for violation in violations:
        if 'arguments' in violation:
            violation['arguments'] = replacements.get(violation['arguments'], violation['arguments'])
    return violations, polls


@contextmanager
def patched_origin():
    original = transport.wrapper_origin
    if (original is not ORIGINAL_WRAPPER_ORIGIN or transport.audit_transport is not ORIGINAL_AUDIT
            or collect.audit_transport is not ORIGINAL_COLLECT_AUDIT):
        raise ValueError('Unexpected active transport classifier')
    transport.wrapper_origin = wrapper_origin
    transport.audit_transport = audit_transport
    collect.audit_transport = audit_transport
    try:
        yield
    finally:
        transport.wrapper_origin = original
        transport.audit_transport = ORIGINAL_AUDIT
        collect.audit_transport = ORIGINAL_COLLECT_AUDIT


def verify_registration(path=None):
    path = Path(path) if path is not None else MANIFEST
    try:
        registration = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError('Collection adapter registration unavailable') from error
    pins = registration.get('source_sha256', {})
    if registration.get('parser_runtime') != PARSER_RUNTIME:
        raise ValueError('Collection adapter parse-only runtime is not preregistered')
    verify_parser_runtime()
    if (registration.get('version') != VERSION or registration.get('status') != 'frozen'
            or registration.get('actor_reexecution_allowed') is not False
            or not isinstance(pins, dict) or not REQUIRED_PINS <= set(pins)):
        raise ValueError('Collection adapter is not completely preregistered')
    for name, expected in pins.items():
        if digest(ROOT / name) != expected:
            raise ValueError('Registered collection source changed: ' + name)
    core = json.loads((ROOT / 'results/frozen-core-v3.6.json').read_text())
    if core.get('core_version') != 'v3.6' or core.get('freeze_revision') != 2:
        raise ValueError('Collection adapter requires unchanged v3.6 revision 2')
    for name, expected in core['grader_hashes'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Frozen evaluation source changed: ' + name)
    native = json.loads((ROOT / 'results/frozen-native-schema-v3.6.1.json').read_text())
    if native.get('version') != 'native-content-v1' or native.get('status') != 'frozen':
        raise ValueError('Native schema registration is not frozen')
    for name, expected in native['source_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Native schema source changed: ' + name)
    for manifest_name in ('results/frozen-escaped-template-collection-v3.6.2.json',
                          'results/frozen-software-gui-transport-v3.6.3.json',
                          'results/frozen-software-poll-presentation-v3.6.4.json'):
        frozen = json.loads((ROOT / manifest_name).read_text())
        if frozen.get('status') != 'frozen':raise ValueError('Prior operational registration is not frozen')
        for name, expected in frozen['source_sha256'].items():
            if digest(ROOT / name) != expected:raise ValueError('Prior operational source changed: ' + name)
    return registration


def prior_files(run_id):
    names = [f'results/{run_id}/{name}' for name in ('native-tools.jsonl', 'manifest.json', 'turns.json')]
    metadata = ROOT / 'runtime' / run_id / 'run.json'
    existing = [name for name in names if (ROOT / name).exists()]
    if existing or (metadata.exists() and json.loads(metadata.read_text()).get('turns')):
        existing.append(f'runtime/{run_id}/run.json')
    return existing


def verify_preservation(run_id, registration, explicit=None):
    files = prior_files(run_id)
    if not files:
        return None
    registered = registration.get('prior_preservation', {}).get(run_id, {})
    path = Path(explicit) if explicit else Path(registered.get('path', ''))
    if not path.is_file():
        raise ValueError('Existing collection requires registered prior preservation')
    if registered.get('path') != str(path) or registered.get('sha256') != digest(path):
        raise ValueError('Prior preservation must be pinned in frozen registration')
    proof = json.loads(path.read_text())
    if (proof.get('version') != 'raw-template-original-preservation-v3.6.6'
            or proof.get('status') != 'preserved' or proof.get('run_id') != run_id
            or proof.get('adapter_sha256') != digest(Path(__file__))):
        raise ValueError('Prior preservation identity/source pin mismatch')
    for name in files:
        record = proof.get('files', {}).get(name, {})
        saved = Path(record.get('preserved_path', ''))
        if (not saved.is_file() or saved.resolve() == (ROOT / name).resolve()
                or record.get('sha256') != digest(ROOT / name)
                or digest(saved) != record.get('sha256')):
            raise ValueError('Unpreserved collection file: ' + name)
    return {'path': str(path), 'sha256': digest(path)}


def append_qualification(run_id, source, request, agent_path):
    """Recognize one new terminal over an exact preserved native prefix."""
    native = ROOT / 'results' / run_id / 'native-tools.jsonl'
    if not request or not native.exists():
        return None
    proofs = []
    for path in native.parent.glob('collection-schema-v3.6.6-*.json'):
        try:
            proof = json.loads(path.read_text())
        except (OSError, ValueError):
            return None
        if proof.get('original_native_sha256') == digest(native):
            proofs.append((path, proof))
    if len(proofs) != 1:
        return None
    proof_path, proof = proofs[0]
    source_bytes = source.read_bytes()
    prefix_size = proof.get('original_session_bytes')
    if (proof.get('version') != VERSION or proof.get('run_id') != run_id
            or proof.get('adapter_sha256') != digest(Path(__file__))
            or not MANIFEST.is_file() or proof.get('registration_sha256') != digest(MANIFEST)
            or proof.get('original_session_path') != str(source.resolve())
            or proof.get('agent_path') != agent_path
            or type(prefix_size) is not int or not 0 < prefix_size < len(source_bytes)
            or not isinstance(proof.get('original_session_sha256'), str)
            or proof_path.name != f"collection-schema-v3.6.6-{proof['original_session_sha256']}.json"
            or hashlib.sha256(source_bytes[:prefix_size]).hexdigest() != proof['original_session_sha256']):
        return None
    # This checks append identity only. Frozen dialogue/control attestation still
    # verifies coordinator dispatch, incoming message token, staging and receipt.
    # The encrypted incoming body is never decrypted or inspected here.
    prefix_events = [json.loads(line) for line in source_bytes[:prefix_size].decode().splitlines()]
    appended = [json.loads(line) for line in source_bytes[prefix_size:].decode().splitlines()]
    contexts = [(i, e['payload']) for i, e in enumerate(appended) if e.get('type') == 'turn_context']
    started = [(i, e['payload']) for i, e in enumerate(appended)
               if e.get('type') == 'event_msg' and e.get('payload', {}).get('type') == 'task_started']
    completed = [(i, e['payload']) for i, e in enumerate(appended)
                 if e.get('type') == 'event_msg' and e.get('payload', {}).get('type') == 'task_complete']
    incoming = [(i, e['payload']) for i, e in enumerate(appended)
                if e.get('type') == 'response_item' and e.get('payload', {}).get('type') == 'agent_message']
    terminal = [(i, e['payload']) for i, e in enumerate(appended)
                if e.get('type') == 'response_item' and e.get('payload', {}).get('type') == 'message'
                and e['payload'].get('role') == 'assistant'
                and (e['payload'].get('channel') == 'final' or e['payload'].get('phase') == 'final_answer')]
    if any(len(items) != 1 for items in (contexts, started, completed, incoming, terminal)):
        return None
    context_i, context = contexts[0]
    started_i, start = started[0]
    completed_i, completion = completed[0]
    incoming_i, message = incoming[0]
    terminal_i, final = terminal[0]
    turn_id = context.get('turn_id')
    prior_ids = {e['payload'].get('turn_id') for e in prefix_events
                 if e.get('type') == 'event_msg' and e.get('payload', {}).get('type') == 'task_complete'}
    if (not isinstance(turn_id, str) or not turn_id or turn_id in prior_ids
            or start.get('turn_id') != turn_id or completion.get('turn_id') != turn_id
            or context.get('model') != 'gpt-6.1-sol' or context.get('effort') != 'medium'
            or message.get('recipient') != agent_path or message.get('author') != agent_path.rsplit('/', 1)[0]
            or message.get('internal_chat_message_metadata_passthrough', {}).get('turn_id') != turn_id
            or not started_i < context_i < incoming_i < terminal_i < completed_i):
        return None
    old = [json.loads(line) for line in native.read_text().splitlines()]
    events = [json.loads(line) for line in source.read_text().splitlines()]
    evidence = []
    completions_after_old = []
    for event in events:
        payload = event.get('payload', {})
        if event.get('type') == 'response_item':
            typ = payload.get('type')
            if typ in {'function_call', 'function_call_output', 'custom_tool_call', 'custom_tool_call_output'}:
                evidence.append(event)
            elif (typ == 'message' and payload.get('role') == 'assistant'
                    and (payload.get('channel') == 'final' or payload.get('phase') == 'final_answer')
                    and any(c.get('type') == 'output_text' and c.get('text') for c in payload.get('content', []))):
                evidence.append(event)
        if (event.get('type') == 'event_msg' and payload.get('type') == 'task_complete'
                and len(evidence) > len(old)):
            completions_after_old.append(payload)
    if not old or evidence[:len(old)] != old:
        return None
    additions = evidence[len(old):]
    finals = [e for e in additions if e['payload'].get('type') == 'message']
    metadata = json.loads((ROOT / 'runtime' / run_id / 'run.json').read_text())
    turns = metadata.get('turns', [])
    if (len(finals) != 1 or len(completions_after_old) != 1 or not turns
            or turns[-1].get('request') == request):
        return None
    new_final = '\n'.join(c.get('text', '') for c in finals[0]['payload'].get('content', []) if c.get('type') == 'output_text')
    saved_turns = json.loads((ROOT / 'results' / run_id / 'turns.json').read_text())
    if saved_turns != turns:
        raise ValueError('Prior turn snapshots disagree')
    return {'prior_native_sha256': digest(native), 'prior_native_events': len(old), 'prior_proof_sha256': digest(proof_path),
            'append_turn_id': turn_id, 'incoming_identity_verified': True, 'control_attestation_replaced': False,
            'prior_session_bytes': prefix_size, 'prior_session_sha256': proof['original_session_sha256'],
            'prior_turns': turns, 'new_terminal_count': 1, 'new_completion_count': 1}


def qualified_collect(run_id, agent_path, request=None, *, preservation=None):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise ValueError('Invalid run identifier')
    registration = verify_registration()
    source = collect.find_session(agent_path)
    source_sha = digest(source)
    append = append_qualification(run_id, source, request, agent_path)
    previous = None if append else verify_preservation(run_id, registration, preservation)
    sidecar = ROOT / 'results' / run_id / f'collection-schema-v3.6.6-{source_sha}.json'
    if sidecar.exists():
        raise ValueError('Collection proof already exists for this native source')
    # Extract public tool calls/results only, never private reasoning content.
    source_events = []
    for line in source.read_text().splitlines():
        event = json.loads(line); payload = event.get('payload', {})
        if event.get('type') == 'response_item' and payload.get('type') in {
                'function_call', 'custom_tool_call', 'function_call_output', 'custom_tool_call_output'}:
            source_events.append(event)
    failed_attempts = []
    _, transforms = classifier_events(source_events, {'run_id': run_id}, str(ROOT), failed_attempts)
    transforms = [{k: v for k, v in p.items() if k not in {'raw_literal', 'exact_six_scoped_host_argv'}} for p in transforms]
    with patched_origin():
        result = collect.collect(run_id, agent_path, request)
    if append:
        current = json.loads((ROOT / 'results' / run_id / 'turns.json').read_text())
        if len(current) != len(append['prior_turns']) + 1 or current[:-1] != append['prior_turns']:
            raise ValueError('Normal append modified an immutable prior turn snapshot')
    if digest(source) != source_sha:
        raise ValueError('Native source changed during collection')
    native_path = ROOT / 'results' / run_id / 'native-tools.jsonl'
    proof = {'version': VERSION, 'run_id': run_id, 'adapter_sha256': digest(Path(__file__)),
             'registration_sha256': digest(MANIFEST), 'original_session_sha256': source_sha,
             'original_session_bytes': source.stat().st_size, 'original_session_path': str(source.resolve()),
             'agent_path': agent_path,
             'original_native_sha256': digest(native_path), 'classifier_view_transforms': transforms,
             'source_unmutated': True, 'original_native_records_mutated': False,
             'unsuccessful_tool_attempts': failed_attempts, 'parser_runtime': dict(PARSER_RUNTIME),
             'actor_reexecuted': False, 'prior_preservation': previous,
             'normal_append': {k: v for k, v in append.items() if k != 'prior_turns'} if append else None}
    sidecar.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n')
    return {**result, 'collection_adapter_proof': {'path': str(sidecar), 'sha256': digest(sidecar)}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run'); parser.add_argument('agent_path'); parser.add_argument('--request')
    parser.add_argument('--preservation')
    args = parser.parse_args()
    print(json.dumps(qualified_collect(args.run, args.agent_path, args.request, preservation=args.preservation), ensure_ascii=False))
