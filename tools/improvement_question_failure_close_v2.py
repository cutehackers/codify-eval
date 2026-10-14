"""Guard-independent failure preservation for an already allocated question run.

Never stops an actor. Removes its owned product container only after the same
actual native source proves every opened turn completed. A live/unknown actor
remains pending for the root to observe or interrupt with actual tool evidence.
"""
import json
import math
from pathlib import Path
import time

import improvement_q01_dialogue_pilot_v1 as old
from collect import find_session
from improvement_q04_verifier_v5 import IMAGE
from improvement_software_artifacts_v3 import atomic_json

ROOT, core, legacy = old.ROOT, old.core, old.legacy
PHASE = 'control-probe-natural-question-v1'


def allocated_paths(run):
    assert isinstance(run, str) and all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in run)
    folder, out = ROOT / 'runtime' / run, ROOT / 'results' / run
    metadata = legacy.read(folder / 'run.json')
    assert metadata['case_id'] in {'Q05', 'Q06'} and metadata['condition'] in {'A', 'C0', 'C16'}
    assert metadata['repeat'] == 1
    assert run == f"{PHASE}-{metadata['case_id']}-{metadata['condition']}-1"
    assert metadata['run_id'] == run and metadata['phase'] == PHASE
    assert metadata['model'] == 'gpt-6.1-sol' and metadata['effort'] == 'medium'
    assert metadata['image_id'] == IMAGE and metadata['container'] == 'codify-' + run.lower()
    started = metadata['started_at']
    assert type(started) in (int, float) and math.isfinite(started)
    intent = legacy.read(out / 'launch-intent.json')
    assert intent['run_id'] == run and intent['started_at'] == started
    # Ownership checks are independent of the source guard that triggered close.
    legacy.owned_identity(metadata)
    return folder, out, metadata


def terminal_graph(events):
    """Structural terminality only. Invalid model evidence remains invalid."""
    try:
        groups = {name: [] for name in ('start', 'context', 'incoming', 'final', 'complete')}
        for index, event in enumerate(events):
            payload = event['payload']
            name = None
            if event.get('type') == 'turn_context':
                name = 'context'
            elif event.get('type') == 'event_msg' and payload.get('type') in ('task_started', 'task_complete'):
                name = 'start' if payload['type'] == 'task_started' else 'complete'
            elif event.get('type') == 'response_item':
                if payload.get('type') == 'agent_message':
                    name = 'incoming'
                elif payload.get('type') == 'message' and payload.get('role') == 'assistant' and (
                        payload.get('channel') == 'final' or payload.get('phase') == 'final_answer'):
                    name = 'final'
            if name:
                groups[name].append((index, payload))
        count = len(groups['start'])
        if count not in (1, 2) or any(len(rows) != count for rows in groups.values()):
            return False
        seen, end, bounds = set(), -1, []
        header = events[0]['payload']
        for rows in zip(*(groups[name] for name in ('start', 'context', 'incoming', 'final', 'complete'))):
            indexes = [i for i, _ in rows]
            ids = [core.turn_id(payload) for _, payload in rows]
            identity = ids[0]
            incoming = rows[2][1]
            if (not isinstance(identity, str) or not identity or len(set(ids)) != 1 or identity in seen
                    or not end < indexes[0] or indexes != sorted(set(indexes))
                    or incoming.get('author') != header['agent_path'].rsplit('/', 1)[0]
                    or incoming.get('recipient') != header['agent_path']
                    or rows[-1][1].get('last_agent_message') != core.final_text(rows[3][1])):
                return False
            seen.add(identity)
            end = indexes[-1]
            bounds.append((indexes[2], indexes[3]))
        calls, outputs = {}, set()
        for index, event in enumerate(events):
            payload = event['payload']
            kind = payload.get('type')
            if event.get('type') != 'response_item' or kind not in (
                    'function_call', 'custom_tool_call', 'function_call_output', 'custom_tool_call_output'):
                continue
            if not any(start < index < finish for start, finish in bounds):
                return False
            identity = payload.get('call_id')
            if not isinstance(identity, str) or not identity:
                return False
            if kind in ('function_call', 'custom_tool_call'):
                if identity in calls:
                    return False
                calls[identity] = kind
            else:
                if identity not in calls or identity in outputs or kind != calls[identity] + '_output':
                    return False
                outputs.add(identity)
        return set(calls) == outputs
    except (KeyError, TypeError, ValueError):
        return False


