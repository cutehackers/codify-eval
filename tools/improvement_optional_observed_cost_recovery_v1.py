"""Additive observed-counter recovery for one bootstrap-null snapshot only.

Never changes native bytes or historical outcomes. Recorded usage is not a
manifest of every backend request, currency, or whole final research cost.
Caller retains original allocation, route, terminal and cleanup authority.
"""
import copy
from contextlib import contextmanager
import hashlib

import improvement_optional_member_cost_v2 as original
import improvement_optional_lifecycle_v5 as lifecycle

BASE = original.usage_members
core = original.strict.core
require = core.require
FIELDS = original.usage.FIELDS


def counters(value):
    require(isinstance(value, dict) and set(value) == set(FIELDS), 'Exact six-field native counters required')
    return original.usage.counters(value)


def started(events):
    rows = [e['payload'] for e in events if e.get('type') == 'event_msg'
            and e['payload'].get('type') == 'task_started']
    require(len(rows) == 1, 'One original optional turn required for numeric recovery')
    return rows[0]


def recover(raw, member, proof, root_raw):
    require(isinstance(raw, bytes) and raw.endswith(b'\n')
            and len(raw) == member['raw_bytes']
            and hashlib.sha256(raw).hexdigest() == member['raw_sha256'],
            'Original bound full member prefix required')
    events = core.parse(raw)
    original.strict.finite(events)
    require(all(type(e.get('ordinal')) is int and e['ordinal'] == i for i,e in enumerate(events)),
            'Original complete native ordinal sequence required')
    headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
    require(len(headers) == 1 and events[0].get('type') == 'session_meta', 'Unique original native header required')
    header = headers[0]
    root_events = core.parse(root_raw)
    root_header = root_events[0]['payload']
    start, root_start = started(events), started(root_events)
    root_turn = root_start.get('root_turn_id')
    path = member['agent_path']
    parent = proof['coordinator_native_id'] if path == proof['root_path'] else root_header['id']
    require(header.get('id') == member['native_session_id'] and header.get('agent_path') == path
            and header.get('parent_thread_id') == parent
            and header.get('session_id') == proof['coordinator_native_id']
            and root_header.get('id') == next(m['native_session_id'] for m in proof['members']
                                             if m['agent_path'] == proof['root_path']),
            'Numeric actor/thread/enclosing-session binding changed')
    turn = start.get('turn_id')
    require(isinstance(turn, str) and bool(turn) and isinstance(root_turn, str) and bool(root_turn)
            and start.get('root_turn_id') == root_turn, 'Native original turn attribution required')
    attribution = start.get('turn_attribution')
    expected_parent_turn = root_turn if path == proof['root_path'] else root_start['turn_id']
    require(isinstance(attribution, dict) and attribution.get('turn_id') == turn
            and attribution.get('root_turn_id') == root_turn
            and attribution.get('parent_turn_id') == expected_parent_turn
            and attribution.get('initiating_agent_path') == path.rsplit('/',1)[0],
            'Original parent/child turn attribution changed')
    start_indexes = [i for i,e in enumerate(events) if e.get('type') == 'event_msg'
                     and e['payload'].get('type') == 'task_started']
    context_indexes = [i for i,e in enumerate(events) if e.get('type') == 'turn_context']
    contexts = [events[i]['payload'] for i in context_indexes]
    completes = [i for i,e in enumerate(events) if e.get('type') == 'event_msg'
                 and e['payload'].get('type') == 'task_complete']
    require(len(contexts) == 1 and contexts[0].get('model') == 'gpt-6.1-sol'
            and contexts[0].get('effort') == 'medium' and len(completes) == 1
            and completes[0] == len(events)-1
            and events[-1]['payload'].get('turn_id') == turn
            and events[-1]['payload'].get('root_turn_id') == root_turn,
            'Original completed fixed-model turn required for recovery')
    require(lifecycle.turn_id(contexts[0]) == turn
            and contexts[0].get('root_turn_id') == root_turn,
            'Context turn/root attribution must match original start')
    settings = contexts[0].get('collaboration_mode',{}).get('settings')
    require(settings is None or (isinstance(settings,dict)
            and settings.get('model') == 'gpt-6.1-sol'
            and settings.get('reasoning_effort') == 'medium'), 'Conflicting native context model settings')
    incoming = [i for i,e in enumerate(events) if e['payload'].get('type') == 'agent_message'
                and e['payload'].get('author') == path.rsplit('/',1)[0]]
    require(len(incoming) == 1 and events[incoming[0]]['payload'].get('recipient') == path
            and lifecycle.turn_id(events[incoming[0]]['payload']) == turn
            and start_indexes[0] < context_indexes[0] < incoming[0],
            'Original start/context/received input ordering required')
    completion = events[-1]['payload']
    finals = [i for i,e in enumerate(events) if e['payload'].get('type') == 'message'
              and e['payload'].get('role') == 'assistant'
              and (e['payload'].get('channel') == 'final' or e['payload'].get('phase') == 'final_answer')]
    if completion.get('error') is None:
        require(len(finals) == 1 and incoming[0] < finals[0] < completes[0]
                and lifecycle.turn_id(events[finals[0]]['payload']) == turn
                and completion.get('last_agent_message') == lifecycle.final_text(events[finals[0]]['payload']),
                'Original normal final and completion must match')
    else:
        error = completion['error']
        require(not finals and isinstance(error,dict) and set(error) == {'message','codex_error_info'}
                and error['codex_error_info'] == 'server_overloaded'
                and isinstance(error['message'],str) and bool(error['message'])
                and 'last_agent_message' in completion and completion['last_agent_message'] is None,
                'Only diagnosed genuine capacity-error terminal may recover observations')
    records = [(i,e['payload']) for i,e in enumerate(events) if e.get('type') == 'token_usage_record']
    require(bool(records), 'Original per-response usage records required')
    counts = [(i,e['payload']) for i,e in enumerate(events) if e.get('type') == 'event_msg'
              and e['payload'].get('type') == 'token_count']
    bad = [(i,p) for i,p in counts if not isinstance(p.get('info'),dict)]
    require(len(bad) == 1 and 'info' in bad[0][1] and bad[0][1]['info'] is None
            and incoming[0] < bad[0][0] < records[0][0],
            'Only one bootstrap-null snapshot before first recorded response may recover')
    generated = [i for i,e in enumerate(events) if e.get('type') == 'response_item'
                 and (e['payload'].get('type') in ('function_call','custom_tool_call','reasoning')
                      or (e['payload'].get('type') == 'message'
                          and e['payload'].get('role') == 'assistant'))]
    require(generated and bad[0][0] < min(generated) < records[0][0],
            'Null snapshot must precede generated responses and recorded usage')
    total = {k:0 for k in FIELDS}
    ids, snapshots = set(), []
    for index,p in records:
        require(p.get('thread_id') == member['native_session_id'] and p.get('turn_id') == turn
                and p.get('root_turn_id') == root_turn and p.get('session_id') == proof['coordinator_native_id'],
                'Response usage attribution changed')
        response = p.get('response_id')
        require(isinstance(response,str) and bool(response) and response not in ids, 'Unique response usage ID required')
        ids.add(response)
        last = counters(p.get('usage'))
        total = {k:total[k]+last[k] for k in FIELDS}
        require(counters(p.get('thread_token_usage')) == total
                and counters(p.get('turn_token_usage')) == total,
                'Every recorded per-response sum must equal thread and turn cumulative')
        snapshots.append((index,dict(total),last,response))
    valid_counts = [(i,p) for i,p in counts if isinstance(p.get('info'),dict)]
    require(bool(valid_counts), 'Actual final valid native counter required')
    for index,p in valid_counts:
        prior = [r for r in snapshots if r[0] < index]
        require(bool(prior), 'Matching prior recorded response required')
        require(counters(p['info'].get('total_token_usage')) == prior[-1][1]
                and counters(p['info'].get('last_token_usage')) == prior[-1][2],
                'Native cumulative/last counter conflicts with recorded response')
    require(all(any(index < count_index and count_index < (snapshots[n+1][0]
                    if n+1 < len(snapshots) else completes[0])
                    for count_index,_ in valid_counts) for n,(index,*_) in enumerate(snapshots)),
            'Each recorded response requires a corroborating counter before the next response')
    last_count = valid_counts[-1][0]
    require(snapshots[-1][0] < last_count < completes[0]
            and all(i < last_count for i,e in enumerate(events) if e.get('type') == 'response_item'),
            'Final native counter must include final response and every response item')
    return {'observed_counter':total,'null_snapshot_indexes':[bad[0][0]],
            'unique_recorded_response_ids':[r[3] for r in snapshots],
            'original_source_sha256':hashlib.sha256(raw).hexdigest(),'original_source_bytes':len(raw),
            'actor_native_id':member['native_session_id'],'turn_id':turn,'root_turn_id':root_turn,
            'enclosing_session_id':proof['coordinator_native_id'],
            'recorded_counter_reconciliation_pass':True,'every_backend_generation_manifest_proven':False,
            'whole_final_cost_qualified':False,'billable_currency_observed':False}


