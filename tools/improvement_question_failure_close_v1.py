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
    groups = {'task_started': [], 'context': [], 'task_complete': []}
    finals = {}
    for index, event in enumerate(events):
        payload = event['payload']
        if event.get('type') == 'turn_context':
            groups['context'].append((index, payload))
        elif event.get('type') == 'event_msg' and payload.get('type') in {'task_started', 'task_complete'}:
            groups[payload['type']].append((index, payload))
        elif event.get('type') == 'response_item' and payload.get('type') == 'message' and payload.get('role') == 'assistant' and (
                payload.get('channel') == 'final' or payload.get('phase') == 'final_answer'):
            identity = core.turn_id(payload)
            if identity in finals:
                return False
            finals[identity] = (index, core.final_text(payload))
    count = len(groups['task_started'])
    if count not in {1, 2} or any(len(rows) != count for rows in groups.values()) or len(finals) != count:
        return False
    seen, last_end = set(), -1
    for rows in zip(groups['task_started'], groups['context'], groups['task_complete']):
        identities = [core.turn_id(payload) for _, payload in rows]
        identity = identities[0]
        if not isinstance(identity, str) or not identity or len(set(identities)) != 1 or identity in seen or identity not in finals:
            return False
        seen.add(identity)
        start, context, end = [index for index, _ in rows]
        final_index, text = finals[identity]
        if not last_end < start < context < final_index < end or rows[-1][1].get('last_agent_message') != text:
            return False
        last_end = end
    return True


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
    prefix = out / 'failure-native-prefix-v1.jsonl'
    if not prefix.exists():
        with prefix.open('xb') as stream:
            stream.write(raw)
    events = None
    observed = None
    try:
        events = core.parse(raw)
        header = events[0]['payload']
        assert header['id'] == binding['native_session_id'] and header['agent_path'] == agent_path
        assert header['parent_thread_id'] == binding['parent_thread_id']
        observed = old.failure_snapshot(raw, agent_path, str(source))
        terminal = terminal_graph(events)
    except Exception as native_error:
        terminal = False
        observed = {'native_source': str(source), 'source_sha256': core.digest(raw),
                    'source_bytes': len(raw), 'usage': None, 'native_completion_observed': False,
                    'metrics_unavailable': ['token_usage', 'qualified_model', 'billable_currency'],
                    'failure_snapshot_reason': str(native_error)}
    value = {'run_id': run, 'status': 'evaluation_error' if terminal else 'awaiting_actor_terminal',
             'actor_allocated': True, 'actor_retried': False, 'started_at': metadata['started_at'],
             'first_error': {'type': type(error).__name__, 'message': str(error)},
             'usage': observed, 'behavior_pass': None, 'software_pass': None, 'overall_pass': None,
             'comparison_eligible': False, 'lifecycle_errors': [], 'superiority_proven': False,
             'complete_final_cost': False, 'primary_confirmation_reuse_allowed': False,
             'actor_terminal_observed': terminal, 'actor_control': False}
    if not terminal:
        atomic_json(out / 'failure-close-pending-v1.json', value)
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
        old.stop_owned(metadata)
        legacy.diagnostics.preserve_tmp(out, metadata['container'], 'failure-close')
        value['product_cleanup'] = legacy.remove_owned(metadata)
    except Exception as cleanup_error:
        value['lifecycle_errors'].append({'type': type(cleanup_error).__name__, 'message': str(cleanup_error)})
    value['finished_at'] = time.time()
    value['allocation_through_product_cleanup_seconds'] = value['finished_at'] - metadata['started_at']
    atomic_json(out / 'grade.json', value)
    return value
