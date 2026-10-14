"""Frozen-registration-gated literal shell wrapper presentation compatibility.

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
import collect
import transport
from prepare import ROOT

VERSION = 'software-poll-presentation-v3.6.4'
MANIFEST = ROOT / 'results/frozen-software-poll-presentation-v3.6.4.json'
REQUIRED_PINS = {'tools/collect_schema_v364.py', 'tools/collect_schema_v364_probes.py', 'tools/collect_schema.py', 'tools/transport.py', 'tools/collect.py',
                 'tools/grade.py', 'tools/dialogue_control.py', 'tools/dialogue_schema.py',
                 'tools/prepare.py', 'tools/finalize.py', 'docs/spec.md',
                 'results/frozen-core-v3.6.json', 'results/frozen-native-schema-v3.6.1.json',
                 'results/frozen-escaped-template-collection-v3.6.2.json',
                 'results/frozen-software-gui-transport-v3.6.3.json',
                 'results/frozen-software-cohort-launch-v3.6.3.json',
                 'results/software-poll-presentation-revision-plan-v3.6.4.json',
                 'results/software-poll-origin-validity-review-v3.6.4.json'}
ORIGINAL_WRAPPER_ORIGIN = transport.wrapper_origin
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



def classifier_view(code):
    """Normalize two exact presentation equivalences, then approved literal escapes."""
    original = code
    count = 0
    expression = r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*'
    end = transport.OPTIONS + r'\s*\}\s*\)\s*\)\s*;?\s*'
    direct = re.fullmatch(expression + '(' + transport.STRING + ')' + end, code.strip())
    if direct:
        command = json.loads(direct.group(1))
        trimmed = command.rstrip(' \t\n')
        if trimmed != command:
            # Canonical origin validation later proves this whitespace follows the
            # closed scoped argument. Never trim the inner command or prefix.
            try:
                if shlex.split(command) != shlex.split(trimmed):
                    return original, 0
            except ValueError:
                return original, 0
            stripped = code.strip()
            code = stripped[:direct.start(1)] + json.dumps(trimmed, ensure_ascii=False) + stripped[direct.end(1):]
            count += 1
    else:
        template = TEMPLATE.fullmatch(code.strip())
        if template:
            variable = re.escape(template.group(1))
            replace_all = re.fullmatch(expression + '(' + transport.STRING + r'(?:\s*\+\s*' + transport.STRING + r')?)\s*\+\s*' + variable +
                         r'\.replaceAll\(\s*(' + transport.STRING + r')\s*,\s*(' + transport.STRING + r')\s*\)\s*\+\s*(' + transport.STRING + ')' + end,
                         template.group(3), re.S)
            if replace_all:
                search = json.loads(replace_all.group(2))
                replacement = json.loads(replace_all.group(3))
                if search != "'" or replacement != "'\\''":
                    return original, 0
                suffix = template.group(3)
                method_start = suffix.index('.replaceAll', replace_all.end(1))
                method_end = replace_all.end(3)
                # Preserve the exact replacement literal and closing syntax.
                suffix = suffix[:method_start] + ".replace(/'/g," + replace_all.group(3) + suffix[method_end:]
                stripped = code.strip()
                code = stripped[:template.start(3)] + suffix
                count += 1
    view, escaped_count = escaped_template_view(code)
    return view, count + escaped_count

def wrapper_origin(code, root, run_id):
    try:
        if ORIGINAL_WRAPPER_ORIGIN(code, root, run_id):
            return True
        view, count = classifier_view(code)
        return bool(count and ORIGINAL_WRAPPER_ORIGIN(view, root, run_id))
    except ValueError:
        return False


@contextmanager
def patched_origin():
    original = transport.wrapper_origin
    if original is not ORIGINAL_WRAPPER_ORIGIN:
        raise ValueError('Unexpected active transport classifier')
    transport.wrapper_origin = wrapper_origin
    try:
        yield
    finally:
        transport.wrapper_origin = original


def verify_registration(path=None):
    path = Path(path) if path is not None else MANIFEST
    try:
        registration = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError('Collection adapter registration unavailable') from error
    pins = registration.get('source_sha256', {})
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
                          'results/frozen-software-gui-transport-v3.6.3.json'):
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
    if (proof.get('version') != 'software-poll-presentation-original-preservation-v3.6.4'
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
    for path in native.parent.glob('collection-schema-v3.6.4-*.json'):
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
            or proof_path.name != f"collection-schema-v3.6.4-{proof['original_session_sha256']}.json"
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
    sidecar = ROOT / 'results' / run_id / f'collection-schema-v3.6.4-{source_sha}.json'
    if sidecar.exists():
        raise ValueError('Collection proof already exists for this native source')
    transforms = []
    for line in source.read_text().splitlines():
        payload = json.loads(line).get('payload', {})
        if payload.get('type') not in {'function_call', 'custom_tool_call'} or payload.get('name') not in {'functions.exec', 'exec'}:
            continue
        code = str(payload.get('arguments', payload.get('input', '')))
        view, count = classifier_view(code)
        if count and not ORIGINAL_WRAPPER_ORIGIN(code, str(ROOT), run_id) and ORIGINAL_WRAPPER_ORIGIN(view, str(ROOT), run_id):
            transforms.append({'call_id': payload.get('call_id'), 'presentation_transform_count': count,
                               'original_code_sha256': hashlib.sha256(code.encode()).hexdigest(),
                               'classifier_view_sha256': hashlib.sha256(view.encode()).hexdigest()})
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