def usage_members(proof, sources, locators):
    value = copy.deepcopy(BASE(proof,sources,locators))
    bound = {m['agent_path']:m for m in proof['members']}
    recovered = []
    for member in value['members']:
        path = member['agent_path']
        if member['usage'] is not None or path not in bound or path not in value['malformed_counter_info_paths']:
            continue
        try:
            evidence = recover(sources[path],bound[path],proof,sources[proof['root_path']])
        except (ValueError,KeyError,TypeError) as error:
            member['observed_counter_recovery_error'] = {'type':type(error).__name__,'message':str(error)}
            continue
        member['original_metric_error'] = member['metric_error']
        member['metric_error'] = None
        member['usage'] = evidence['observed_counter']
        member['observed_counter_recovery'] = evidence
        recovered.append(path)
    unknown = [m['agent_path'] for m in value['members'] if m['usage'] is None]
    totals = {k:sum(m['usage'][k] for m in value['members'] if m['usage'] is not None) for k in FIELDS}
    value.update({'unknown_usage_paths':unknown,'observed_prefix_totals':None
                  if unknown or value['pending_allocation_slots'] else totals,
                  'known_valid_prefix_category_totals':totals,
                  'known_valid_prefix_totals_are_partial':bool(unknown or value['pending_allocation_slots']),
                  'recovered_bootstrap_null_counter_paths':recovered,
                  'whole_final_cost_qualified':False,'complete_final_cost':False,
                  'billable_currency_observed':False,'every_backend_generation_manifest_proven':False,
                  'comparison_eligible':False,'superiority_proven':False})
    return value


@contextmanager
def decoder():
    """Scoped only by a prospectively admitted caller; all hooks restored."""
    before = original.usage_members
    require(before is BASE, 'Unexpected or nested numeric decoder')
    original.usage_members = usage_members
    try:
        yield
    finally:
        original.usage_members = before
