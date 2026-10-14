"""Owned-product deadline closure. Prospective integration, not qualified yet.

The root must commit no more delivery BEFORE interrupting the original actor.
No source guard, timeout, or previous_status alone permits product removal.
"""
import math
from pathlib import Path
import time

import improvement_deadline_authority_v3 as parser
import improvement_question_failure_close_v4 as normal
from improvement_software_artifacts_v3 import atomic_json

ROOT, core, legacy = normal.ROOT, normal.core, normal.legacy
PHASE = 'pilot-fresh-question-v6'
COMMIT = 'deadline-no-more-delivery-v1.json'
COMMIT_PARENT = 'deadline-commit-parent-prefix-v1.jsonl'
COMMIT_CHILD = 'deadline-commit-child-prefix-v1.jsonl'
AUTHORITY = 'deadline-coordinator-authority-v1.json'


def paths(run):
    previous = normal.PHASE
    normal.PHASE = PHASE
    try:
        return normal.allocated_paths(run)
    finally:
        normal.PHASE = previous


def child_identity(raw, binding):
    events = core.parse(raw)
    headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
    assert len(headers) == 1 and events[0].get('type') == 'session_meta'
    header = headers[0]
    assert header['id'] == binding['native_session_id']
    assert header['agent_path'] == binding['agent_path']
    assert header['parent_thread_id'] == binding['parent_thread_id']
    return events


def commitment(metadata, binding, parent_raw, child_raw, now):
    started = metadata['started_at']
    assert type(started) in (int, float) and math.isfinite(started)
    assert type(now) in (int, float) and math.isfinite(now) and now >= started + 1200
    assert metadata['run_id'] == binding['run_id']
    events = core.parse(parent_raw)
    headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
    assert len(headers) == 1 and headers[0]['id'] == binding['parent_thread_id']
    assert not headers[0].get('parent_thread_id')
    child_identity(child_raw, binding)
    return {'run_id': metadata['run_id'], 'started_at': started,
            'original_deadline': started + 1200, 'binding': binding,
            'no_more_delivery': True, 'committed_at': now,
            'parent_prefix_sha256': core.digest(parent_raw), 'parent_prefix_bytes': len(parent_raw),
            'child_prefix_sha256': core.digest(child_raw), 'child_prefix_bytes': len(child_raw),
            'comparison_eligible': False, 'full_runtime_qualified': False}


def evidence_gate(metadata, binding, child_raw, parent_raw, value, committed_parent, committed_child):
    """Pure current-source fence, also used before every product mutation."""
    assert value['run_id'] == metadata['run_id'] and value['binding'] == binding
    assert value['started_at'] == metadata['started_at']
    assert value['original_deadline'] == metadata['started_at'] + 1200
    assert value['no_more_delivery'] is True
    assert core.digest(committed_parent) == value['parent_prefix_sha256']
    assert len(committed_parent) == value['parent_prefix_bytes']
    assert parent_raw.startswith(committed_parent), 'Parent no longer extends commitment prefix'
    assert core.digest(committed_child) == value['child_prefix_sha256']
    assert len(committed_child) == value['child_prefix_bytes']
    assert child_raw.startswith(committed_child), 'Child no longer extends commitment prefix'
    assert type(value['committed_at']) in (int, float) and math.isfinite(value['committed_at'])
    assert value['committed_at'] >= value['original_deadline']
    events = core.parse(parent_raw)
    suffix = events[len(core.parse(committed_parent)):]
    # Bind the actual interrupt to a tool call appended AFTER the immutable
    # no-more-delivery commitment, not a previously interrupted actor.
    interrupts = [e for e in suffix if e['payload'].get('type') == 'function_call'
                  and core.route(e['payload'], 'collaboration', 'interrupt_agent')
                  and core.decode(e['payload']['arguments']) == {'target': binding['agent_path']}]
    assert interrupts and core.instant(interrupts[-1]['timestamp']).timestamp() >= value['committed_at']
    # A delivery issued after commitment but BEFORE interrupt also violates it.
    for event in suffix:
        p = event['payload']
        if p.get('type') == 'function_call' and any(core.route(p, 'collaboration', name)
                                                for name in ('followup_task', 'send_message')):
            args = core.decode(p['arguments'])
            assert args.get('target') not in (binding['agent_path'], binding['agent_path'].rsplit('/', 1)[-1]), 'Delivery after commitment'
    child_events = child_identity(child_raw, binding)
    delivery = normal.parent_gate(parent_raw, binding, child_events)
    # This cleanup contract accepts the existing one/two-turn followup channel.
    # A separate send_message delivery is not silently treated as a followup.
    for event in events:
        p = event['payload']
        if p.get('type') == 'function_call' and core.route(p, 'collaboration', 'send_message'):
            args = core.decode(p['arguments'])
            assert args.get('target') not in (binding['agent_path'], binding['agent_path'].rsplit('/', 1)[-1]), 'Unsupported actor message delivery'
    result = parser.authority(parent_raw, binding, value['original_deadline'])
    return {'binding': binding, 'started_at': metadata['started_at'],
            'commitment': value, 'actor_native_sha256': core.digest(child_raw),
            'actor_native_bytes': len(child_raw), 'terminal_inventory': result,
            'parent_delivery': delivery,
            'no_more_delivery': True, 'cleanup_authorized': True}


