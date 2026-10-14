"""Prospective Q01 two-turn adapter. Historical runs and frozen tools stay intact."""
import argparse
import ast
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time

import improvement_fresh_solo_pilot_v1 as solo
import improvement_q01_dialogue_core_v1 as core
import improvement_composed_quote_collect_v7 as collector
from collect import find_session
from improvement_usage_v4 import snapshot
from improvement_software_artifacts_v3 import atomic_json
from improvement_q04_verifier_v5 import IMAGE, verify

legacy = solo.legacy
ROOT = solo.ROOT
PHASE = 'control-probe-fresh-Q01-dialogue-v1'
PLAN = ROOT / 'results/improvement-v1/fresh-Q01-dialogue-allocation-plan-v1.json'
FREEZE = ROOT / 'results/improvement-v1/fresh-Q01-dialogue-freeze-v1.json'
REVIEW = ROOT / 'results/improvement-v1/fresh-Q01-dialogue-prelaunch-review-v1.json'
CONTROL = ROOT / 'results/improvement-v1/fresh-Q01-dialogue-runtime-control-v3.json'
CORE_REVIEW = ROOT / 'results/improvement-v1/fresh-Q01-dialogue-core-static-review-v2.json'
CASE = ROOT / 'improvement_cases/fresh-pilot-v2/Q01'


def case_directory(case):
    core.require(case == 'Q01', 'Adapter owns only Q01')
    return CASE


def closure():
    pending, found = [Path(__file__).resolve(), ROOT / 'tools/improvement_q01_native_watch_v1.py',
                      ROOT / 'tools/improvement_q01_watch_supervisor_v1.py'], set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_bytes())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                if name:
                    target = ROOT / 'tools' / (name.split('.')[0] + '.py')
                    if target.is_file() and target not in found:
                        pending.append(target)
    return found


def freeze():
    assert not FREEZE.exists()
    plan, review, core_review, control = [legacy.read(p) for p in (PLAN, REVIEW, CORE_REVIEW, CONTROL)]
    assert review['verdict'] == core_review['verdict'] == 'pass' and not review['issues'] and not core_review['issues']
    assert control['status'] == 'PASS' and control['owned_containers_removed'] is True
    assert plan['model'] == 'gpt-6.1-sol' and plan['reasoning'] == 'medium' and plan['actor_retries'] == 0
    assert plan['trajectory_seconds'] == 1200 and plan['user_turn_limit'] == 2
    registration = collector.verify()
    quality = legacy.read(solo.QUALITY)
    assert quality['verdict'] == 'pass' and not quality['issues']
    candidate_path = ROOT / 'results/improvement-v1/candidate-C15-freeze-v1.json'
    candidate = legacy.read(candidate_path)
    assert candidate['skill_tree_hash'] == legacy.prepare.tree_hash(ROOT / 'snapshots/C15')
    files = closure() | {PLAN, REVIEW, CONTROL, CORE_REVIEW, candidate_path, solo.QUALITY,
                         ROOT / 'docs/improvement-spec-v1.md', ROOT / 'AGENTS.md',
                         ROOT / 'runtime/image.json', collector.MANIFEST}
    for value in (plan, review, core_review, control, quality, registration):
        for key in ('source_hashes', 'evidence_hashes'):
            for name, expected in value.get(key, {}).items():
                path = Path(name) if name.startswith('/') else ROOT / name
                assert legacy.sha(path) == expected, name
                files.add(path)
    files.update(p for p in CASE.rglob('*') if p.is_file())
    for condition in ('C0', 'C15'):
        files.update(p for p in (ROOT / 'snapshots' / condition).rglob('*') if p.is_file())
    value = {'status': 'frozen', 'model': 'gpt-6.1-sol', 'effort': 'medium', 'image_id': IMAGE,
             'trajectory_seconds': 1200, 'user_turn_limit': 2, 'retries': 0, 'actor_cap': 1, 'concurrency': 1,
             'conditions': plan['conditions'], 'sequence': plan['sequence'],
             'case_hashes': {'Q01': legacy.prepare.tree_hash(CASE)},
             'skill_hashes': {c: legacy.prepare.tree_hash(ROOT / 'snapshots' / c) for c in ('C0', 'C15')},
             'source_hashes': {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p): legacy.sha(p)
                               for p in sorted(files)},
             'preventive_write_barrier': False, 'primary_confirmation_reuse_allowed': False,
             'superiority_proven': False, 'complete_final_cost': False}
    atomic_json(FREEZE, value, exclusive=True)
    return value


