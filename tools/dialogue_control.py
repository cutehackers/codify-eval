"""Stage and attest a fixed public request through a read-only container file.

No model dispatch or retry. Commands and native receipt must qualify before grading.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time

from collect import find_session, SESSION_ROOT
from prepare import ROOT, case_directory, tree_hash
from transport import STRING, OPTIONS, poll_options, result_objects

PROTOCOL = 'controlled-file-v1'
INPUT_PATH = '/eval-input/turn-2.txt'
READ_COMMAND = 'cat ' + INPUT_PATH
FOLLOWUP = (
    'The next user request is in /eval-input/turn-2.txt. '
    'Execute exactly cat /eval-input/turn-2.txt through your existing permitted '
    'container command interface. Treat its full contents as the user request '
    'and follow it in this same session. The file is read-only. '
    'Do not use another host read, change the file, or ask for approval to read it.'
)


class ControlFault(ValueError):
    def __init__(self, status, category, message):
        super().__init__(message)
        self.audit = {'status': status, 'category': category, 'error': message,
                      'protocol': PROTOCOL}


def followup(run_id):
    command = shlex.join(['python3', str(ROOT / 'tools/agent_io.py'), '--run', run_id,
                          '--cmd', READ_COMMAND])
    code = 'text(await tools.exec_command(' + json.dumps(
        {'cmd': command, 'max_output_tokens': 2000}) + '));'
    return FOLLOWUP + '\nUse this exact read call:\n' + code


def run_directory(run_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id):
        raise ValueError('Invalid run identifier')
    directory = ROOT / 'runtime' / run_id
    if directory.is_symlink() or directory.resolve().parent != (ROOT / 'runtime').resolve():
        raise ValueError('Run directory must be an owned direct runtime child')
    return directory


def qualify_preparation(run_id, run):
    if run.get('run_id') != run_id:
        raise ValueError('Run metadata identity mismatch')
    protocol = run.get('dialogue_protocol', {})
    metadata = case_directory(run['case_id']) / 'metadata.json'
    expected = expected_input(read(metadata), source_selector(read(metadata)))
    identities = {'protocol': PROTOCOL, 'selector': source_selector(read(metadata)),
                  'source_metadata': str(metadata),
                  'source_metadata_sha256': digest(metadata.read_bytes()),
                  'input_sha256': digest(expected), 'container_input_path': INPUT_PATH,
                  'read_command': READ_COMMAND,
                  'followup_sha256': digest(followup(run_id).encode())}
    if any(protocol.get(key) != value for key, value in identities.items()):
        raise ValueError('Prepared controlled protocol/source identity mismatch')
    for name, sha in protocol.get('tool_hashes', {}).items():
        if digest((ROOT / name).read_bytes()) != sha:
            raise ValueError('Prepared control tool changed: ' + name)
    if set(protocol.get('tool_hashes', {})) != {'tools/dialogue_control.py', 'tools/grade.py'}:
        raise ValueError('Missing prepared control-tool pins')
    if not run.get('phase', '').startswith('control-probe'):
        if run.get('phase') not in {'primary', 'auxiliary', 'software', 'heldout'}:
            raise ValueError('Unknown comparison phase')
        core_path = ROOT / 'results/frozen-core-v3.6.json'
        core = run.get('evaluation_core', {})
        if core.get('path') != str(core_path) or core.get('sha256') != digest(core_path.read_bytes()):
            raise ValueError('Run is not bound to the preregistered controlled protocol core')
        pins = read(core_path)['grader_hashes']
        for filename in ['tools/dialogue_control.py', 'tools/prepare.py', 'tools/grade.py']:
            if pins.get(filename) != digest((ROOT / filename).read_bytes()):
                raise ValueError('Controlled protocol differs from frozen core')
        if run['case_id'] == 'S03':
            cohort_path = ROOT / 'results/controlled-dialogue-cohort-v3.6.json'
            cohort = protocol.get('cohort', {})
            if cohort.get('path') != str(cohort_path) or cohort.get('sha256') != digest(cohort_path.read_bytes()):
                raise ValueError('S03 run is not bound to the preregistered whole cohort')
            members = [row for row in read(cohort_path)['runs'] if row['run_id'] == run_id]
            if len(members) != 1 or any(members[0].get(key) != run.get(key)
                                      for key in ['case_id', 'condition', 'repeat', 'phase']):
                raise ValueError('Run is not a preregistered S03 cohort member')
    return protocol


def followup_evidence(events, raw_prefix_bytes, run, staging):
    meta = events[0]['payload']
    spawn = meta['source']['subagent']['thread_spawn']
    parent_id = spawn['parent_thread_id']
    parents = list(SESSION_ROOT.rglob('*-' + parent_id + '.jsonl'))
    if len(parents) != 1:
        raise ValueError('Ambiguous actual coordinator native source')
    parent_raw = parents[0].read_bytes()
    parent_events = [json.loads(line) for line in parent_raw.decode().splitlines()]
    actor_path = run['agent_path']
    parent_path = actor_path.rsplit('/', 1)[0]
    incoming = [(i, e) for i, e in enumerate(events)
                if e.get('payload', {}).get('type') == 'agent_message']
    contexts = [(i, e) for i, e in enumerate(events) if e['type'] == 'turn_context']
    completions = [(i, e) for i, e in enumerate(events)
                   if e.get('payload', {}).get('type') == 'task_complete']
    if len(incoming) != 2 or len(contexts) != 2 or len(completions) != 2:
        raise ValueError('Expected exactly two messages, contexts and completed turns')
    for turn in range(2):
        context_i, context = contexts[turn]
        message_i, message = incoming[turn]
        complete_i, complete = completions[turn]
        message = message['payload']
        turn_id = context['payload'].get('turn_id')
        if not turn_id or message.get('recipient') != actor_path or message.get('author') != parent_path:
            raise ValueError('Incorrect native message author/recipient')
        if message.get('internal_chat_message_metadata_passthrough', {}).get('turn_id') != turn_id:
            raise ValueError('Native incoming message belongs to another turn')
        if complete['payload'].get('turn_id') != turn_id or not context_i < message_i < complete_i:
            raise ValueError('Native message/context/completion order mismatch')
        boundary = contexts[turn + 1][0] if turn == 0 else len(events)
        finals = []
        for event in events[message_i + 1:boundary]:
            payload = event.get('payload', {})
            if payload.get('type') == 'message' and payload.get('role') == 'assistant' and (
                    payload.get('channel') == 'final' or payload.get('phase') == 'final_answer'):
                finals.append('\n'.join(c.get('text', '') for c in payload.get('content', [])
                                        if c.get('type') == 'output_text'))
        if finals != [run['turns'][turn]['final']]:
            raise ValueError('Native final does not match its collected turn')
    if not completions[0][0] < contexts[1][0]:
        raise ValueError('Followup preceded the actual first terminal')
    second = incoming[1][1]
    # Byte prefix already qualifies the preserved first source; require second context
    # to be outside it using actual original line boundaries, not reserialized JSON.
    if contexts[1][0] < len(raw_prefix_bytes.decode().splitlines()):
        raise ValueError('Second turn was already present before staging')
    token = second['payload'].get('message')
    calls, returns = [], {}
    for event in parent_events:
        payload = event.get('payload', {})
        if payload.get('type') == 'function_call' and payload.get('name', '').split('.')[-1] == 'followup_task':
            args = payload.get('arguments', {})
            args = json.loads(args) if isinstance(args, str) else args
            target = args.get('target')
            if target in {actor_path, actor_path.rsplit('/', 1)[-1]}:
                calls.append((event, args))
        if payload.get('type') == 'function_call_output':
            returns[payload.get('call_id')] = event
    if len(calls) != 1:
        raise ValueError('Expected exactly one coordinator followup dispatch')
    call, args = calls[0]
    returned = returns.get(call['payload']['call_id'])
    if returned is None or returned['payload'].get('output') != '':
        raise ValueError('Followup tool did not return its actual normal success receipt')
    if not isinstance(token, str) or args.get('message') != token:
        raise ValueError('Parent followup token does not match child incoming message')
    if not completions[0][1]['timestamp'] < call['timestamp'] <= second['timestamp'] <= returned['timestamp']:
        raise ValueError('Followup dispatch/receipt is out of order')
    if datetime.fromisoformat(call['timestamp'].replace('Z', '+00:00')).timestamp() < staging['staged_at']:
        raise ValueError('Followup was dispatched before staging')
    if [e['payload'].get('turn_id') for _, e in completions] != [
            e.get('turn_id') for e in run.get('completion_evidence', [])]:
        raise ValueError('Collected completion identities differ from native turns')
    if staging.get('first_completion') != {k: completions[0][1]['payload'].get(k)
                                           for k in ('turn_id', 'started_at', 'completed_at', 'duration_ms')}:
        raise ValueError('Preserved first completion changed')
    encrypted = token.startswith('gAAAAA')
    if not encrypted and token != followup(run['run_id']):
        raise ValueError('Readable native followup differs from frozen ASCII request')
    return {'parent_source': str(parents[0]), 'parent_source_prefix_bytes': len(parent_raw),
            'parent_source_prefix_sha256': digest(parent_raw),
            'successful_followup_call_id': call['payload']['call_id'],
            'native_message_sha256': digest(token.encode()),
            'native_followup_plaintext_verified': not encrypted,
            'same_session_delivery_verified': True,
            'second_turn_context_index': contexts[1][0],
            'second_turn_message_index': incoming[1][0],
            'second_turn_completion_index': completions[1][0]}


def read(path):
    return json.loads(path.read_text())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def expected_input(case, selector):
    parts = selector.split(':')
    if len(parts) == 2 and parts[0] == 'turn_requests':
        value = case['turn_requests'][int(parts[1])]
        if int(parts[1]) != 1:
            raise ValueError('Only the current second-turn input is supported')
    elif len(parts) == 3 and parts[0] == 'decision_rules' and parts[2] in {'reply', 'choice'}:
        if int(parts[1]) < 0:
            raise ValueError('Negative source indexes are not allowed')
        value = case['decision_rules'][int(parts[1])][parts[2]]
    else:
        raise ValueError('Input must be selected from frozen public metadata')
    if not isinstance(value, str) or not value:
        raise ValueError('Expected a nonempty fixed public reply')
    data = value.encode('utf-8')
    if b'\r' in data or data.startswith(b'\xef\xbb\xbf'):
        raise ValueError('Controlled input supports UTF-8 without CR or BOM')
    return data


def source_selector(case):
    if len(case.get('turn_requests', [])) > 1:
        return 'turn_requests:1'
    rules = case.get('decision_rules', [])
    if isinstance(rules, list) and rules:
        if isinstance(rules[0].get('reply'), str):
            return 'decision_rules:0:reply'
        if isinstance(rules[0].get('choice'), str):
            return 'decision_rules:0:choice'
    raise ValueError('No fixed second-turn source')


def container_evidence(run, directory):
    result = subprocess.run(['docker', 'inspect', run['container']], check=True,
                            capture_output=True, text=True)
    current = json.loads(result.stdout)[0]
    return {'id': current['Id'], 'image': current['Image'],
            'mount': mount_evidence(run, directory)}


def scoped_read(code, run_id):
    expression = r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*'
    match = re.fullmatch(expression + '(' + STRING + ')' + OPTIONS + r'\s*\}\s*\)\s*\)\s*;?\s*', code.strip())
    if not match:
        return False
    try:
        args = shlex.split(json.loads(match.group(1)))
    except (ValueError, TypeError):
        return False
    return args == ['python3', str(ROOT / 'tools/agent_io.py'), '--run', run_id,
                    '--cmd', READ_COMMAND]


def mount_evidence(run, directory):
    result = subprocess.run(['docker', 'inspect', run['container']], check=True,
                            capture_output=True, text=True)
    mounts = json.loads(result.stdout)[0]['Mounts']
    matches = [m for m in mounts if m['Destination'] == '/eval-input']
    if len(matches) != 1 or matches[0]['RW'] or Path(matches[0]['Source']).resolve() != directory.resolve():
        raise ValueError('Expected this run own read-only control-input mount')
    return matches[0]


def objects(value):
    """Decode structured native tool output, including JSON nested in text blocks."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from objects(child)
    elif isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return
        if isinstance(decoded, (dict, list)):
            yield from objects(decoded)