def bind(run, actor):
    _, out, _ = paths(run)
    previous = normal.old.paths
    normal.old.paths = paths
    try:
        binding = normal.old.failure_only_binding(run, actor)
    finally:
        normal.old.paths = previous
    assert binding['run_id'] == run
    return out, binding


def commit(run, actor):
    _, out, metadata = paths(run)
    assert not (out / 'grade.json').exists(), 'Existing outcome must be preserved'
    _, binding = bind(run, actor)
    child_raw = Path(binding['native_source']).read_bytes()
    child_identity(child_raw, binding)
    parent_raw = Path(binding['parent_source']).read_bytes()
    value = commitment(metadata, binding, parent_raw, child_raw, time.time())
    assert not any((out / name).exists() for name in (COMMIT, COMMIT_PARENT, COMMIT_CHILD))
    with (out / COMMIT_PARENT).open('xb') as stream:
        stream.write(parent_raw)
    with (out / COMMIT_CHILD).open('xb') as stream:
        stream.write(child_raw)
    atomic_json(out / COMMIT, value, exclusive=True)
    return value


def current(out, metadata, binding):
    child = Path(binding['native_source']).read_bytes()
    parent = Path(binding['parent_source']).read_bytes()
    value = evidence_gate(metadata, binding, child, parent, legacy.read(out / COMMIT),
                          (out / COMMIT_PARENT).read_bytes(), (out / COMMIT_CHILD).read_bytes())
    return value, child, parent


def authorize(run, actor):
    _, out, metadata = paths(run)
    _, binding = bind(run, actor)
    value, child, parent = current(out, metadata, binding)
    assert Path(binding['native_source']).read_bytes() == child, 'Child changed during authorization'
    assert current(out, metadata, binding)[0] == value, 'Authority changed during authorization'
    atomic_json(out / AUTHORITY, value, exclusive=True)
    return value


def fence(out, metadata, binding, expected):
    value, raw, parent = current(out, metadata, binding)
    assert value == expected, 'Current actor or parent authority changed'
    assert Path(binding['native_source']).read_bytes() == raw, 'Child append during fence'
    return raw, parent


def require_delivery_open(run):
    """Prospective allocator must call this before stage/dispatch/followup."""
    out = ROOT / 'results' / run
    assert not any((out / name).exists() for name in (COMMIT, COMMIT_PARENT, COMMIT_CHILD, AUTHORITY)), 'Coordinator has committed no more delivery'