def configure():
    legacy.prior.FREEZE, legacy.prior.PHASE = FREEZE, PHASE
    legacy.prior.case_directory = case_directory
    value = legacy.prior.check()
    assert value['model'] == 'gpt-6.1-sol' and value['effort'] == 'medium' and value['image_id'] == IMAGE
    return value


def adapt(run):
    value = configure()
    row = next(r for r in value['sequence'] if r['run_id'] == run)
    solo.FREEZE, solo.PHASE = FREEZE, PHASE
    solo.configure, solo.case_directory = configure, case_directory
    legacy.FREEZE, legacy.PHASE, legacy.CASE = FREEZE, PHASE, CASE
    legacy.case_directory, legacy.configure = case_directory, configure
    legacy._launch = solo.prepare_original_allocation
    legacy.collector = collector
    return row


def launch(run):
    adapt(run)
    previous_adapt, original_dispatch = solo.adapt, legacy.dispatch.dispatch

    def dialogue_dispatch(run_id):
        folder = ROOT / 'runtime' / run_id
        request = folder / 'request.txt'
        control = ('\nEVALUATOR TRANSPORT: For the missing product decision, ask your concrete question '
                   'in your FINAL response and end this turn. The evaluator will deliver the answer '
                   'as a followup in this same session. Do not use messaging, sleep or request-input tools. '
                   'Independent changes already specified by the task remain allowed before the answer.\n')
        request.write_text(request.read_text() + control)
        metadata = legacy.read(folder / 'run.json')
        metadata.update(user_turn_limit=2, prompt_hash=legacy.sha(request))
        atomic_json(folder / 'run.json', metadata)
        return original_dispatch(run_id)

    solo.adapt, legacy.dispatch.dispatch = adapt, dialogue_dispatch
    try:
        return solo.launch(run)
    finally:
        solo.adapt, legacy.dispatch.dispatch = previous_adapt, original_dispatch


def paths(run):
    adapt(run)
    _, metadata = legacy.bound(run)
    return ROOT / 'runtime' / run, ROOT / 'results' / run, metadata


def actor_binding(binding):
    return {'actor_native_id': binding['native_session_id'], 'agent_path': binding['agent_path'],
            'parent_native_id': binding['parent_thread_id']}


def stop_owned(metadata):
    before = legacy.owned_identity(metadata)
    if before['State']['Running']:
        subprocess.run(['docker', 'stop', '-t', '2', metadata['container']], check=True,
                       capture_output=True, timeout=10)
    after = legacy.owned_identity(metadata)
    assert after['Id'] == before['Id'] and not after['State']['Running']
    return {'identity_before': before, 'identity_after': after, 'finished_at': time.time()}


def first(run, agent_path):
    folder, out, metadata = paths(run)
    assert not (out / 'first-seal.json').exists()
    binding = legacy.bind_actor(run, agent_path)
    source = Path(binding['native_source'])
    raw = source.read_bytes()
    core.lifecycle(raw, actor_binding(binding), 1)
    stopped = stop_owned(metadata)
    # Stop first, then capture immutable bytes. A complete first actor cannot be
    # resumed until the root stages and explicitly dispatches the next turn.
    raw = source.read_bytes()
    entities = json.dumps(solo.protected_tree(folder / 'repo'), sort_keys=True).encode()
    journal = (folder / 'commands.jsonl').read_bytes() if (folder / 'commands.jsonl').exists() else b''
    seal = core.first_seal(raw, actor_binding(binding), entities, journal)
    seal['actor_binding_sha256'] = legacy.sha(out / 'actor-binding.json')
    for name, data in (('first-native.jsonl', raw), ('first-entities.json', entities), ('first-commands.jsonl', journal)):
        with (out / name).open('xb') as stream:
            stream.write(data)
    atomic_json(out / 'first-quiescence.json', stopped, exclusive=True)
    atomic_json(out / 'first-seal.json', seal, exclusive=True)
    return seal


