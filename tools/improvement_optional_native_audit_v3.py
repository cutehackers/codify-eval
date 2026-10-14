"""Composite native origin, role, integration ordering and prefix-cost audit.

Inputs must be original coordinator-authenticated snapshots. This pure adapter
has no native API, filesystem mutation, cleanup or whole-cost authority. Its
result cannot qualify a comparison without prospective source freeze, continuous
observer, current delivery/source fences, software grading and owned cleanup.
"""
import hashlib
import json
import math
from pathlib import Path

import improvement_optional_broker_v10 as broker

import improvement_optional_membership_v3 as membership
import improvement_optional_routes_v4 as routes
import improvement_optional_member_cost_v2 as cost
import improvement_optional_inventory_v3 as inventory

require=inventory.core.require


def lifecycle_binding(member):
    origin=member['binding']
    require(member['agent_path']==origin['child_path'] and member['native_session_id']==origin['child_native_id'],
            'Native allocation/lifecycle identity changed')
    return {'agent_path':member['agent_path'],'actor_native_id':member['native_session_id'],
            'parent_native_id':origin['parent_native_id']}


def original_ledger(folder,job):
    rows=broker.ledger(folder,job)
    for row in rows:
        directory=Path(folder)/'broker'/job/'actions'/f"{row['number']:06d}"
        intent=broker.original(directory/'intent.json')
        receipt=broker.original(directory/'receipt.json')
        terminal=inventory.decoded(receipt)
        require(terminal['intent_sha256']==hashlib.sha256(intent).hexdigest(),'Original receipt intent changed')
        row.update(finished_at=terminal['finished_at'],intent_sha256=hashlib.sha256(intent).hexdigest(),
                   receipt_sha256=hashlib.sha256(receipt).hexdigest())
    return rows


def dispatch_contract(contract,intent,provision):
    require(contract['job']==intent['job']==provision['job'] and
            contract['agent_path']==intent['agent_path']==provision['agent_path'] and
            contract['request_sha256']==intent['public_request_sha256']==provision['public_request_sha256'],
            'Actual bootstrap contract differs from original prepared dispatch')


def integration_order(root_raw,contract,config,ledger,worker_ends,root_end,released_at):
    integrations=[row for row in ledger if row['request']['op']=='integrate']
    require(len(integrations)==1 and integrations[0]['status']=='completed',
            'One original completed final integration required')
    began=integrations[0].get('started_at');finished=integrations[0].get('finished_at')
    calls={};sessions={};intervals=[]
    for event in inventory.core.parse(root_raw):
        payload=event['payload'];kind=payload.get('type');cid=payload.get('call_id')
        if kind in ('function_call','custom_tool_call') and inventory.core.route(payload,'functions','exec'):
            code=payload.get('input',payload.get('arguments'));poll=routes.poll(code)
            if poll is not None:
                calls[cid]=sessions.get(poll['session_id'])
            elif routes.wrapper(code,contract)['op']=='integrate':
                interval={'start':inventory.core.instant(event['timestamp']).timestamp()}
                intervals.append(interval);calls[cid]=interval
        elif kind in ('function_call_output','custom_tool_call_output') and calls.get(cid) is not None:
            value=routes.result(payload);interval=calls[cid]
            if 'exit_code' in value:
                interval['end']=inventory.core.instant(event['timestamp']).timestamp()
            else:sessions[value['session_id']]=interval
    require(len(intervals)==1 and 'end' in intervals[0],'One original terminal native integration required')
    dispatched=intervals[0]['start'];native_end=intervals[0]['end']
    require(all(type(t) in (int,float) and math.isfinite(t) for t in (began,finished,released_at)) and
            config['started_at']<=dispatched<=began<=released_at<=finished<=native_end<=root_end<config['deadline']
            and all(t<=dispatched for t in worker_ends),
            'Final release outside original integration interval or before native worker completion')
    return True

def audit(config,state,root_intent,worker_intents,coordinator_raw,root_raw,worker_raw_by_path,
          provision,registry_folder,contracts,ledgers,locators,inventory_call_id,commitment):
    proof=membership.reconcile_membership(config,state,root_intent,worker_intents,coordinator_raw,
        root_raw,worker_raw_by_path,provision,registry_folder)
    require(proof['provided_allocation_joins_complete'],'All cumulative allocation joins required for normal closure')
    raw_by_path={proof['root_path']:root_raw,**worker_raw_by_path}
    require(set(contracts)==set(raw_by_path)==set(ledgers)==set(locators),
            'Exact all-member contracts, ledgers and original source locators required')
    actual_members={row['agent_path']:row for row in proof['members']}
    require(set(actual_members)==set(raw_by_path),'Every actual allocated member required')
    route_proofs={};completions={};worker_ends=[]
    for path,member in actual_members.items():
        intent=root_intent if path==proof['root_path'] else worker_intents[contracts[path]['job']]
        dispatch_contract(contracts[path],intent,provision['jobs'][contracts[path]['job']])
        require(membership.registry.encoded(ledgers[path])==membership.registry.encoded(original_ledger(Path(registry_folder).parent,contracts[path]['job'])),
                'Supplied action ledger differs from original intent/terminal receipts')
        raw=raw_by_path[path];events=inventory.core.parse(raw)
        contexts=[e['payload'] for e in events if e['type']=='turn_context']
        require(len(contexts)==1,'Normal optional controls support one original approved turn')
        route_proofs[path]=routes.audit_member(raw,lifecycle_binding(member),contracts[path],
            json.dumps(ledgers[path],allow_nan=False).encode(),
            {'turn_ids':[contexts[0]['turn_id']],'native_sha256':hashlib.sha256(raw).hexdigest(),'approved':True})
        ends=[e['timestamp'] for e in events if e['type']=='event_msg' and e['payload'].get('type')=='task_complete']
        require(len(ends)==1,'One genuine member completion required')
        completions[path]=ends[0]
        if path!=proof['root_path']:worker_ends.append(inventory.core.instant(ends[0]).timestamp())
    require(state.get('integration_release') is not None and not state['active_leases'],'Original registry final release required')
    snapshot=membership.reservation_prefix(registry_folder)
    require(membership.registry.encoded(snapshot['state'])==membership.registry.encoded(state),'Registry changed during composite audit')
    final=inventory.decoded(snapshot['full_events_raw'].splitlines()[-1]);require(final['operation']=='integration_release','Final release event required')
    root_end=inventory.core.instant(completions[proof['root_path']]).timestamp()
    integration_order(root_raw,contracts[proof['root_path']],config,ledgers[proof['root_path']],worker_ends,root_end,final['at'])
    current=inventory.completed_inventory(coordinator_raw,proof['coordinator_native_id'],completions,
                                         inventory_call_id,commitment)
    usage=cost.usage_members(proof,raw_by_path,locators)
    require(usage['all_supplied_member_completions_observed'] and usage['observed_prefix_totals'] is not None,
            'All original completed member usage counters required; unknown never becomes zero')
    return {'membership':proof,'routes':route_proofs,'current_inventory':current,'completions':completions,
            'usage':usage,'integration_after_all_native_worker_completions':True,
            'original_no_more_delivery_commitment':commitment,'observed_native_dimensions_pass':True,
            'native_qualified':False,'whole_final_cost_qualified':False,'cleanup_authorized':False,
            'comparison_eligible':False,'superiority_proven':False}