def verify_closed(out, metadata):
    """Next allocation gate for this version, without inventing completion."""
    out = Path(out)
    value = legacy.read(out / 'grade.json')
    assert value['run_id'] == metadata['run_id'] and value['started_at'] == metadata['started_at']
    assert value['status'] == 'fail' and value['deadline_aborted'] is True
    assert value['actor_allocated'] is True and value['actor_retried'] is False
    assert not value['lifecycle_errors'] and value['product_cleanup']['removed'] is True
    assert value['complete_final_cost'] is False and value['overall_pass'] is False
    binding = legacy.read(out / 'actor-binding.json')
    expected = legacy.read(out / AUTHORITY)
    assert value['deadline_authority_sha256'] == legacy.sha(out / AUTHORITY)
    child = (out / 'terminal-native.jsonl').read_bytes()
    first_parent = (out / 'deadline-parent-native.jsonl').read_bytes()
    last_parent = (out / 'deadline-post-removal-parent-v1.jsonl').read_bytes()
    assert last_parent.startswith(first_parent), 'Post-removal parent lost original prefix'
    for parent in (first_parent, last_parent):
        actual = evidence_gate(metadata, binding, child, parent, legacy.read(out / COMMIT),
                               (out / COMMIT_PARENT).read_bytes(), (out / COMMIT_CHILD).read_bytes())
        assert actual == expected, 'Sealed cleanup authority mismatch'
    usage = legacy.read(out / 'native-usage-v4.json')
    assert usage == value['usage'] and usage['source_sha256'] == core.digest(child)
    receipt = legacy.read(out / 'deadline-closure.json')
    assert receipt['authority'] == expected and receipt['actor_terminal_observed'] is True
    assert receipt['agent_path'] == binding['agent_path'] and receipt['parent_thread_id'] == binding['parent_thread_id']
    assert receipt['parent_prefix_sha256'] == core.digest(first_parent)
    assert receipt['post_removal_parent_sha256'] == core.digest(last_parent)
    assert receipt['child_prefix_sha256'] == core.digest(child)
    assert receipt['post_removal_fence_verified'] is True and receipt['final_cost_complete'] is False
    removed = value['product_cleanup']['finished_at']
    assert type(removed) in (int, float) and math.isfinite(removed)
    assert metadata['started_at'] + 1200 <= removed <= value['finished_at']
    return {'deadline_cleanup_evidence_verified': True, 'native_completion_observed': usage['native_completion_observed'],
            'comparison_eligible': False, 'full_runtime_qualified': False}


def close(run, actor):
    _, out, metadata = paths(run)
    assert time.time() >= metadata['started_at'] + 1200
    assert not (out / 'grade.json').exists(), 'Existing outcome must be preserved'
    _, binding = bind(run, actor)
    expected = legacy.read(out / AUTHORITY)
    raw, parent = fence(out, metadata, binding, expected)
    observed = normal.old.failure_snapshot(raw, actor, binding['native_source'])
    assert observed['source_sha256'] == core.digest(raw)
    # Keep incomplete usage incomplete. Interruption is terminal for cleanup,
    # not a normal model completion and not proof of final billable cost.
    for name, data in [('terminal-native.jsonl', raw), ('deadline-parent-native.jsonl', parent)]:
        with (out / name).open('xb') as stream:
            stream.write(data)
    atomic_json(out / 'native-usage-v4.json', observed, exclusive=True)
    value = {'run_id': run, 'status': 'fail', 'deadline_aborted': True, 'time_limit_exceeded': True,
             'started_at': metadata['started_at'], 'actor_allocated': True, 'actor_retried': False,
             'actor_terminal_observed': True, 'usage': observed, 'complete_final_cost': False,
             'behavior_pass': False, 'overall_pass': False, 'comparison_eligible': False,
             'full_runtime_qualified': False, 'lifecycle_errors': [],
             'deadline_authority_sha256': legacy.sha(out / AUTHORITY)}
    atomic_json(out / 'grade.json', value, exclusive=True)
    try:
        fence(out, metadata, binding, expected)
        normal.old.stop_owned(metadata)
        fence(out, metadata, binding, expected)
        legacy.diagnostics.preserve_tmp(out, metadata['container'], 'deadline-close-v1')
        fence(out, metadata, binding, expected)
        value['product_cleanup'] = legacy.remove_owned(metadata)
        _, final_parent = fence(out, metadata, binding, expected)
        with (out / 'deadline-post-removal-parent-v1.jsonl').open('xb') as stream:
            stream.write(final_parent)
        atomic_json(out / 'deadline-closure.json', {
            'agent_path': actor, 'parent_thread_id': binding['parent_thread_id'],
            'actor_terminal_observed': True, 'authority': expected,
            'parent_prefix_sha256': legacy.sha(out / 'deadline-parent-native.jsonl'),
            'post_removal_parent_sha256': core.digest(final_parent),
            'child_prefix_sha256': core.digest(raw), 'final_cost_complete': False,
            'post_removal_fence_verified': True}, exclusive=True)
    except Exception as error:
        value['lifecycle_errors'].append({'type': type(error).__name__, 'message': str(error)})
    value['finished_at'] = time.time()
    if value.get('product_cleanup', {}).get('removed') is True:
        value['allocation_through_product_cleanup_seconds'] = value['product_cleanup']['finished_at'] - metadata['started_at']
    atomic_json(out / 'grade.json', value)
    return value
