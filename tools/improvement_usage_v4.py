"""Atomic native snapshots and session-ID membership for future cohorts.

This does not discover workers: the runner must first attest a complete allocation
registry. Existing frozen development usage receipts are not replaced.
"""
import hashlib,json
from collect import find_session
from improvement_usage_v1 import aggregate as prior_aggregate

def usage(agent_path):
    source=find_session(agent_path);raw=source.read_bytes()
    return snapshot(raw,agent_path,str(source))

def snapshot(raw,agent_path,source):
    if not raw.endswith(b'\n'):raise ValueError('Incomplete native record; observe same session again')
    events=[json.loads(line) for line in raw.splitlines()]
    headers=[e['payload'] for e in events if e.get('type')=='session_meta']
    if len(headers)!=1 or headers[0].get('agent_path')!=agent_path or not headers[0].get('id'):raise ValueError('Native session identity unavailable or mismatched')
    models=[];ends=[];counts=[];opened=set();finished=set();contexted=set();invalid_turn_identity=False
    for e in events:
        p=e.get('payload',{})
        if e.get('type')=='turn_context' or e.get('type')=='event_msg' and p.get('type')=='task_started':
            turn=p.get('turn_id')
            if not isinstance(turn,str) or not turn: invalid_turn_identity=True
            else:
                if turn in finished:invalid_turn_identity=True
                opened.add(turn)
                if e.get("type")=="turn_context":contexted.add(turn)
        if e.get('type')=='event_msg' and p.get('type')=='task_complete':
            turn=p.get('turn_id')
            if turn not in opened or turn in finished:invalid_turn_identity=True
            else:finished.add(turn)
        if e.get('type')=='turn_context':models.append({k:p.get(k) for k in ('model','effort')})
        if e.get('type')=='event_msg' and p.get('type')=='token_count':counts.append(p.get('info',{}))
        if e.get('type')=='event_msg' and p.get('type')=='task_complete':ends.append({k:p.get(k) for k in ('turn_id','duration_ms','started_at','completed_at')})
    if not models or any(m!={'model':'gpt-6.1-sol','effort':'medium'} for m in models):raise ValueError('Unqualified model or reasoning')
    terminal=bool(opened) and not invalid_turn_identity and opened==finished and opened==contexted
    total=counts[-1].get('total_token_usage') if counts else None
    return {'agent_path':agent_path,'native_session_id':headers[0]['id'],'parent_thread_id':headers[0].get('parent_thread_id'),'native_source':str(source),'source_sha256':hashlib.sha256(raw).hexdigest(),'source_bytes':len(raw),'models':models,'completions':ends,'usage':total,'native_completion_observed':terminal,'opened_turn_ids':sorted(opened),'completed_turn_ids':sorted(finished),'turn_identity_invalid':invalid_turn_identity,'status':'completed_observed_turns' if terminal else 'incomplete_or_interrupted_native_prefix','metrics_unavailable':[] if total is not None else ['token_usage'],'billable_currency_observed':False,'scope':'One atomic native prefix; entire fresh product session including failure. Complete allocation registry required separately.'}

def aggregate(records,registry):
    if len({r['agent_path'] for r in registry})!=len(registry) or len({r['native_session_id'] for r in registry})!=len(registry):raise ValueError('Duplicate allocated path or native session')
    expected={r['agent_path']:r for r in registry};seen_ids=set()
    for record in records:
        row=expected.get(record['agent_path'])
        if row is None or any(record.get(k)!=row.get(k) for k in ('native_session_id','role')):raise ValueError('Unexpected or mismatched allocated session')
        identity=record['native_session_id']
        if identity in seen_ids:raise ValueError('Duplicate actual native session')
        seen_ids.add(identity)
    result=prior_aggregate(records,list(expected))
    for role,group in result.items():
        group['native_session_ids_unique']=True;group['registry_membership_exact']=True
        group['all_attempts_included']=None
        group['allocation_registry_completeness_attested']=False
        group['all_registered_sessions_terminal']=all(r['native_completion_observed'] for r in records if r['role']==role)
        group['cost_scope']='Observed native prefix totals for supplied registry only; full cost completeness unproven'
    return result
