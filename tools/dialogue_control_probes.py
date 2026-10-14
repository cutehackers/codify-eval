"""Isolated synthetic regressions and owned Docker transport probes.

Synthetic native events establish parser behavior only, never model receipt.
No evaluated actor, source case, or pre-existing container is touched.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import copy
from datetime import datetime, timezone
import json
import inspect
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid
from unittest.mock import patch

import dialogue_control as control
from prepare import tree_hash

ROOT = Path(__file__).resolve().parents[1]


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2))


def event(kind, payload, timestamp):
    stamp = datetime.fromtimestamp(time.time()+timestamp, timezone.utc).isoformat()
    return {'type': kind, 'payload': payload, 'timestamp': stamp}


class Fixture:
    """Every fixture uses only public synthetic Korean bytes and fake sessions."""
    def __init__(self, root):
        self.root = root
        self.run_id = 'control-probe-SYN-B-1'
        self.directory = root / 'runtime' / self.run_id
        self.folder = self.directory / 'control-inputs'
        self.folder.mkdir(parents=True)
        self.case = root / 'contract_cases' / 'SYN'
        self.case.mkdir(parents=True)
        self.data = '합성 검사 요청\n둘째 줄'.encode()
        dump(self.case / 'metadata.json', {'turn_requests': ['synthetic initial', self.data.decode()]})
        (root / 'tools').mkdir()
        for name in ('dialogue_control.py', 'grade.py'):
            shutil.copyfile(ROOT / 'tools' / name, root / 'tools' / name)
        self.sessions = root / 'synthetic-sessions'
        self.sessions.mkdir()
        self.actor = self.sessions / 'actor.jsonl'
        self.parent = self.sessions / 'synthetic-parent-id.jsonl'
        self.identity = {'id': 'synthetic-container-id', 'image': 'synthetic-image',
                         'mount': {'Source': str(self.folder), 'Destination': '/eval-input', 'RW': False}}
        self.first_completion = {'turn_id':'first', 'started_at':time.time()-2,
                                 'completed_at':time.time()-1, 'duration_ms':1000}
        self.first = [event('session_meta', {'source': {'subagent': {'thread_spawn': {
            'parent_thread_id': 'parent-id', 'agent_path': '/root/synthetic'}}}}, 0),
            event('turn_context', {'turn_id': 'first', 'model': 'gpt-6.1-sol', 'effort': 'medium'}, 1),
            event('event_msg', {'type': 'agent_message', 'message': 'synthetic initial',
                'recipient': '/root/synthetic', 'author': '/root',
                'internal_chat_message_metadata_passthrough': {'turn_id': 'first'}}, 2),
            event('response_item', {'type': 'message', 'role': 'assistant', 'channel': 'final',
                'content': [{'type': 'output_text', 'text': 'synthetic question'}]}, 3),
            event('event_msg', {'type': 'task_complete', **self.first_completion}, 4)]
        self.write_events(self.actor, self.first)
        self.run = {'run_id': self.run_id, 'phase': 'control-probe-synthetic',
                    'case_id': 'SYN', 'condition': 'B', 'repeat': 1,
                    'container': 'synthetic-container', 'image_id': self.identity['image'],
                    'case_hash': tree_hash(self.case), 'agent_path': '/root/synthetic',
                    'prompt_hash': 'synthetic-prompt-hash', 'completion_evidence': [self.first_completion],
                    'turns': [{'index': 0, 'request': 'synthetic initial', 'final': 'synthetic question',
                               'collected_at':time.time(), 'files': {'synthetic.txt': 'first snapshot'}}]}

    def pins(self):
        metadata = self.case / 'metadata.json'
        self.run['dialogue_protocol'] = {
            'protocol': control.PROTOCOL, 'selector': 'turn_requests:1',
            'source_metadata': str(metadata), 'source_metadata_sha256': control.digest(metadata.read_bytes()),
            'input_sha256': control.digest(self.data), 'container_input_path': control.INPUT_PATH,
            'input_path': str(self.folder / 'turn-2.txt'), 'read_command': control.READ_COMMAND,
            'followup_sha256': control.digest(control.followup(self.run_id).encode()),
            'tool_hashes': {name: control.digest((self.root / name).read_bytes())
                           for name in ('tools/dialogue_control.py', 'tools/grade.py')},
            'container_identity': copy.deepcopy(self.identity)}
        self.save()

    def save(self):
        dump(self.directory / 'run.json', self.run)

    @staticmethod
    def write_events(path, events):
        path.write_text(''.join(json.dumps(e, ensure_ascii=False) + '\n' for e in events))

    def patched(self, real_docker=False):
        stack = ExitStack()
        stack.enter_context(patch.object(control, 'ROOT', self.root))
        stack.enter_context(patch.object(control, 'SESSION_ROOT', self.sessions))
        stack.enter_context(patch.object(control, 'case_directory', lambda _: self.case))
        stack.enter_context(patch.object(control, 'find_session', lambda _: self.actor))
        if not real_docker:
            stack.enter_context(patch.object(control, 'container_evidence', lambda *_: copy.deepcopy(self.identity)))
            stack.enter_context(patch.object(control.subprocess, 'run', lambda *_args, **_kw:
                subprocess.CompletedProcess([], 0, self.data, b'')))
        return stack

    def stage(self):
        self.pins()
        return control.stage(self.run_id, 'turn_requests:1')

    def second(self, mode='complete', encrypted=False):
        token = 'gAAAAASYNTHETIC-NOT-A-REAL-CIPHERTEXT' if encrypted else control.followup(self.run_id)
        self.parent_events = [event('response_item', {'type': 'function_call',
            'name': 'collaboration.followup_task', 'call_id': 'followup',
            'arguments': json.dumps({'target': '/root/synthetic', 'message': token})}, 5),
            event('response_item', {'type': 'function_call_output', 'call_id': 'followup', 'output': ''}, 7)]
        self.write_events(self.parent, self.parent_events)
        self.second_events = [event('turn_context', {'turn_id': 'second', 'model': 'gpt-6.1-sol', 'effort': 'medium'}, 5),
            event('event_msg', {'type': 'agent_message', 'message': token, 'recipient': '/root/synthetic',
                'author': '/root', 'internal_chat_message_metadata_passthrough': {'turn_id': 'second'}}, 6)]
        record = {'command': control.READ_COMMAND, 'exit_code': 0, 'output': self.data.decode(),
                  'container': self.run['container'], 'synthetic': True}
        if mode == 'failedread':
            record.update(exit_code=1, output='')
        elif mode == 'alteredoutput':
            record['output'] = 'synthetic altered output'
        records = []
        code = control.followup(self.run_id).split('Use this exact read call:\n', 1)[1]
        if mode != 'missing':
            records.append(record)
            self.second_events.append(event('response_item', {'type': 'custom_tool_call',
                'name': 'functions.exec', 'call_id': 'read', 'input': code}, 8))
            if mode == 'poll':
                self.second_events.extend([
                    event('response_item', {'type': 'custom_tool_call_output', 'call_id': 'read',
                        'output': json.dumps({'session_id': 123, 'output': '', 'wall_time_seconds': .1})}, 9),
                    event('response_item', {'type': 'custom_tool_call', 'name': 'functions.exec', 'call_id': 'poll',
                        'input': 'text(await tools.write_stdin({"session_id": 123}));'}, 10)])
            output = {'exit_code': 0, 'output': json.dumps(record), 'wall_time_seconds': .1}
            if mode == 'truncated':
                output['output'] = json.dumps(record)[:-5] + '... [truncated]'
            self.second_events.append(event('response_item', {'type': 'custom_tool_call_output',
                'call_id': 'poll' if mode == 'poll' else 'read', 'output': json.dumps(output)}, 11))
            if mode == 'repeated':
                records.append(copy.deepcopy(record))
                self.second_events.extend([
                    event('response_item', {'type': 'custom_tool_call', 'name': 'functions.exec',
                        'call_id': 'read2', 'input': code}, 12),
                    event('response_item', {'type': 'custom_tool_call_output', 'call_id': 'read2',
                        'output': json.dumps(output)}, 13)])
        self.second_events.append(event('response_item', {'type':'message','role':'assistant','channel':'final',
            'content':[{'type':'output_text','text':'synthetic done'}]}, 13))
        second_completion = {'turn_id':'second','started_at':time.time(),'completed_at':time.time(), 'duration_ms':1}
        self.second_events.append(event('event_msg', {'type': 'task_complete', **second_completion}, 14))
        self.write_events(self.actor, self.first + self.second_events)
        (self.directory / 'commands.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in records))
        self.run['turns'].append({'index': 1, 'request': self.data.decode(), 'final': 'synthetic done'})
        self.run['completion_evidence'].append(second_completion)
        self.save()


def synthetic_probes():
    results = []

    def check(name, operation, expected='pass', category=None):
        with tempfile.TemporaryDirectory(prefix='controlled-synthetic-') as temp:
            fixture = Fixture(Path(temp))
            with fixture.patched():
                try:
                    result = operation(fixture)
                    actual = result.get('status', 'pass') if isinstance(result, dict) else 'pass'
                    detail = result if isinstance(result, dict) else {}
                except Exception as error:
                    detail = getattr(error, 'audit', {'error': str(error), 'type': type(error).__name__})
                    actual = detail.get('status', 'rejected')
                ok = actual == expected and (category is None or detail.get('category') == category)
                results.append({'name': name, 'expected': expected, 'actual': actual, 'passed': ok,
                                'detail': detail, 'evidence_kind': 'synthetic_no_model_receipt'})

    def staged(f):
        assert not (f.folder / 'turn-2.txt').exists() and not list(f.folder.iterdir())
        proof = f.stage()
        assert proof['commands_before_staging'] == 0
        assert (f.folder / 'turn-2.txt').read_bytes() == f.data
        assert (f.folder / 'turn-2.txt').stat().st_mode & 0o222 == 0
        return {'status': 'pass', 'zero_commands': True, 'exact_bytes': True, 'host_mode_read_only': True}

    def attest(f, mode='complete', encrypted=False):
        f.stage(); f.second(mode, encrypted)
        return control.attest(f.run_id)

    def mutate_proof(f, key, value):
        f.stage(); f.second()
        path = f.directory / 'control-input-stage.json'
        proof = control.read(path); proof[key] = value; dump(path, proof)
        return control.attest(f.run_id)

    check('initial_absence_stage_exact_korean_utf8_missing_commands_zero', staged)
    for mode in ('complete', 'poll', 'repeated'):
        check('qualifies_' + mode, lambda f, mode=mode: attest(f, mode))
    check('plaintext_missing_read_actor_failure', lambda f: attest(f, 'missing'), 'fail', 'actor_control_read_missing')
    check('wrong_second_model_and_plaintext_missing_read_evaluator_error',
          lambda f: _wrong_model_missing_read(f), 'evaluation_error', 'control_integrity_fault')
    check('plaintext_failed_exact_read_evaluator_error', lambda f: attest(f, 'failedread'),
          'evaluation_error', 'controlled_receipt_unavailable')
    check('plaintext_altered_exact_read_output_evaluator_error', lambda f: attest(f, 'alteredoutput'),
          'evaluation_error', 'controlled_receipt_unavailable')
    check('encrypted_missing_receipt_evaluator_error', lambda f: attest(f, 'missing', True), 'evaluation_error', 'controlled_receipt_unavailable')
    check('truncated_receipt_evaluator_error', lambda f: attest(f, 'truncated'), 'evaluation_error')
    for key, value in [('run_id', 'other'), ('source_metadata', '/synthetic/other'),
                       ('container', 'other'), ('first_actor_source_sha256', 'other'),
                       ('first_snapshot_sha256', 'other')]:
        check('reject_swapped_' + key, lambda f, key=key, value=value: mutate_proof(f, key, value), 'evaluation_error')

    def identity_changed(f):
        f.stage(); f.second(); f.identity['id'] = 'recreated'; return control.attest(f.run_id)
    check('reject_recreated_container_id', identity_changed, 'evaluation_error')

    def stage_wrong_mount(f):
        f.pins(); f.identity['mount']['RW'] = True
        try:
            control.stage(f.run_id, 'turn_requests:1')
        finally:
            assert not (f.folder / 'turn-2.txt').exists()
    check('stage_wrong_rw_mount_no_disclosure', stage_wrong_mount, 'evaluation_error', 'evaluator_staging_fault')

    def stage_failed(f):
        f.pins()
        original = Path.open
        def denied(path, *args, **kw):
            if path == f.directory / 'control-input-stage.json':
                raise OSError('synthetic publication failure')
            return original(path, *args, **kw)
        try:
            with patch.object(Path, 'open', denied):
                control.stage(f.run_id, 'turn_requests:1')
        finally:
            assert not (f.folder / 'turn-2.txt').exists()
            assert control.read(f.directory / 'control-input-staging-fault.json')['input_disclosed'] is False
    check('stage_proof_failure_no_disclosure_fault_record', stage_failed, 'evaluation_error', 'evaluator_staging_fault')

    def native_mutation(f, mutation):
        f.stage(); f.second()
        mutation(f)
        f.write_events(f.actor, f.first + f.second_events)
        f.write_events(f.parent, f.parent_events)
        return control.attest(f.run_id)

    check('wrong_incoming_turn', lambda f: native_mutation(f, lambda x: x.second_events[1]['payload']['internal_chat_message_metadata_passthrough'].update(turn_id='wrong')), 'evaluation_error')
    check('wrong_followup_target', lambda f: native_mutation(f, lambda x: x.parent_events[0]['payload'].update(arguments=json.dumps({'target':'/root/wrong','message':control.followup(x.run_id)}))), 'evaluation_error')
    check('ciphertext_chain_mismatch', lambda f: native_mutation(f, lambda x: x.second_events[1]['payload'].update(message='gAAAAAdifferent')), 'evaluation_error')
    check('wrong_scoped_read_run', lambda f: native_mutation(f, lambda x: x.second_events[2]['payload'].update(input=x.second_events[2]['payload']['input'].replace(x.run_id,'other-run'))), 'evaluation_error')
    check('unproven_poll_session', lambda f: _wrong_poll(f), 'evaluation_error')
    check('read_in_first_turn_not_second', lambda f: _wrong_turn(f), 'evaluation_error')
    check('read_before_followup_incoming', lambda f: _before_incoming(f), 'evaluation_error')
    check('unrelated_tool_named_as_scoped_read', lambda f: native_mutation(f, lambda x: x.second_events[2]['payload'].update(name='unrelated_tool')), 'evaluation_error')
    check('outer_truncation_with_embedded_complete_record', lambda f: _outer_truncated(f), 'evaluation_error')
    check('reject_utf8_korean_crlf_source', lambda f: control.expected_input({'turn_requests':['x','한글\r\n요청']}, 'turn_requests:1'), 'rejected')
    return results


def _wrong_poll(f):
    f.stage(); f.second('poll')
    f.second_events[4]['payload']['input'] = 'text(await tools.write_stdin({"session_id": 999}));'
    f.write_events(f.actor, f.first + f.second_events)
    return control.attest(f.run_id)


def _wrong_model_missing_read(f):
    f.stage(); f.second('missing')
    f.second_events[0]['payload']['model'] = 'synthetic-wrong-model'
    f.write_events(f.actor, f.first + f.second_events)
    return control.attest(f.run_id)


def _wrong_turn(f):
    f.stage(); f.second()
    read_events = f.second_events[2:4]
    f.second_events[2:4] = []
    # Rewriting preserved first bytes must itself be rejected before a receipt is accepted.
    f.write_events(f.actor, f.first[:-1] + read_events + f.first[-1:] + f.second_events)
    return control.attest(f.run_id)


def _before_incoming(f):
    f.stage(); f.second()
    incoming = f.second_events.pop(1)
    f.second_events.insert(3, incoming)
    f.write_events(f.actor, f.first + f.second_events)
    return control.attest(f.run_id)


def _outer_truncated(f):
    f.stage(); f.second()
    payload = f.second_events[3]['payload']
    output = json.loads(payload['output'])
    output['original_token_count'] = 10000
    output['output'] += '\n... output truncated ...'
    # Preserve a valid nested object elsewhere to ensure outer truncation is not ignored.
    output['embedded_record'] = json.loads((f.directory/'commands.jsonl').read_text())
    payload['output'] = json.dumps(output)
    f.write_events(f.actor, f.first + f.second_events)
    return control.attest(f.run_id)


def docker_probe():
    """Real file/mount checks using one new container and synthetic first-final."""
    image = control.read(ROOT / 'runtime/image.json')['image_id']
    name = 'codify-control-probe-v36-' + uuid.uuid4().hex[:12]
    evidence = {'evidence_kind': 'real_docker_no_model_receipt', 'container_name': name,
                'image_id': image, 'synthetic_first_final': True, 'checks': []}
    def command(args, **kwargs):
        return subprocess.run(['docker'] + args, capture_output=True, **kwargs)
    created = False
    with tempfile.TemporaryDirectory(prefix='control-probe-v36-', dir=ROOT / 'runtime') as temp:
        fixture = Fixture(Path(temp))
        with fixture.patched(real_docker=True):
            try:
                fixture.run['container'] = name
                fixture.run['image_id'] = image
                # A real writable mount must be rejected before file disclosure.
                result = command(['run','-d','--name',name,'--network','none','-v',str(fixture.folder)+':/eval-input',image,'sleep','infinity'], check=True)
                created = True
                evidence['wrong_mount_container_id'] = result.stdout.decode().strip()
                fixture.identity = {'id': evidence['wrong_mount_container_id'], 'image': image,
                    'mount': {'Source': str(fixture.folder), 'Destination':'/eval-input','RW': True}}
                fixture.pins()
                try:
                    control.mount_evidence(fixture.run, fixture.folder)
                    rejected = False
                except ValueError as error:
                    rejected = True; evidence['wrong_mount_error'] = str(error)
                evidence['checks'].append({'name':'real_wrong_mount_rejected_without_disclosure',
                    'passed': rejected and not (fixture.folder/'turn-2.txt').exists()})
                command(['rm','-f',name], check=True); created = False
                result = command(['run','-d','--name',name,'--network','none','-v',str(fixture.folder)+':/eval-input:ro',image,'sleep','infinity'], check=True)
                created = True
                fixture.identity = control.container_evidence(fixture.run, fixture.folder)
                evidence['initial_container_identity'] = copy.deepcopy(fixture.identity)
                absent = command(['exec',name,'cat',control.INPUT_PATH])
                evidence['checks'].append({'name':'real_initial_file_absent', 'passed': absent.returncode != 0,
                                           'exit_code':absent.returncode, 'stderr':absent.stderr.decode()})
                fixture.stage()
                installed = command(['exec',name,'cat',control.INPUT_PATH], check=True)
                evidence['checks'].append({'name':'real_post_first_final_exact_utf8_bytes',
                    'passed':installed.stdout == fixture.data and not installed.stderr,
                    'sha256':control.digest(installed.stdout), 'byte_count':len(installed.stdout)})
                denied = command(['exec',name,'sh','-c','printf altered > /eval-input/turn-2.txt'])
                evidence['checks'].append({'name':'real_container_write_denied', 'passed':denied.returncode != 0,
                    'exit_code':denied.returncode, 'stderr':denied.stderr.decode()})
                evidence['checks'].append({'name':'real_bytes_unchanged_after_denied_write',
                    'passed':command(['exec',name,'cat',control.INPUT_PATH],check=True).stdout == fixture.data})
                fixture.second()
                evidence['synthetic_attest_on_real_docker'] = control.attest(fixture.run_id)['status']
                command(['rm','-f',name], check=True); created = False
                command(['run','-d','--name',name,'--network','none','-v',str(fixture.folder)+':/eval-input:ro',image,'sleep','infinity'],check=True)
                created = True
                evidence['recreated_container_identity'] = control.container_evidence(fixture.run, fixture.folder)
                try:
                    control.attest(fixture.run_id)
                    rejected = False
                except control.ControlFault as error:
                    rejected = error.audit['status'] == 'evaluation_error'
                    evidence['recreated_fault'] = error.audit
                evidence['checks'].append({'name':'real_recreated_id_rejected', 'passed':rejected})
            except Exception as error:
                evidence['error'] = str(error)
            finally:
                if created:
                    cleanup = command(['rm','-f',name])
                    evidence['owned_container_cleanup_exit_code'] = cleanup.returncode
                else:
                    evidence['owned_container_cleanup_exit_code'] = 0
                absent = command(['inspect', name])
                evidence['owned_container_absent_after_cleanup'] = absent.returncode != 0
    evidence['passed'] = not evidence.get('error') and all(c['passed'] for c in evidence['checks']) and evidence['owned_container_cleanup_exit_code'] == 0 and evidence['owned_container_absent_after_cleanup']
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--docker', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT/'results/controlled-input-regression-v3.6.json')
    args = parser.parse_args()
    probes = synthetic_probes()
    report = {'protocol':control.PROTOCOL, 'version':'v3.6',
        'scope':'Deterministic isolated synthetic regressions and optional owned real Docker file/mount checks. No actor dispatch, semantic H access, or model receipt claim.',
        'implementation_sha256':control.digest((ROOT/'tools/dialogue_control.py').read_bytes()),
        'tested_tool_sha256':{name:control.digest((ROOT/name).read_bytes())
            for name in ('tools/dialogue_control.py','tools/prepare.py','tools/grade.py','tools/transport.py')},
        'physical_docker_function_sha256':{name:control.digest(inspect.getsource(getattr(control,name)).encode())
            for name in ('_stage','stage','mount_evidence','container_evidence')},
        'probe_tool_sha256':control.digest(Path(__file__).read_bytes()),
        'synthetic': {'count':len(probes),'passed':sum(p['passed'] for p in probes), 'probes':probes},
        'real_docker':docker_probe() if args.docker else {'status':'not_run'},
        'model_receipt_verified':False}
    dump(args.output, report)
    passed = all(p['passed'] for p in probes) and (not args.docker or report['real_docker']['passed'])
    print(json.dumps({'passed':passed,'synthetic_count':len(probes),
        'synthetic_failures':[p['name'] for p in probes if not p['passed']],
        'real_docker':report['real_docker'].get('passed','not_run'),'output':str(args.output)}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
