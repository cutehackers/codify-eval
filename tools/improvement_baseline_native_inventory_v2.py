"""Prospective baseline final inventory with approved one/two-turn decoding.

Caller must separately authenticate the supplied turn contract, native membership,
member completions, exclusive delivery commitment and before/after source fences.
A passing result never authorizes cleanup or qualifies an evaluation.
"""
import json
import re
import math
import improvement_q01_dialogue_core_v1 as core
import improvement_baseline_question_lifecycle_v3 as lifecycle
import improvement_baseline_membership_v1 as membership


def finite(value):
    if isinstance(value, float):
        core.require(math.isfinite(value), 'Nonfinite native JSON number')
    elif isinstance(value, dict):
        for item in value.values(): finite(item)
    elif isinstance(value, list):
        for item in value: finite(item)


def decoded(value):
    result = core.decode(value)
    finite(result)
    return result


def completed_inventory(raw, parent_id, member_completions, inventory_call_id, commitment, root_raw=None, child_sources=None, *, root_lifecycle_contract):
    core.require(type(root_raw) is bytes and type(child_sources) is dict
                 and type(root_lifecycle_contract) is dict
                 and root_lifecycle_contract.get('phase') == 'terminal',
                 'Original root/child sources and terminal turn contract required')
    events = core.parse(raw)
    finite(events)
    core.require(isinstance(parent_id, str) and bool(parent_id), 'Coordinator identity required')
    headers = [e for e in events if e.get('type') == 'session_meta']
    core.require(len(headers) == 1 and events[0] == headers[0], 'Ambiguous coordinator header')
    header = headers[0]['payload']
    core.require(header.get('id') == parent_id and not header.get('parent_thread_id'),
                 'Original coordinator required')
    core.require(isinstance(member_completions, dict) and 1 <= len(member_completions) <= 3,
                 'Require root and at most two workers')
    core.require(all(isinstance(p, str) for p in member_completions), 'Member paths must be strings')
    paths = sorted(member_completions)
    core.require(all(isinstance(p, str) and re.fullmatch(r'/root/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)?', p)
                     for p in paths), 'Invalid member path')
    roots = [p for p in paths if re.fullmatch(r'/root/[A-Za-z0-9_]+', p)]
    core.require(len(roots) == 1, 'Require exact immediate product root')
    root = roots[0]
    core.require(all(p == root or (p.startswith(root + '/') and p.count('/') == root.count('/') + 1)
                     for p in paths), 'Members must be root and immediate workers')
    completions = [core.instant(t) for t in member_completions.values()]
    core.require(isinstance(inventory_call_id, str) and bool(inventory_call_id), 'Inventory ID required')
    expected = {'parent_id': parent_id, 'root_path': root, 'member_paths': paths,
                'inventory_call_id': inventory_call_id, 'parent_sha256': core.digest(raw),
                'parent_bytes': len(raw), 'no_more_delivery': True}
    core.require(isinstance(commitment, dict) and commitment.get('no_more_delivery') is True and json.dumps(commitment, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False),
                 'Exact frozen no-more-delivery commitment required')
    calls, outputs, inventories = {}, {}, []
    for i, e in enumerate(events):
        p = e['payload']
        if p.get('type') in ('function_call', 'custom_tool_call'):
            core.require(e.get('type') == 'response_item', 'Wrong native call event type')
            cid = p.get('call_id')
            core.require(isinstance(cid, str) and cid and cid not in calls, 'Duplicate or missing call ID')
            calls[cid] = (i, e)
            if core.route(p, 'collaboration', 'list_agents'):
                core.require(p.get('type') == 'function_call', 'Wrong inventory call type')
                inventories.append(cid)
        elif p.get('type') in ('function_call_output', 'custom_tool_call_output'):
            core.require(e.get('type') == 'response_item', 'Wrong native receipt event type')
            cid = p.get('call_id')
            core.require(isinstance(cid, str) and cid and cid not in outputs, 'Duplicate or missing receipt ID')
            outputs[cid] = (i, e)
    core.require(bool(inventories) and inventories[-1] == inventory_call_id,
                 'Require latest coordinator inventory')
    ci, call = calls[inventory_call_id]
    p = call['payload']
    core.require(decoded(p['arguments']) == {}, 'Latest inventory must be unfiltered')
    core.require(inventory_call_id in outputs, 'Latest inventory receipt pending')
    oi, receipt = outputs[inventory_call_id]
    core.require(oi > ci and receipt['payload'].get('type') == 'function_call_output',
                 'Inventory receipt type or order changed')
    core.require(max(completions) <= core.instant(call['timestamp']) <= core.instant(receipt['timestamp']),
                 'Inventory must follow every member completion')
    result = decoded(receipt['payload']['output'])
    core.require(isinstance(result, dict) and isinstance(result.get('agents'), list), 'Malformed inventory')
    rows = result['agents']
    core.require(all(isinstance(a, dict) and isinstance(a.get('agent_name'), str) and a['agent_name']
                     for a in rows), 'Malformed inventory row')
    core.require(len({a['agent_name'] for a in rows}) == len(rows), 'Duplicate inventory member')
    relevant = {a['agent_name']: a for a in rows
                if a['agent_name'] == root or a['agent_name'].startswith(root + '/')}
    retired={}
    if root_raw is not None:
        core.require(isinstance(child_sources,dict),'Explicit exact child original sources required')
        _,root_header=membership.source(root_raw,root,parent_id)
        binding={'agent_path':root,'actor_native_id':root_header['id'],'parent_native_id':parent_id}
        origin=membership.native.binding(raw,membership.first_request_prefix(root_raw,'/root'),'/root',root)
        core.require(origin['child_native_id']==root_header['id'],'Original coordinator/root allocation join changed')
        expected_turns=root_lifecycle_contract.get('expected_turns')
        _,root_turns=lifecycle.lifecycle(root_raw,binding,expected_turns,child_sources,
                                       turn_contract=root_lifecycle_contract)
        proof=lifecycle.child_proofs(root_raw,binding,child_sources)
        actual={root:root_turns[-1]['completed_at'],**{p:v['completed_at'] for p,v in proof.items()}}
        core.require(set(actual)==set(member_completions) and
                     all(core.instant(actual[p])==core.instant(member_completions[p]) for p in actual),
                     'Declared member completion differs from original native source')
        core.require(root in relevant and set(relevant)<=set(paths),'Current root missing or unregistered live descendant')
        retired={p:proof[p] for p in set(paths)-set(relevant)}
        core.require(set(retired)<=set(child_sources),'Only original completed children may be absent from live inventory')
    else:
        core.require(child_sources is None,'Missing original root source for retired member validation')
        core.require(set(relevant) == set(paths), 'Current subtree membership mismatch')
    for a in relevant.values():
        status = a.get('agent_status')
        core.require(isinstance(status, dict) and set(status) == {'completed'}
                     and isinstance(status['completed'], str), 'Member not normally completed')
    aliases = {}
    for path in paths:
        for alias in {path, path.rsplit('/', 1)[-1], path.removeprefix('/root/')}:
            aliases.setdefault(alias, set()).add(path)
    for _, (i, e) in calls.items():
        p = e['payload']
        when = core.instant(e['timestamp'])
        if core.route(p, 'collaboration', 'spawn_agent') and when >= max(completions):
            raise ValueError('Allocation after member completion')
        if any(core.route(p, 'collaboration', n) for n in ('followup_task', 'send_message', 'interrupt_agent')):
            args = decoded(p['arguments'])
            core.require(isinstance(args, dict) and isinstance(args.get('target'), str), 'Malformed delivery')
            target = args['target']
            matches = aliases.get(target, {target})
            core.require(len(matches) == 1, 'Ambiguous member delivery target')
            canonical = next(iter(matches))
            if canonical in member_completions:
                completed = core.instant(member_completions[canonical])
                core.require(when < completed, 'Member activity after its completion')
                cid = p['call_id']
                core.require(cid in outputs, 'Member delivery receipt pending')
                di, delivery = outputs[cid]
                core.require(di > i and delivery['payload'].get('type') == 'function_call_output',
                             'Member delivery receipt type or order changed')
                core.require(when <= core.instant(delivery['timestamp']) < completed,
                             'Member delivery receipt not closed before completion')
            elif canonical.startswith(root + '/'):
                core.require(when < max(completions), 'Descendant activity after member completion')
            elif not target.startswith('/') and when >= max(completions):
                raise ValueError('Unresolved relative delivery after member completion')
    return {'verdict': 'pass', 'inventory_call_id': inventory_call_id, 'member_paths': paths,
            'observed_at': receipt['timestamp'], 'current_listed_member_paths':sorted(relevant),
            'original_completed_children_absent_from_live_inventory':retired, 'parent_sha256': core.digest(raw), 'parent_bytes': len(raw),
            'receipt_sha256': core.digest(json.dumps(receipt, sort_keys=True, allow_nan=False).encode()),
            'native_membership_proven': False, 'member_completion_proven': False, 'turn_approval_authenticated': False,
            'exclusive_delivery_enforced': False, 'cleanup_authorized': False,
            'native_qualified': False, 'comparison': False, 'superiority': False}