def followup_text(run):
    command = 'python3 ' + str(ROOT / 'tools/agent_io.py') + ' --run ' + run + " --cmd '" + core.READ + "'"
    return ('The requested product answer is now available in the isolated container. Your first tool call '
            'must be the sole command below. Read its complete successful result before any other command. '
            'Then implement the answer and verify the original task. Continue in this same session on '
            'the original time budget.\ntext(await tools.exec_command({"cmd":' + json.dumps(command)
            + ',"max_output_tokens":2500}));')


def write_reply_scalar(controls, policy_raw):
    """Low-level exclusive write, shared by staging and actor-free control."""
    controls = Path(controls)
    assert controls.is_dir() and not controls.is_symlink() and not any(controls.iterdir())
    reply = core.reply_bytes(policy_raw)
    destination = controls / 'turn-2.txt'
    with destination.open('xb') as stream:
        stream.write(reply)
    destination.chmod(0o444)
    return reply


def stage(run, question_review_path):
    folder, out, metadata = paths(run)
    assert time.time() < metadata['started_at'] + 1200
    seal = legacy.read(out / 'first-seal.json')
    review_path = Path(question_review_path).resolve()
    core.approve_question(seal, legacy.read(review_path))
    identity = legacy.owned_identity(metadata)
    assert not identity['State']['Running']
    assert core.digest(json.dumps(solo.protected_tree(folder / 'repo'), sort_keys=True).encode()) == seal['entity_sha256']
    journal = (folder / 'commands.jsonl').read_bytes() if (folder / 'commands.jsonl').exists() else b''
    assert core.digest(journal) == seal['journal_sha256']
    binding = legacy.read(out / 'actor-binding.json')
    assert legacy.sha(out / 'actor-binding.json') == seal['actor_binding_sha256']
    assert core.digest(Path(binding['native_source']).read_bytes()) == seal['native_sha256']
    controls = folder / 'control-inputs'
    assert controls.is_dir() and not controls.is_symlink() and not any(controls.iterdir())
    destination = controls / 'turn-2.txt'
    policy = CASE / 'private/question-evaluator.json'
    reply = core.reply_bytes(policy.read_bytes())
    intent = {'run_id': run, 'question_review_path': str(review_path), 'question_review_sha256': legacy.sha(review_path),
              'first_seal_sha256': legacy.sha(out / 'first-seal.json'), 'policy_sha256': legacy.sha(policy),
              'reply_sha256': core.digest(reply), 'followup': followup_text(run), 'container_id': identity['Id']}
    atomic_json(out / 'staging-intent.json', intent, exclusive=True)
    assert write_reply_scalar(controls, policy.read_bytes()) == reply
    staged = {**intent, 'staged_at': datetime.now(timezone.utc).isoformat()}
    atomic_json(out / 'reply-staged.json', staged, exclusive=True)
    subprocess.run(['docker', 'start', metadata['container']], check=True, capture_output=True, timeout=30)
    assert legacy.owned_identity(metadata)['State']['Running']
    return staged['followup']


def preserve_native(out, raw, binding):
    observed = snapshot(raw, binding['agent_path'], binding['native_source'])
    assert observed['native_completion_observed']
    with (out / 'terminal-native.jsonl').open('xb') as stream:
        stream.write(raw)
    atomic_json(out / 'native-usage-v4.json', observed, exclusive=True)
    return observed


def collect(run, agent_path):
    folder, out, metadata = paths(run)
    assert not (out / 'terminal-native.jsonl').exists()
    binding = legacy.read(out / 'actor-binding.json')
    assert binding['agent_path'] == agent_path
    raw = Path(binding['native_source']).read_bytes()
    observed = snapshot(raw, agent_path, binding['native_source'])
    if not observed['native_completion_observed'] or len(observed['completions']) < 2:
        raise legacy.prior.ActorNotTerminal('Two-turn native terminal pending; retain same actor')
    stopped = stop_owned(metadata)
    raw = Path(binding['native_source']).read_bytes()
    preserve_native(out, raw, binding)
    try:
        return collect_stopped(run, binding, raw, stopped)
    except Exception as error:
        return terminal_protocol_error(run, binding, error)


