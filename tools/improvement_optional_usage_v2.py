"""Whole supplied-member prefix counters, not allocation/route/cost authority.

Registry must later be established from actual native allocations. Currency,
external research cost and whole runtime qualification remain unobserved here.
"""
import json

from improvement_usage_v4 import snapshot

FIELDS=('input_tokens','cached_input_tokens','cache_write_input_tokens',
        'output_tokens','reasoning_output_tokens','total_tokens')


def unique_keys(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate native JSON key: '+key)
        result[key]=value
    return result


def reject_nonfinite(value):
    raise ValueError('Nonfinite native JSON value: '+value)


def counters(value):
    if not isinstance(value,dict) or any(type(value.get(k)) is not int or value[k]<0 for k in FIELDS):
        raise ValueError('Missing/invalid cumulative token counter')
    if (value['cached_input_tokens'] > value['input_tokens'] or
            value['reasoning_output_tokens'] > value['output_tokens'] or
            value['total_tokens'] != value['input_tokens']+value['output_tokens']):
        raise ValueError('Inconsistent cumulative counters or subset double count')
    return {k:value[k] for k in FIELDS}


def summarize(registry, raw_by_path, pending_slots=()):
    """Use last cumulative once/UUID. Missing member/usage makes total unknown."""
    if (not isinstance(registry,list) or not 1<=len(registry)<=3
            or not isinstance(raw_by_path,dict)):
        raise ValueError('Bounded actual member registry required')
    if any(not isinstance(row,dict) or set(row)!={'agent_path','native_session_id','role','source'}
           or any(not isinstance(v,str) or not v for v in row.values()) for row in registry):
        raise ValueError('Invalid member locator')
    paths={row['agent_path'] for row in registry};ids={row['native_session_id'] for row in registry}
    roles=[row['role'] for row in registry]
    if (len(paths)!=len(registry) or len(ids)!=len(registry) or roles.count('root')!=1
            or len(set(roles))!=len(roles) or not set(roles)<={'root','worker1','worker2'}):
        raise ValueError('Duplicate UUID/path/role or missing root')
    if not set(raw_by_path)<=paths:
        raise ValueError('Unregistered native source cannot disappear from membership')
    if (not isinstance(pending_slots,(list,tuple)) or any(s not in ('worker1','worker2') for s in pending_slots)
            or len(set(pending_slots))!=len(pending_slots)):
        raise ValueError('Invalid unknown allocation slots')
    members=[];unknown=[];totals={k:0 for k in FIELDS};all_complete=True
    for row in registry:
        raw=raw_by_path.get(row['agent_path'])
        if raw is None:
            members.append(dict(row,status='native_source_missing',usage=None))
            unknown.append(row['agent_path']);all_complete=False
            continue
        if not isinstance(raw,bytes):raise ValueError('Atomic native bytes required')
        events=[json.loads(line,object_pairs_hook=unique_keys,parse_constant=reject_nonfinite)
                for line in raw.splitlines()]
        value=snapshot(raw,row['agent_path'],row['source'])
        if value['native_session_id']!=row['native_session_id']:
            raise ValueError('Native UUID/registry conflict')
        previous=None;metric_error=None
        for event in events:
            p=event.get('payload',{})
            if event.get('type')=='event_msg' and p.get('type')=='token_count':
                try:
                    current=counters(p.get('info',{}).get('total_token_usage'))
                    if previous and any(current[k]<previous[k] for k in FIELDS):
                        raise ValueError('Cumulative counter moved backwards')
                    previous=current
                except ValueError as error:
                    metric_error=str(error)
                    break
        if previous is None and metric_error is None:metric_error='Token usage unobserved'
        if metric_error:
            previous=None;unknown.append(row['agent_path'])
        else:
            for k in FIELDS:totals[k]+=previous[k]
        all_complete=all_complete and value['native_completion_observed']
        members.append(dict(row,source_sha256=value['source_sha256'],source_bytes=value['source_bytes'],
                            usage=previous,metric_error=metric_error,
                            opened_turn_ids=value['opened_turn_ids'],completed_turn_ids=value['completed_turn_ids'],
                            native_completion_observed=value['native_completion_observed']))
    return {'members':members,'observed_prefix_totals':None if unknown or pending_slots else totals,
            'unknown_usage_paths':unknown,'pending_allocation_slots':list(pending_slots),
            'all_supplied_member_completions_observed':all_complete,
            'distinct_uuid_count':len(ids),'last_cumulative_counted_once_per_uuid':True,
            'cached_input_is_subset_not_added_to_input':True,
            'reasoning_output_is_subset_not_added_to_output':True,
            'allocation_membership_qualified':False,'route_qualified':False,
            'complete_final_cost':False,'billable_currency_observed':False,
            'comparison_eligible':False,'superiority_proven':False,
            'scope':'Supplied product members only; actual native allocation reconciliation and external research ledger required'}