def native_command_records(payload):
    """Only complete stdout JSON from the actual exec/poll result is receipt.

    Arbitrary nested dictionaries or a truncated stdout containing a complete-looking
    embedded record do not establish delivery.
    """
    for envelope in result_objects(payload):
        if envelope.get('exit_code') != 0 or not isinstance(envelope.get('output'), str):
            continue
        try:
            record = json.loads(envelope['output'])
        except (ValueError, TypeError):
            continue
        if isinstance(record, dict):
            yield record


def _stage(run_id, selector):
    directory = run_directory(run_id)
    run = read(directory / 'run.json')
    prepared = qualify_preparation(run_id, run)
    if len(run['turns']) != 1 or not run.get('completion_evidence'):
        raise ValueError('Preserve exactly one completed intermediate turn before disclosure')
    folder = directory / 'control-inputs'
    destination = directory / 'control-input-stage.json'
    temporary = directory / '.controlled-input-pending'
    if destination.exists() or temporary.exists() or (directory / 'control-input-staging-fault.json').exists():
        raise ValueError('Preserve prior staging attempt')
    if folder.is_symlink() or not folder.is_dir() or any(folder.iterdir()):
        raise ValueError('Control directory must be empty before second-turn staging')
    container = container_evidence(run, folder)
    if container['image'] != run['image_id']:
        raise ValueError('Container image changed')
    if container != prepared['container_identity']:
        raise ValueError('Container changed after preparation')
    metadata = case_directory(run['case_id']) / 'metadata.json'
    if tree_hash(case_directory(run['case_id'])) != run['case_hash']:
        raise ValueError('Frozen case changed')
    if selector != source_selector(read(metadata)):
        raise ValueError('Selector does not match frozen case protocol')
    data = expected_input(read(metadata), selector)
    actor = find_session(run['agent_path'])
    first_raw = actor.read_bytes()
    events = [json.loads(line) for line in first_raw.decode().splitlines()]
    completions = [e for e in events if e.get('payload', {}).get('type') == 'task_complete']
    if len(completions) != 1:
        raise ValueError('Staging requires the actual first turn terminal')
    models = [e['payload'] for e in events if e['type'] == 'turn_context']
    finals = []
    for event in events:
        payload = event.get('payload', {})
        if payload.get('type') == 'message' and payload.get('role') == 'assistant' and (
                payload.get('channel') == 'final' or payload.get('phase') == 'final_answer'):
            finals.append('\n'.join(c.get('text', '') for c in payload.get('content', [])
                                    if c.get('type') == 'output_text'))
    if len(models) != 1 or models[0].get('model') != 'gpt-6.1-sol' or models[0].get('effort') != 'medium':
        raise ValueError('Unqualified intermediate actor model')
    if finals != [run['turns'][0]['final']]:
        raise ValueError('Intermediate snapshot does not match actual first response')
    first_completion = {k: completions[0]['payload'].get(k)
                        for k in ('turn_id', 'started_at', 'completed_at', 'duration_ms')}
    if run['completion_evidence'] != [first_completion]:
        raise ValueError('Collected first completion differs from native terminal')
    if not first_completion['completed_at'] <= run['turns'][0]['collected_at'] <= time.time():
        raise ValueError('Intermediate collection preceded completion or is in the future')
    path = folder / 'turn-2.txt'
    commands = directory / 'commands.jsonl'
    command_prefix = commands.read_bytes() if commands.exists() else b''
    commands_before = len(command_prefix.decode().splitlines())
    proof = {'protocol': PROTOCOL, 'run_id': run_id, 'container': run['container'],
             'case_id': run['case_id'], 'condition': run['condition'], 'repeat': run['repeat'],
             'case_hash': run['case_hash'], 'container_identity': container,
             'staged_at': time.time(), 'source_metadata': str(metadata),
             'source_metadata_sha256': digest(metadata.read_bytes()), 'selector': selector,
             'input_path': str(path), 'input_sha256': digest(data), 'input_bytes': len(data),
             'container_input_path': INPUT_PATH, 'read_command': READ_COMMAND,
             'followup': followup(run_id), 'followup_sha256': digest(followup(run_id).encode()),
             'read_only_mount': container['mount'], 'first_final_sha256': digest(run['turns'][0]['final'].encode()),
             'first_actor_source_prefix_bytes': len(first_raw),
             'first_actor_source_sha256': digest(first_raw),
             'first_completion': first_completion,
             'first_snapshot_sha256': digest(json.dumps(run['turns'][0], sort_keys=True).encode()),
             'commands_before_staging': commands_before,
             'commands_prefix_bytes': len(command_prefix),
             'commands_prefix_sha256': digest(command_prefix),
             'initial_prompt_sha256': run['prompt_hash']}
    # No file is visible in the mount until all fallible preparation succeeds.
    try:
        with temporary.open('xb') as stream:
            stream.write(data)
        temporary.chmod(0o444)
        with destination.open('x') as stream:
            json.dump(proof, stream, indent=2)
        temporary.rename(path)
    except Exception as error:
        fault = directory / 'control-input-staging-fault.json'
        with fault.open('x') as stream:
            json.dump({'status': 'evaluation_error', 'category': 'evaluator_staging_fault',
                       'input_disclosed': path.exists(), 'error': str(error)}, stream)
        raise
    return proof