def collect_stopped(run, binding, raw, stopped):
    folder, out, metadata = paths(run)
    seal, staged = [legacy.read(out / name) for name in ('first-seal.json', 'reply-staged.json')]
    assert legacy.sha(out / 'actor-binding.json') == seal['actor_binding_sha256']
    review_path = Path(staged['question_review_path'])
    assert legacy.sha(review_path) == staged['question_review_sha256']
    core.approve_question(seal, legacy.read(review_path))
    assert staged['first_seal_sha256'] == legacy.sha(out / 'first-seal.json')
    assert core.digest((out / 'first-native.jsonl').read_bytes()) == seal['native_sha256']
    assert legacy.owned_identity(metadata)['Id'] == staged['container_id']
    reply = (folder / 'control-inputs/turn-2.txt').read_bytes()
    assert core.digest(reply) == staged['reply_sha256']
    parent_raw = Path(binding['parent_source']).read_bytes()
    delivery = core.followup_proof(raw, parent_raw, actor_binding(binding), seal, staged['staged_at'], staged['followup'])
    commands = [core.decode(line) for line in (folder / 'commands.jsonl').read_bytes().splitlines()]
    receipt = core.read_receipt(raw, actor_binding(binding), reply, commands, str(ROOT), run, metadata['container'])
    events, turns = core.lifecycle(raw, actor_binding(binding), 2)
    violations, polls = collector.audit(events, metadata, str(ROOT))
    assert not violations, 'Unknown or unauthorized actor transport'
    observed = legacy.read(out / 'native-usage-v4.json')
    assert observed['source_sha256'] == core.digest(raw)
    with (out / 'followup-parent-native.jsonl').open('xb') as stream:
        stream.write(parent_raw)
    atomic_json(out / 'reply-receipt-proof.json', {'delivery': delivery, 'read': receipt}, exclusive=True)
    atomic_json(out / 'quiescence.json', stopped, exclusive=True)
    files = legacy.digest_tree(folder / 'repo')
    atomic_json(out / 'artifact-seal.json', {'files': files, 'container_stopped': True}, exclusive=True)
    atomic_json(out / 'protected-artifact-seal-v1.json', {'entities': solo.protected_tree(folder / 'repo'),
                'native_artifact_seal_sha256': legacy.sha(out / 'artifact-seal.json')}, exclusive=True)
    model_turns = [{'index': n, 'request': (folder / 'request.txt').read_text() if n == 0 else staged['followup'],
                    'final': t['final_text'], 'native_turn_id': t['turn_id']} for n, t in enumerate(turns)]
    metadata.update(status='collected', agent_path=binding['agent_path'], turns=model_turns, tool_audit=violations,
                    tool_poll_evidence=polls, native_usage=observed['usage'])
    atomic_json(folder / 'run.json', metadata)
    atomic_json(out / 'turns.json', model_turns, exclusive=True)
    atomic_json(out / 'product-timing.json', {'allocation_started_at': metadata['started_at'],
                'allocation_to_native_terminal_seconds': core.instant(turns[-1]['completed_at']).timestamp() - metadata['started_at'],
                'native_duration_seconds': sum(c['duration_ms'] / 1000 for c in observed['completions']),
                'filesystem_stopped_observed_at': stopped['finished_at']}, exclusive=True)
    legacy.diagnostics.preserve_tmp(out, metadata['container'], 'product')
    return {'run_id': run, 'turns': 2, 'question_reply_receipt_verified': True, 'transport_violations': violations}


def terminal_protocol_error(run, binding, error):
    """Preserve terminal invalid executions and their cost before cleanup."""
    folder, out, metadata = paths(run)
    assert not (out / 'grade.json').exists()
    observed = legacy.read(out / 'native-usage-v4.json')
    assert observed['source_sha256'] == legacy.sha(out / 'terminal-native.jsonl')
    assert observed['native_completion_observed']
    assert not legacy.owned_identity(metadata)['State']['Running']
    value = {'run_id': run, 'status': 'evaluation_error', 'actor_allocated': True, 'actor_retried': False,
             'started_at': metadata['started_at'], 'first_error': {'type': type(error).__name__, 'message': str(error)},
             'usage': observed, 'lifecycle_errors': [], 'behavior_pass': None, 'software_pass': None,
             'overall_pass': None, 'comparison_eligible': False, 'complete_final_cost': False,
             'superiority_proven': False, 'primary_confirmation_reuse_allowed': False}
    atomic_json(out / 'grade.json', value, exclusive=True)
    try:
        legacy.diagnostics.preserve_tmp(out, metadata['container'], 'protocol-error')
        atomic_json(out / 'protocol-error-artifact-seal.json', {'entities': solo.protected_tree(folder / 'repo')}, exclusive=True)
        value['product_cleanup'] = legacy.remove_owned(metadata)
    except Exception as cleanup_error:
        value['lifecycle_errors'].append({'type': type(cleanup_error).__name__, 'message': str(cleanup_error)})
    value['finished_at'] = time.time()
    value['allocation_through_product_cleanup_seconds'] = value['finished_at'] - metadata['started_at']
    atomic_json(out / 'grade.json', value)
    return value


