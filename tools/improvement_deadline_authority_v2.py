"""Pure current-parent interruption authority. Not an installed cleanup path.

The caller must separately commit no more delivery and fence this evidence again
before and after stopping its owned product. Actual interrupted receipt/status
formats and cleanup remain unqualified until a prospective native control.
"""
import json
import math

import improvement_q01_dialogue_core_v1 as core
from improvement_run_v2 import ActorNotTerminal


def terminal_status(status):
    closed = {'completed', 'failed', 'interrupted', 'shutdown'}
    if isinstance(status, str):
        return status in closed | {'handle_missing'}
    return (isinstance(status, dict) and len(status) == 1
            and next(iter(status)) in closed
            and isinstance(next(iter(status.values())), str))


def authority(raw, binding, deadline):
    core.require(type(deadline) in (int, float) and math.isfinite(deadline), 'Invalid original deadline')
    events = core.parse(raw)
    headers = [e['payload'] for e in events if e.get('type') == 'session_meta']
    core.require(len(headers) == 1 and headers[0]['id'] == binding['parent_thread_id']
                 and not headers[0].get('parent_thread_id'), 'Original root parent required')
    target = binding['agent_path']
    calls, outputs = [], {}
    for index, event in enumerate(events):
        p = event['payload']
        if p.get('type') == 'function_call':
            args = core.decode(p['arguments']) if isinstance(p.get('arguments'), str) else p.get('arguments')
            if core.route(p, 'collaboration', 'list_agents'):
                kind = 'inventory'
            elif any(core.route(p, 'collaboration', name) for name in ('interrupt_agent', 'followup_task', 'send_message')):
                core.require(isinstance(args, dict), 'Malformed actor operation')
                if args.get('target') not in (target, target.rsplit('/', 1)[-1]):
                    continue
                kind = 'interrupt' if core.route(p, 'collaboration', 'interrupt_agent') else 'delivery'
            else:
                continue
            core.require(isinstance(p.get('call_id'), str) and p['call_id'], 'Missing operation call ID')
            calls.append((index, event, kind, args))
    identities = {e['payload']['call_id'] for _, e, _, _ in calls}
    for index, event in enumerate(events):
        p = event['payload']
        if p.get('type') in ('function_call_output', 'custom_tool_call_output') and p.get('call_id') in identities:
            identity = p.get('call_id')
            core.require(identity not in outputs, 'Duplicate tool receipt')
            outputs[identity] = (index, event)
    core.require(len({e['payload']['call_id'] for _, e, _, _ in calls}) == len(calls), 'Duplicate operation ID')
    interruptions = [(i, e, a) for i, e, k, a in calls if k == 'interrupt'
                     and core.instant(e['timestamp']).timestamp() >= deadline]
    core.require(bool(interruptions), 'Actual same-actor original-deadline interrupt required')
    index, interrupt, args = interruptions[-1]
    core.require(args == {'target': target}, 'Exact bound interrupt target required')
    identity = interrupt['payload']['call_id']
    receipt = outputs.get(identity)
    core.require(receipt is not None and receipt[0] > index, 'Interrupt receipt pending')
    result = core.decode(receipt[1]['payload']['output'])
    core.require(isinstance(result, dict) and set(result) == {'previous_status'}, 'Interrupt must succeed')
    core.require(core.instant(receipt[1]['timestamp']) >= core.instant(interrupt['timestamp']), 'Interrupt receipt clock reversed')
    core.require(not any(k == 'delivery' for i, _, k, _ in calls if i > index), 'Actor delivery after interruption')
    later = [(i, e, k, a) for i, e, k, a in calls if i > receipt[0]]
    core.require(not any(k in {'delivery', 'interrupt'} for _, _, k, _ in later), 'Actor activity after interruption')
    inventories = [(i, e, a) for i, e, k, a in later if k == 'inventory']
    if not inventories:
        raise ActorNotTerminal('Current unfiltered terminal inventory required')
    inv_index, inventory, inv_args = inventories[-1]
    core.require(inv_args == {}, 'Latest inventory must be unfiltered')
    inv_id = inventory['payload']['call_id']
    inv_receipt = outputs.get(inv_id)
    if inv_receipt is None:
        raise ActorNotTerminal('Latest inventory receipt pending')
    core.require(inv_receipt[0] > inv_index, 'Inventory receipt order reversed')
    value = core.decode(inv_receipt[1]['payload']['output'])
    core.require(isinstance(value, dict) and isinstance(value.get('agents'), list), 'Malformed inventory')
    agents = value['agents']
    core.require(all(isinstance(a, dict) and isinstance(a.get('agent_name'), str) for a in agents), 'Malformed actor inventory')
    core.require(len({a['agent_name'] for a in agents}) == len(agents), 'Duplicate actor inventory')
    selected = [a for a in agents if a['agent_name'] == target]
    status = selected[0].get('agent_status') if selected else 'handle_missing'
    if not terminal_status(status):
        raise ActorNotTerminal('Latest actual actor inventory remains live or unknown')
    core.require(core.instant(inv_receipt[1]['timestamp']) >= core.instant(inventory['timestamp'])
                 >= core.instant(receipt[1]['timestamp']), 'Terminal inventory clock reversed')
    ledger = [interrupt, receipt[1]]
    for _, event, _, _ in later:
        ledger.append(event)
        output = outputs.get(event['payload']['call_id'])
        if output is not None:
            ledger.append(output[1])
    return {'interrupt_call_id': identity, 'terminal_poll_call_id': inv_id,
            'observed_status': status, 'observed_at': inv_receipt[1]['timestamp'],
            'relevant_parent_ledger_sha256': core.digest(json.dumps(ledger, sort_keys=True, allow_nan=False).encode()),
            'cleanup_authorized': False}