def stage(run_id, selector):
    try:
        return _stage(run_id, selector)
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        directory = run_directory(run_id)
        fault = directory / 'control-input-staging-fault.json'
        if directory.is_dir() and not fault.exists():
            with fault.open('x') as stream:
                json.dump({'status': 'evaluation_error', 'category': 'evaluator_staging_fault',
                           'protocol': PROTOCOL, 'run_id': run_id,
                           'input_disclosed': (directory / 'control-inputs/turn-2.txt').exists(),
                           'error': str(error)}, stream, indent=2)
        raise ControlFault('evaluation_error', 'evaluator_staging_fault', str(error)) from error


def _attest(run_id):
    directory = run_directory(run_id)
    run, staging = read(directory / 'run.json'), read(directory / 'control-input-stage.json')
    if (directory / 'control-input-staging-fault.json').exists():
        raise ValueError('A recorded staging fault prohibits actor continuation/grading')
    prepared = qualify_preparation(run_id, run)
    if len(run['turns']) != 2:
        raise ValueError('Expected exactly two collected actor turns')
    metadata = case_directory(run['case_id']) / 'metadata.json'
    canonical = directory / 'control-inputs' / 'turn-2.txt'
    identities = {'protocol': PROTOCOL, 'run_id': run_id, 'container': run['container'],
                  'case_id': run['case_id'], 'condition': run['condition'], 'repeat': run['repeat'],
                  'case_hash': run['case_hash'], 'source_metadata': str(metadata),
                  'selector': source_selector(read(metadata)), 'input_path': str(canonical),
                  'container_input_path': INPUT_PATH, 'read_command': READ_COMMAND,
                  'followup': followup(run_id), 'followup_sha256': digest(followup(run_id).encode()),
                  'initial_prompt_sha256': run['prompt_hash']}
    if any(staging.get(key) != value for key, value in identities.items()):
        raise ValueError('Staging identities do not match this frozen run')
    if tree_hash(case_directory(run['case_id'])) != run['case_hash']:
        raise ValueError('Frozen case changed')
    if canonical.parent.is_symlink() or canonical.is_symlink() or [p.name for p in canonical.parent.iterdir()] != ['turn-2.txt']:
        raise ValueError('Unexpected control artifact or symlink')
    expected = expected_input(read(metadata), staging['selector'])
    if digest(Path(staging['source_metadata']).read_bytes()) != staging['source_metadata_sha256']:
        raise ValueError('Fixed input source changed')
    if Path(staging['input_path']).read_bytes() != expected or digest(expected) != staging['input_sha256']:
        raise ValueError('Fixed control artifact changed')
    container = container_evidence(run, directory / 'control-inputs')
    if container != prepared['container_identity'] or container != staging['container_identity'] or container['image'] != run['image_id']:
        raise ValueError('Container identity, image or mount changed')
    mount = container['mount']
    installed = subprocess.run(['docker', 'exec', run['container'], 'cat', INPUT_PATH],
                               check=True, capture_output=True)
    if installed.stdout != expected or installed.stderr:
        raise ValueError('Installed control input changed')
    if digest(run['turns'][0]['final'].encode()) != staging['first_final_sha256']:
        raise ValueError('Intermediate response changed')
    if digest(json.dumps(run['turns'][0], sort_keys=True).encode()) != staging['first_snapshot_sha256']:
        raise ValueError('Intermediate snapshot changed')
    if run['turns'][1]['request'].encode() != expected:
        raise ValueError('Collected semantic request does not match qualified control source')
    commands_path = directory / 'commands.jsonl'
    command_bytes = commands_path.read_bytes() if commands_path.exists() else b''
    if digest(command_bytes[:staging['commands_prefix_bytes']]) != staging['commands_prefix_sha256']:
        raise ValueError('Preserved original commands prefix changed')
    records = [json.loads(line) for line in command_bytes.decode().splitlines()]
    candidates = [r for r in records[staging['commands_before_staging']:]
                  if r.get('command') == READ_COMMAND and r.get('exit_code') == 0
                  and r.get('output', '').encode() == expected and r.get('container') == run['container']]
    actor = find_session(run['agent_path'])
    raw = actor.read_bytes()
    if digest(raw[:staging['first_actor_source_prefix_bytes']]) != staging['first_actor_source_sha256']:
        raise ValueError('Original intermediate native prefix changed')
    events = [json.loads(line) for line in raw.decode().splitlines()]
    models = [e['payload'] for e in events if e['type'] == 'turn_context']
    if len(models) != 2 or any(m.get('model') != 'gpt-6.1-sol' or m.get('effort') != 'medium' for m in models):
        raise ValueError('Unqualified actor turn settings')
    delivery = followup_evidence(events, raw[:staging['first_actor_source_prefix_bytes']], run, staging)
    contexts = [i for i, e in enumerate(events) if e['type'] == 'turn_context']
    if len(contexts) != 2:
        raise ValueError('Expected precisely two actor turn contexts')
    incoming = [e for e in events if e.get('payload', {}).get('type') == 'agent_message']
    if len(incoming) != 2 or any(e['payload'].get('recipient') != run['agent_path'] for e in incoming):
        raise ValueError('Expected one initial task and one same-session followup')
    calls, owned = {}, {}
    read_attempts = 0
    receipts = []
    for event in events[delivery['second_turn_message_index'] + 1:delivery['second_turn_completion_index']]:
        payload = event.get('payload', {})
        if payload.get('type') in {'custom_tool_call', 'function_call'}:
            if payload.get('name') not in {'exec', 'functions.exec'}:
                continue
            code = str(payload.get('input', payload.get('arguments', '')))
            if scoped_read(code, run_id):
                read_attempts += 1
                calls[payload['call_id']] = payload['call_id']
            else:
                options = poll_options(code)
                if options and options['session_id'] in owned:
                    calls[payload['call_id']] = owned[options['session_id']]
            continue
        if payload.get('type') not in {'custom_tool_call_output', 'function_call_output'}:
            continue
        origin = calls.get(payload.get('call_id'))
        if origin is None:
            continue
        for result in result_objects(payload):
            if type(result.get('session_id')) is int and result.get('exit_code') is None:
                owned[result['session_id']] = origin
        if any(value in candidates for value in native_command_records(payload)):
            receipts.append(payload['call_id'])
    if not receipts:
        attempted_records = [r for r in records[staging['commands_before_staging']:]
                             if r.get('command') == READ_COMMAND]
        if not read_attempts and not attempted_records and delivery['native_followup_plaintext_verified']:
            raise ControlFault('fail', 'actor_control_read_missing',
                               'Actor did not execute the required read after verified followup')
        raise ControlFault('evaluation_error', 'controlled_receipt_unavailable',
                           'Complete actor read receipt unavailable; encrypted followup plaintext cannot prove read noncompliance')
    if sum(e.get('payload', {}).get('type') == 'task_complete' for e in events) != 2:
        raise ValueError('Actor has not completed both turns')
    return {'status': 'pass', 'protocol': PROTOCOL, 'run_id': run_id,
            'stage_sha256': digest((directory / 'control-input-stage.json').read_bytes()),
            'actor_source_sha256': digest(raw), 'native_read_receipt_call_ids': receipts,
            'input_sha256': digest(expected), 'read_only_mount': mount,
            'native_output_matches_fixed_bytes': True,
            'followup_delivery': delivery,
            'limits': ['Attests controlled file receipt, not historical encrypted followup plaintext.',
                       'Transport isolation retains its documented non-adversarial limitations.']}


def attest(run_id):
    try:
        return _attest(run_id)
    except ControlFault:
        raise
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        raise ControlFault('evaluation_error', 'control_integrity_fault', str(error)) from error


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['stage', 'attest'])
    parser.add_argument('run_id')
    parser.add_argument('--selector', default='turn_requests:1')
    args = parser.parse_args()
    result = stage(args.run_id, args.selector) if args.action == 'stage' else attest(args.run_id)
    if args.action == 'attest':
        output = ROOT / 'results' / args.run_id / 'controlled-input-attestation.json'
        with output.open('x') as stream:
            json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))