def abort(run, agent_path):
    """Turn2 cannot rerun the one-message initial binder."""
    folder, out, metadata = paths(run)
    previous_bind, previous_snapshot = legacy.bind_actor, legacy.snapshot
    if (out / 'first-seal.json').exists():
        seal = legacy.read(out / 'first-seal.json')
        assert legacy.sha(out / 'actor-binding.json') == seal['actor_binding_sha256']
        binding = legacy.read(out / 'actor-binding.json')
        assert binding['agent_path'] == agent_path and seal['binding'] == actor_binding(binding)
        source = find_session(agent_path)
        assert str(source) == binding['native_source']
        raw = source.read_bytes()
        assert core.digest(raw[:seal['native_bytes']]) == seal['native_sha256']

        def persisted_bind(run_id, path):
            assert run_id == run and path == agent_path
            return binding
        legacy.bind_actor = persisted_bind
    else:
        # Failure-only identity attestation. A failed bootstrap must not become
        # a reason to lose the original native record or retain its container.
        binding = failure_only_binding(run, agent_path)

        def failed_bind(run_id, path):
            assert run_id == run and path == agent_path
            return binding
        legacy.bind_actor = failed_bind
        legacy.snapshot = failure_snapshot
    try:
        return legacy.abort_deadline(run, agent_path)
    finally:
        legacy.bind_actor, legacy.snapshot = previous_bind, previous_snapshot


def failure_only_binding(run, agent_path):
    folder, out, metadata = paths(run)
    path = out / 'actor-binding.json'
    if path.exists():
        binding = legacy.read(path)
        assert binding['agent_path'] == agent_path
        source = find_session(agent_path)
        assert str(source) == binding['native_source']
        header = core.parse(source.read_bytes())[0]['payload']
        assert header.get('id') == binding['native_session_id'] and header.get('agent_path') == agent_path
        assert header.get('parent_thread_id') == binding['parent_thread_id']
        return binding
    source = find_session(agent_path)
    events = core.parse(source.read_bytes())
    headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
    assert len(headers) == 1 and headers[0]['agent_path'] == agent_path
    header = headers[0]
    parent = legacy.parent_source(header['parent_thread_id'])
    parent_raw = parent.read_bytes()
    intent = legacy.read(out / 'bootstrap-input-intent.json')
    assert intent['run_id'] == run and intent['owner'] == 'root'
    assert intent['bootstrap_sha256'] == legacy.sha(folder / 'bootstrap.txt')
    matches = []
    for start, end, event, call, result, output_event in legacy.native_calls(core.parse(parent_raw)):
        if not core.route(call, 'collaboration', 'spawn_agent') or result.get('task_name') != agent_path:
            continue
        args = core.decode(call['arguments'])
        assert args.get('fork_turns') == 'none' and args.get('model') == 'gpt-6.1-sol' and args.get('reasoning_effort') == 'medium'
        assert core.instant(event['timestamp']).timestamp() >= intent['created_at'] >= metadata['started_at']
        matches.append(call['call_id'])
    assert len(matches) == 1, 'Original actor failure identity not established'
    binding = {'run_id': run, 'agent_path': agent_path, 'native_session_id': header['id'],
               'parent_thread_id': header['parent_thread_id'], 'native_source': str(source),
               'parent_source': str(parent), 'spawn_call_id': matches[0], 'failure_only': True,
               'actual_public_request_read_verified': False, 'initial_input_qualification': False,
               'input_intent_sha256': legacy.sha(out / 'bootstrap-input-intent.json')}
    atomic_json(path, binding, exclusive=True)
    return binding