def parent_gate(raw, binding, events):
    """No successful or unresolved same-actor delivery without a closed child turn."""
    parent = core.parse(raw)
    headers = [e['payload'] for e in parent if e.get('type') == 'session_meta']
    assert len(headers) == 1 and headers[0]['id'] == binding['parent_thread_id']
    target = binding['agent_path']
    calls, outputs = [], {}
    for index, event in enumerate(parent):
        payload = event['payload']
        if payload.get('type') == 'function_call' and core.route(payload, 'collaboration', 'followup_task'):
            args = core.decode(payload['arguments']) if isinstance(payload.get('arguments'), str) else payload.get('arguments')
            assert isinstance(args, dict)
            if args.get('target') in (target, target.rsplit('/', 1)[-1]):
                calls.append((index, event, args))
        if payload.get('type') in ('function_call_output', 'custom_tool_call_output'):
            identity = payload.get('call_id')
            if identity in outputs:
                outputs[identity] = None
            else:
                outputs[identity] = (index, event)
    incoming = [event for event in events if event.get('type') == 'response_item'
                and event['payload'].get('type') == 'agent_message']
    assert len(calls) == len(incoming) - 1 and len(calls) <= 1
    signatures = []
    for call, delivered in zip(calls, incoming[1:]):
        index, event, args = call
        identity = event['payload'].get('call_id')
        assert isinstance(identity, str) and identity
        receipt = outputs.get(identity)
        assert receipt and receipt[0] > index and receipt[1]['payload'].get('output') == ''
        token, _ = core.delivery_token(delivered['payload'])
        assert args.get('message') == token
        assert core.instant(event['timestamp']) <= core.instant(delivered['timestamp'])
        assert core.instant(event['timestamp']) <= core.instant(receipt[1]['timestamp'])
        signatures.append({'call_id': identity, 'token_sha256': core.digest(token.encode()),
                           'receipt_timestamp': receipt[1]['timestamp']})
    return signatures


