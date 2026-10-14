"""Atomic native snapshots and session-ID membership for future cohorts.

This does not discover workers: the runner must first attest a complete allocation
registry. Existing frozen development usage receipts are not replaced.
"""
import hashlib,json
from collect import find_session
from improvement_usage_v1 import aggregate as prior_aggregate

def usage(agent_path):
    source=find_session(agent_path);raw=source.read_bytes()
    if not raw.endswith(b'\n'):raise ValueError('Incomplete native record; observe same session again')
    events=[json.loads(line) for line in raw.splitlines()]
    headers=[e['payload'] for e in events if e.get('type')=='session_meta']
    if len(headers)!=1 or headers[0].get('agent_path')!=agent_path or not headers[0].get('id'):raise ValueError('Native session identity unavailable or mismatched')
    models=[];ends=[];counts=[]
    for e in events:
        p=e.get('payload',{})
        if e.get('type')=='turn_context':models.append({k:p.get(k) for k in ('model','effort')})
        if e.get('type')=='event_msg' and p.get('type')=='token_count':counts.append(p.get('info',{}))
        if e.get('type')=='event_msg' and p.get('type')=='task_complete':ends.append({k:p.get(k) for k in ('turn_id','duration_ms','started_at','completed_at')})
    if not models or any(m!={'model':'gpt-6.1-sol','effort':'medium'} for m in models):raise ValueError('Unqualified model or reasoning')
    total=counts[-1].get('total_token_usage') if counts else None
    return {'agent_path':agent_path,'native_session_id':headers[0]['id'],'parent_thread_id':headers[0].get('parent_thread_id'),'native_source':str(source),'source_sha256':hashlib.sha256(raw).hexdigest(),'source_bytes':len(raw),'models':models,'completions':ends,'usage':total,'native_completion_observed':bool(ends),'status':'completed' if ends else 'no_native_completion_observed','metrics_unavailable':[] if total is not None else ['token_usage'],'billable_currency_observed':False,'scope':'One atomic native prefix; entire fresh product session including failure. Complete allocation registry required separately.'}

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
    for group in result.values():group['native_session_ids_unique']=True;group['registry_membership_exact']=True
    return result