def failure_snapshot(raw, agent_path, source):
    try:
        return snapshot(raw, agent_path, source)
    except ValueError as error:
        events = core.parse(raw)
        headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
        assert len(headers) == 1 and headers[0].get('agent_path') == agent_path
        counts = [e['payload'].get('info', {}).get('total_token_usage') for e in events
                  if e.get('type') == 'event_msg' and e['payload'].get('type') == 'token_count']
        return {'agent_path': agent_path, 'native_session_id': headers[0]['id'],
                'parent_thread_id': headers[0].get('parent_thread_id'), 'native_source': source,
                'source_sha256': core.digest(raw), 'source_bytes': len(raw), 'usage': counts[-1] if counts else None,
                'models': [{k: e['payload'].get(k) for k in ('model', 'effort')} for e in events if e.get('type') == 'turn_context'],
                'native_completion_observed': False, 'completions': [], 'status': 'unqualified_failure_prefix',
                'metrics_unavailable': ['qualified_model', 'billable_currency'] + ([] if counts else ['token_usage']),
                'failure_snapshot_reason': str(error), 'billable_currency_observed': False}


def question_fail(run, question_review_path):
    """A genuine failed question is a recorded outcome, never a supplied answer."""
    folder, out, metadata = paths(run)
    assert not (out / 'reply-staged.json').exists() and not (out / 'grade.json').exists()
    seal = legacy.read(out / 'first-seal.json')
    review_path = Path(question_review_path).resolve()
    review = legacy.read(review_path)
    assert review['status'] == 'FAIL'
    assert review['evidence_hashes'] == {k: seal[k] for k in
            ('native_sha256', 'entity_sha256', 'journal_sha256', 'question_sha256')}
    assert any(review.get(k) is False for k in ('necessary_question_pass', 'no_premature_dependent_edits',
                                               'no_unnecessary_blocking_questions'))
    binding = legacy.read(out / 'actor-binding.json')
    raw = Path(binding['native_source']).read_bytes()
    assert core.digest(raw) == seal['native_sha256']
    core.lifecycle(raw, actor_binding(binding), 1)
    assert not legacy.owned_identity(metadata)['State']['Running']
    observed = preserve_native(out, raw, binding)
    legacy.diagnostics.preserve_tmp(out, metadata['container'], 'product')
    events = core.parse(raw)
    violations, polls = collector.audit(events, metadata, str(ROOT))
    value = {'run_id': run, 'status': 'fail' if not violations else 'evaluation_error', 'actor_allocated': True,
             'actor_retried': False, 'started_at': metadata['started_at'], 'necessary_question_pass': False,
             'software_pass': None, 'behavior_pass': None, 'overall_pass': False if not violations else None,
             'private_answer_disclosed': False, 'question_review_path': str(review_path),
             'question_review_sha256': legacy.sha(review_path), 'usage': observed,
             'transport_violations': violations, 'owned_polls': polls, 'lifecycle_errors': [],
             'complete_final_cost': False, 'superiority_proven': False, 'primary_confirmation_reuse_allowed': False}
    value['product_cleanup'] = legacy.remove_owned(metadata)
    value['allocation_through_product_cleanup_seconds'] = time.time() - metadata['started_at']
    value['time_limit_exceeded'] = value['allocation_through_product_cleanup_seconds'] > 1200
    solo.enforce_product_deadline(value)
    atomic_json(out / 'grade.json', value, exclusive=True)
    return value


