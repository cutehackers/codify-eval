"""Additive current-resource absence observation after zero-model preparation failure.

Never retries preparation, changes shared runtime, marks a job removed, or proves
historical creation did not occur. Original receipts/state/error remain intact.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.parse

import improvement_optional_comparison_driver_v7 as d

ROW = d.inputs.sequence()[1]
FOLDER = d.ROOT / 'runtime' / ROW['run_id']
BASE = d.BASE
MANIFEST = BASE / (ROW['run_id'] + '-preparation-daemon-failure-preservation-v1/manifest.json')
PREFIX = BASE / (ROW['run_id'] + '-authentic-preparation-failure-coordinator-prefix-v1.jsonl')
COORDINATOR = Path('/Users/junhyounglee/.codex/sessions/2026/10/10/rollout-2026-10-10T06-52-20-01a122a7-1f52-7810-8588-f0a7a8732fa1.jsonl')
OUTPUT = BASE / (ROW['run_id'] + '-current-owned-resource-absence-v2.json')
PREPARE_ID = 'call_687ba9ad5c5245d59d82376f3acb6ff9'
TERMINAL_ID = 'call_c87f75a8f65e40b08dfdf346d4e0a477'
PREFIX_SHA = 'b5eb2ea0cc45d331962b090a162a346dd9051c3615c037c5d2b2fe82b2bdc989'
require = d.require


def process_output(payload):
    blocks = payload.get('output')
    require(isinstance(blocks, list), 'Authentic rich process output required')
    values = []
    for block in blocks:
        if isinstance(block, dict) and block.get('type') == 'input_text':
            try:
                value = json.loads(block['text'])
            except (ValueError, KeyError):
                continue
            if isinstance(value, dict) and 'chunk_id' in value:
                values.append(value)
    require(len(values) == 1, 'Exactly one authentic process result required')
    return values[0]


def original_failure():
    manifest = json.loads(MANIFEST.read_bytes())
    require(manifest['row'] == ROW and type(manifest['model_actors_allocated']) is int and manifest['model_actors_allocated'] == 0
            and manifest['runtime_ownership_observed'] is True,
            'Exact original failed preparation required')
    for key, pin in manifest['original_evidence_entities'].items():
        d.control.reviewed_entity(d.ROOT / key, pin)
    for name in ('state.json', 'configuration.json'):
        require((FOLDER / name).read_bytes() == (MANIFEST.parent / name).read_bytes(),
                'Original failed runtime must remain unchanged')
    state = json.loads((FOLDER / 'state.json').read_bytes())
    config = json.loads((FOLDER / 'configuration.json').read_bytes())
    intent = json.loads((BASE / (ROW['run_id'] + '-allocation-intent.json')).read_bytes())
    require(config['case'] == ROW['case_id'] and config['condition'] == ROW['condition']
            and config['model'] == 'gpt-6.1-sol' and config['effort'] == 'medium'
            and hashlib.sha256(d.runtime.encoded(config)).hexdigest() == state['configuration_sha256']
            and intent['row'] == ROW and intent['coordinator_id'] == '01a122a7-1f52-7810-8588-f0a7a8732fa1',
            'Exact failed row configuration and coordinator required')
    require(state['first_error'] == manifest['original_preparation_error']
            and state['phase'] == 'preservation_failed'
            and set(state['jobs']) == {'root'}
            and state['jobs']['root']['container_id'] is None
            and state['jobs']['root']['status'] == 'creation_intent'
            and type(state['jobs']['root']['commands']) is int
            and state['jobs']['root']['commands'] == 0,
            'No known historical creation identity or dispatched product commands allowed')
    require(all(not (FOLDER / name).exists() and not (FOLDER / name).is_symlink()
                for name in ('broker', 'registry', 'native-dispatch', 'native-observer')),
            'Failure must precede broker registration and native dispatch')
    receipts = list((FOLDER / 'engine-creations').glob('*/receipt.json'))
    require(len(receipts) == 1, 'One original creation attempt required')
    creation = json.loads(receipts[0].read_bytes())
    result = creation['result']
    require(creation['run_id'] == state['run_id'] and creation['job'] == 'root'
            and creation['configuration_sha256'] == state['configuration_sha256']
            and result['output_complete'] is True and type(result['exit_code']) is int
            and result['exit_code'] == 1 and result['stdout'] == ''
            and '500 Internal Server Error' in result['stderr'],
            'Preserved original failed Docker creation required')
    return manifest, state, config, intent, creation


def native_zero():
    raw = PREFIX.read_bytes()
    require(raw.endswith(b'\n') and hashlib.sha256(raw).hexdigest() == PREFIX_SHA,
            'Exact complete authentic coordinator prefix required')
    with COORDINATOR.open('rb') as stream:
        require(stream.read(len(raw)) == raw, 'Coordinator original prefix changed')
    events = [json.loads(line) for line in raw.splitlines()]
    require(events[0]['type'] == 'session_meta'
            and events[0]['payload']['id'] == '01a122a7-1f52-7810-8588-f0a7a8732fa1',
            'Exact original coordinator session required')
    selected = {}
    for index, event in enumerate(events):
        p = event.get('payload', {})
        if event.get('type') != 'response_item':
            continue
        if p.get('call_id') in (PREPARE_ID, TERMINAL_ID):
            selected[(p['call_id'], p['type'])] = (index, event)
        if p.get('type') == 'function_call' and p.get('namespace') == 'collaboration':
            args = json.loads(p.get('arguments', '{}'))
            if p.get('name') == 'spawn_agent':
                require(args.get('task_name') != ROW['actor_path'].split('/')[-1],
                        'Product root was allocated despite preparation failure')
            if p.get('name') in ('followup_task', 'send_message', 'interrupt_agent'):
                target = args.get('target', '')
                require(target != ROW['actor_path'] and not target.startswith(ROW['actor_path'] + '/')
                        and target != ROW['actor_path'].split('/')[-1],
                        'Product actor delivery despite preparation failure')
    pc = selected[(PREPARE_ID, 'custom_tool_call')]
    pr = selected[(PREPARE_ID, 'custom_tool_call_output')]
    tc = selected[(TERMINAL_ID, 'custom_tool_call')]
    tr = selected[(TERMINAL_ID, 'custom_tool_call_output')]
    require(pc[0] < pr[0] < tc[0] < tr[0]
            and "prep=d.prepare(d.inputs.sequence()[1]" in pc[1]['payload']['input']
            and 'session_id:77710' in tc[1]['payload']['input'],
            'Exact original preparation and same-handle terminal observation required')
    initial, terminal = process_output(pr[1]['payload']), process_output(tr[1]['payload'])
    require(initial.get('session_id') == 77710 and type(terminal.get('exit_code')) is int and terminal['exit_code'] == 1
            and 'CalledProcessError' in terminal.get('output', '')
            and 'engine_create' in terminal['output'],
            'Original same process failed before model dispatch')
    terminal_time = datetime.datetime.fromisoformat(tr[1]['timestamp'].replace('Z', '+00:00')).timestamp()
    return {'prefix_entity': d.control.entity(PREFIX), 'prepare_call_id': PREPARE_ID,
            'terminal_observation_call_id': TERMINAL_ID, 'original_session_id': 77710,
            'terminal_observed_at': terminal_time, 'model_actors_allocated_verified': 0}


def capture(args):
    start = time.time()
    p = subprocess.run(args, capture_output=True, text=True, timeout=25)
    return {'argv': args, 'started_at': start, 'finished_at': time.time(),
            'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr,
            'output_complete': True}


def good(record):
    require(record['output_complete'] is True and type(record['exit_code']) is int and record['exit_code'] == 0
            and record['stderr'] == '', 'Complete healthy engine command required')
    return record['stdout']


def owned_match(info, state):
    name = state['jobs']['root']['container']
    labels = info.get('Labels') or {}
    require(isinstance(labels, dict) and isinstance(info.get('Mounts'), list),
            'Exact labels and mounts required')
    if info['Name'].lstrip('/') == name:
        return True
    if labels.get('codify.optional.run') == state['run_id']:
        return True
    if labels.get('codify.optional.configuration') == state['configuration_sha256']:
        return True
    for mount in info['Mounts']:
        source = mount.get('Source')
        require(isinstance(source, str), 'Complete actual mount sources required')
        path = Path(source)
        if (path == FOLDER or path.is_relative_to(FOLDER)
                or path.resolve() == FOLDER or path.resolve().is_relative_to(FOLDER)):
            return True
    return False


def observe():
    require(not OUTPUT.exists() and not OUTPUT.is_symlink(), 'Create-only observation required')
    manifest, state, config, intent, creation = original_failure()
    zero = native_zero()
    require(not os.environ.get('DOCKER_HOST') and not os.environ.get('DOCKER_CONTEXT'),
            'No hidden Docker endpoint overrides admitted')
    records = {}
    records['context_before'] = capture(['docker', 'context', 'show'])
    context = good(records['context_before']).strip()
    require(bool(re.fullmatch('[A-Za-z0-9_-]+', context)), 'Exact selected context required')
    records['endpoint_before'] = capture(['docker', 'context', 'inspect', context,
                                  '--format', '{{json .Endpoints.docker}}'])
    endpoint = json.loads(good(records['endpoint_before']))
    host = endpoint['Host']
    require(isinstance(host, str) and host.startswith('unix:///'), 'Same local Docker endpoint required')
    socket = host[len('unix://'):]
    require('http://' + urllib.parse.quote(socket, safe='') + '/v' in creation['result']['stderr'],
            'Post-restart endpoint must match original failed create endpoint')
    command = ['docker', '--host', host]
    records['engine_identity_before'] = capture(command + ['info', '--format', '{{.ID}}'])
    engine_identity = good(records['engine_identity_before']).strip()
    require(bool(engine_identity), 'Actual engine identity required')
    records['inventory_before'] = capture(command + ['ps', '-a', '--no-trunc', '--format', '{{json .}}'])
    rows = [json.loads(line) for line in good(records['inventory_before']).splitlines()]
    ids = [row['ID'] for row in rows]
    require(all(isinstance(uid, str) and re.fullmatch('[0-9a-f]{64}', uid) for uid in ids)
            and len(ids) == len(set(ids)), 'Complete distinct engine identities required')
    for uid in ids:
        record = capture(command + ['inspect', '--format',
            '{"Id":{{json .Id}},"Name":{{json .Name}},"Labels":{{json .Config.Labels}},"Mounts":{{json .Mounts}}}', uid])
        records['inspect_' + uid] = record
        info = json.loads(good(record))
        require(info['Id'] == uid and not owned_match(info, state),
                'A matching owned or ambiguous object still exists')
    records['exact_name'] = capture(command + ['inspect', state['jobs']['root']['container']])
    absent = records['exact_name']
    require(absent['output_complete'] is True and type(absent['exit_code']) is int and absent['exit_code'] == 1
            and absent['stdout'].strip() == '[]'
            and absent['stderr'].strip() == 'Error: No such object: ' + state['jobs']['root']['container'],
            'Exact healthy original-name absence required')
    records['inventory_after'] = capture(command + ['ps', '-a', '--no-trunc', '--format', '{{json .}}'])
    after = [json.loads(line) for line in good(records['inventory_after']).splitlines()]
    require({row['ID'] for row in after} == set(ids) and len(after) == len(ids),
            'Engine membership changed across current-absence observation')
    records['engine_identity_after'] = capture(command + ['info', '--format', '{{.ID}}'])
    require(good(records['engine_identity_after']).strip() == engine_identity,
            'Actual engine identity changed across current-absence observation')
    records['endpoint_after'] = capture(['docker', 'context', 'inspect', context,
                                        '--format', '{{json .Endpoints.docker}}'])
    require(d.runtime.encoded(json.loads(good(records['endpoint_after'])))
            == d.runtime.encoded(endpoint),
            'Selected context endpoint changed across current-absence observation')
    records['context_after'] = capture(['docker', 'context', 'show'])
    require(good(records['context_after']).strip() == context, 'Selected engine context changed')
    original_failure()  # Original state/receipts must remain intact after read-only observations.
    end = time.time()
    require(intent['intent_started_at'] <= state['started_at'] <= zero['terminal_observed_at'] <= end,
            'Original preparation, failure and recovery chronology required')
    value = {'row': ROW, 'observation_revision': 2, 'fixed_engine_host': host,
             'actual_engine_identity': engine_identity, 'recorded_at': end, 'original_preparation_failure_preserved': True,
             'original_cleanup_failure_preserved': True,
             'original_error': manifest['original_preparation_error'],
             'original_cleanup_error': manifest['original_cleanup_error'],
             'historical_creation_identity_known': False,
             'historical_id_removal_proven': False, 'creation_never_occurred_proven': False,
             'current_owned_resource_absence_verified': True,
             'current_owned_resource_absence_scope': 'Complete stable current same-endpoint engine inventory, labels/name/mount inspection and healthy original-name absence only.',
             'native_zero_product_allocation': zero,
             'software_pass': None, 'model_actors_allocated': 0,
             'observed_product_native_tokens': None,
             'product_native_tokens_scope': 'No product actors allocated; no software trajectory or native usage exists. Research/coordination effort remains separate.',
             'original_intent_started_at': intent['intent_started_at'],
             'original_runtime_started_at': state['started_at'],
             'original_deadline': state['deadline'],
             'original_preparation_through_terminal_observation_seconds': zero['terminal_observed_at'] - intent['intent_started_at'],
             'terminal_failure_through_current_absence_seconds': end - zero['terminal_observed_at'],
             'all_preparation_failure_wait_restart_recovery_seconds': end - intent['intent_started_at'],
             'engine_records': records,
             'source_entities': {'tools/improvement_optional_preparation_failure_absence_v2.py': d.control.entity(__file__),
                                 'tools/improvement_optional_comparison_driver_v7.py': d.control.entity(d.__file__),
                                 'tools/improvement_optional_runtime_v10.py': d.control.entity(d.runtime.__file__)},
             'evidence_entities': {str(MANIFEST.relative_to(d.ROOT)): d.control.entity(MANIFEST),
                                   str(PREFIX.relative_to(d.ROOT)): d.control.entity(PREFIX),
                                   str((BASE / (ROW['run_id'] + '-post-restart-observation-v1.json')).relative_to(d.ROOT)):
                                       d.control.entity(BASE / (ROW['run_id'] + '-post-restart-observation-v1.json'))},
             'no_retry_or_namespace_replacement': True,
             'comparison_eligible': False, 'superiority_proven': False, 'goal_complete': False}
    d.control.atomic_json(OUTPUT, value, exclusive=True)
    return value


if __name__ == '__main__':
    print(json.dumps({'status': 'prospective_readonly_observer_no_allocation',
                      'current_absence_not_yet_qualified': True}))