def close(run, error, agent_path=None):
    folder, out, metadata = allocated_paths(run)
    binding_path = out / 'actor-binding.json'
    if binding_path.exists():
        binding = legacy.read(binding_path)
        if agent_path is not None:
            assert binding['agent_path'] == agent_path
        agent_path = binding['agent_path']
    else:
        assert isinstance(agent_path, str) and agent_path.startswith('/root/')
        previous_paths = old.paths
        old.paths = allocated_paths
        try:
            binding = old.failure_only_binding(run, agent_path)
        finally:
            old.paths = previous_paths
    source = find_session(agent_path)
    assert str(source) == binding['native_source']
    raw = source.read_bytes()
    # Preserve exactly the bytes observed, including a partial final line. No
    # missing cost is converted to zero and no malformed source becomes terminal.
    prefix = out / 'failure-native-prefix-v2.jsonl'
    if not prefix.exists():
        with prefix.open('xb') as stream:
            stream.write(raw)
    first_intent = out / 'failure-close-first-intent-v2.json'
    original = {'run_id': run, 'started_at': metadata['started_at'], 'native_source': str(source),
                'prefix_sha256': core.digest(prefix.read_bytes()), 'prefix_bytes': prefix.stat().st_size,
                'first_error': {'type': type(error).__name__, 'message': str(error)}, 'observed_at': time.time()}
    if first_intent.exists():
        original = legacy.read(first_intent)
    else:
        atomic_json(first_intent, original, exclusive=True)
    prefix_raw = prefix.read_bytes()
    parent_source = Path(binding['parent_source'])
    parent_raw = parent_source.read_bytes()
    attempt = {'error': {'type': type(error).__name__, 'message': str(error)},
               'native_sha256': core.digest(raw), 'native_bytes': len(raw),
               'parent_sha256': core.digest(parent_raw), 'observed_at': time.time()}
    number = len(list(out.glob('failure-close-observation-v2-*.json')))
    atomic_json(out / f'failure-close-observation-v2-{number:04d}.json', attempt, exclusive=True)
    observed = None
    try:
        assert original['run_id'] == run and original['started_at'] == metadata['started_at']
        assert original['native_source'] == str(source)
        assert core.digest(prefix_raw) == original['prefix_sha256'] and len(prefix_raw) == original['prefix_bytes']
        assert raw.startswith(prefix_raw), 'Native source no longer extends original failure prefix'
        events = core.parse(raw)
        headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
        assert len(headers) == 1 and events[0].get('type') == 'session_meta'
        header = headers[0]
        assert header['id'] == binding['native_session_id'] and header['agent_path'] == agent_path
        assert header['parent_thread_id'] == binding['parent_thread_id']
        observed = old.failure_snapshot(raw, agent_path, str(source))
        terminal = terminal_graph(events)
        assert terminal, 'Live, incomplete or out-of-turn native activity'
        delivery = parent_gate(parent_raw, binding, events)
        # The coordinator invokes close synchronously instead of delivering any
        # further followup. Recheck both actual sources before touching product.
        assert source.read_bytes() == raw, 'Native append during terminal check'
        assert parent_gate(parent_source.read_bytes(), binding, events) == delivery
    except Exception as native_error:
        terminal = False
        if observed is None:
            observed = {'native_source': str(source), 'source_sha256': core.digest(raw),
                        'source_bytes': len(raw), 'usage': None, 'native_completion_observed': False,
                        'metrics_unavailable': ['token_usage', 'qualified_model', 'billable_currency']}
        observed['failure_snapshot_reason'] = str(native_error)
    value = {'run_id': run, 'status': 'evaluation_error' if terminal else 'awaiting_actor_terminal',
             'actor_allocated': True, 'actor_retried': False, 'started_at': metadata['started_at'],
             'first_error': original['first_error'], 'failure_first_intent_sha256': core.digest(first_intent.read_bytes()),
             'observation': attempt, 'usage': observed, 'behavior_pass': None, 'software_pass': None, 'overall_pass': None,
             'comparison_eligible': False, 'lifecycle_errors': [], 'superiority_proven': False,
             'complete_final_cost': False, 'primary_confirmation_reuse_allowed': False,
             'actor_terminal_observed': terminal, 'actor_control': False}
    if not terminal:
        atomic_json(out / 'failure-close-pending-v2.json', value)
        return value
    try:
        old.stop_owned(metadata)
        assert source.read_bytes() == raw, 'Native append after product stop'
        assert parent_gate(parent_source.read_bytes(), binding, events) == delivery
    except Exception as fence_error:
        value.update(status='awaiting_actor_terminal', actor_terminal_observed=False)
        value['lifecycle_errors'].append({'type': type(fence_error).__name__, 'message': str(fence_error)})
        atomic_json(out / 'failure-close-pending-v2.json', value)
        return value
    observed['native_completion_observed'] = True
    observed['terminal_graph_verified'] = True
    # Qualified model evidence remains as originally observed. Terminal graph
    # completion does not repair invalid model/input/transport qualification.
    terminal_path, usage_path = out / 'terminal-native.jsonl', out / 'native-usage-v4.json'
    if terminal_path.exists():
        assert terminal_path.read_bytes() == raw
    else:
        with terminal_path.open('xb') as stream:
            stream.write(raw)
    if usage_path.exists():
        previous = legacy.read(usage_path)
        assert previous['source_sha256'] == core.digest(raw)
        observed = previous
        value['usage'] = observed
    else:
        atomic_json(usage_path, observed, exclusive=True)
    assert not (out / 'grade.json').exists(), 'Existing grade must be preserved'
    atomic_json(out / 'grade.json', value, exclusive=True)
    try:
        legacy.diagnostics.preserve_tmp(out, metadata['container'], 'failure-close')
        value['product_cleanup'] = legacy.remove_owned(metadata)
    except Exception as cleanup_error:
        value['lifecycle_errors'].append({'type': type(cleanup_error).__name__, 'message': str(cleanup_error)})
    value['finished_at'] = time.time()
    value['allocation_through_product_cleanup_seconds'] = value['finished_at'] - metadata['started_at']
    atomic_json(out / 'grade.json', value)
    return value