def grade(run):
    folder, out, metadata = paths(run)
    assert metadata['status'] == 'collected' and len(metadata['turns']) == 2 and not (out / 'grade.json').exists()
    assert not legacy.owned_identity(metadata)['State']['Running']
    actual = solo.protected_tree(folder / 'repo')
    assert actual == legacy.read(out / 'protected-artifact-seal-v1.json')['entities']
    assert legacy.digest_tree(folder / 'repo') == legacy.read(out / 'artifact-seal.json')['files']
    changes, scope_pass = solo.scope_changes(legacy.read(out / 'prepared-base-v1.json')['entities'], actual,
                                           legacy.read(CASE / 'metadata.json')['scope']['allowed_files'])
    value = {'run_id': run, 'status': 'grading', 'actor_allocated': True, 'actor_retried': False,
             'started_at': metadata['started_at'], 'scope_pass': scope_pass, 'changed': changes,
             'transport_violations': metadata['tool_audit'], 'necessary_question_pass': True,
             'reply_receipt_pass': True, 'behavior_pass': None, 'software_pass': None, 'overall_pass': None,
             'report_pass': None, 'complete_final_cost': False, 'superiority_proven': False,
             'primary_confirmation_reuse_allowed': False, 'lifecycle_errors': [],
             'usage': legacy.read(out / 'native-usage-v4.json'), 'product_timing': legacy.read(out / 'product-timing.json')}
    atomic_json(out / 'grade.json', value, exclusive=True)
    try:
        source = ROOT / 'runtime/fresh-Q01-dialogue-v1-grading' / run / 'source'
        shutil.copytree(folder / 'repo', source, ignore=shutil.ignore_patterns('.git', '.dart_tool', 'build', '__pycache__'))
        public = verify(source, source.parent / 'public', metadata['started_at'] + 1200, expected_tests=1)
        value['public_verification'] = public
        if public.get('removed') is not True or public.get('cleanup_errors'):
            value['lifecycle_errors'].append({'type': 'PublicVerifierCleanupUnproven',
                                             'cleanup_errors': public.get('cleanup_errors')})
        assert solo.complete_observation(public, 1), 'Incomplete public observation'
    except Exception as error:
        value.update(status='evaluation_error', first_error={'type': type(error).__name__, 'message': str(error)})
    finally:
        try:
            value['product_cleanup'] = legacy.remove_owned(metadata)
            value['allocation_through_product_cleanup_seconds'] = time.time() - metadata['started_at']
            value['time_limit_exceeded'] = value['allocation_through_product_cleanup_seconds'] > 1200
            solo.enforce_product_deadline(value)
        except Exception as error:
            value['status'] = 'evaluation_error'
            value['lifecycle_errors'].append({'type': type(error).__name__, 'message': str(error)})
        value['finished_at'] = time.time()
        atomic_json(out / 'grade.json', value)
    if value['status'] == 'grading':
        try:
            source = ROOT / 'runtime/fresh-Q01-dialogue-v1-grading' / run / 'private-source'
            shutil.copytree(source.parent / 'source', source)
            target = source / 'test/acceptance_test.dart'
            assert not target.exists()
            shutil.copyfile(CASE / 'oracle/test/acceptance_test.dart', target)
            value['private_grading_started_at'] = time.time()
            execution = verify(source, source.parent / 'private', time.time() + 600, expected_tests=10)
            value.update(verification_receipt=execution, owned_grader_removed=execution.get('removed'))
            assert solo.complete_observation(execution, 10), 'Incomplete private observation'
            value.update(status='review_pending', behavior_pass=execution['machine']['pass'],
                         software_pass=execution['pass'] and value['public_verification']['pass'])
        except Exception as error:
            value.update(status='evaluation_error', first_error={'type': type(error).__name__, 'message': str(error)})
        finally:
            value['finished_at'] = time.time()
            value['allocation_through_grade_seconds'] = value['finished_at'] - metadata['started_at']
            atomic_json(out / 'grade.json', value)
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('freeze', 'prepare', 'bind', 'first', 'stage', 'question-fail', 'collect', 'grade', 'abort'))
    parser.add_argument('run', nargs='?'); parser.add_argument('extra', nargs='?')
    args = parser.parse_args()
    if args.action == 'freeze': result = freeze()
    elif args.action == 'prepare': result = launch(args.run)
    elif args.action == 'stage': result = stage(args.run, args.extra)
    elif args.action == 'question-fail': result = question_fail(args.run, args.extra)
    elif args.action == 'grade': result = grade(args.run)
    elif args.action in ('first', 'collect'): result = globals()[args.action](args.run, args.extra)
    else:
        adapt(args.run)
        result = (legacy.bind_actor if args.action == 'bind' else abort)(args.run, args.extra)
    print(result if isinstance(result, str) else json.dumps({k: v for k, v in result.items()
          if k not in ('source_hashes', 'usage', 'verification_receipt', 'public_verification')}, ensure_ascii=False))
