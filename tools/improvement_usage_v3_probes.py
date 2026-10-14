import copy,json,hashlib
from pathlib import Path
import improvement_usage_v3 as q
ROOT=Path(__file__).resolve().parents[1]
path='/test/actor';header={'type':'session_meta','payload':{'id':'session-one','agent_path':path}}
def context(t):return {'type':'turn_context','payload':{'turn_id':t,'model':'gpt-6.1-sol','effort':'medium'}}
count={'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':{'input_tokens':100,'cached_input_tokens':80,'output_tokens':10,'total_tokens':110}}}}
end={'type':'event_msg','payload':{'type':'task_complete','turn_id':'one'}}
def snap(events):return q.snapshot(('\n'.join(json.dumps(e) for e in events)+'\n').encode(),path,'/test/native.jsonl')
checks=[]
def check(name,yes):
 if not yes:raise AssertionError(name)
 checks.append(name)
one=snap([header,context('one'),count,end]);check('one_terminal_turn',one['native_completion_observed'])
active=snap([header,context('one'),count,end,context('two')]);check('old_completion_active_second_not_terminal',not active['native_completion_observed'] and active['usage']['total_tokens']==110)
second=copy.deepcopy(end);second['payload']['turn_id']='two';done=snap([header,context('one'),count,end,context('two'),second]);check('both_turns_terminal',done['native_completion_observed'])
check('out_of_order_completion_not_terminal',not snap([header,end,context('one'),count])['native_completion_observed'])
check('duplicate_completion_not_terminal',not snap([header,context('one'),count,end,end])['native_completion_observed'])
record=dict(active,role='product');registry=[{k:record[k] for k in ['agent_path','native_session_id','role']}];out=q.aggregate([record],registry)['product'];check('unattested_registry_not_all_attempts',out['all_attempts_included'] is None and out['registry_membership_exact'] is True)
check('active_session_observed_usage_included',out['usage']['total_tokens']==110 and out['native_completions']==0 and out['all_registered_sessions_terminal'] is False)
unknown=dict(record,usage=None);check('unknown_not_zero',q.aggregate([unknown],registry)['product']['usage']['total_tokens'] is None)
for label,records,reg in [('duplicate_actual',[record,record],registry),('missing_actual',[],registry)]:
 try:q.aggregate(records,reg)
 except ValueError:checks.append(label)
 else:raise AssertionError(label)
real=q.usage('/root/improvement_d02_c0_1');check('actual_completed_native_snapshot',real['native_completion_observed'] and len(real['opened_turn_ids'])==1)
report={'status':'pure_probes_pass_not_actor_registered','checks':checks,'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'tools/improvement_usage_v3.py',ROOT/'tools/improvement_usage_v1.py']},'existing_receipts_changed':False,'limitations':['No worker discovery or allocation registry completeness attestation implemented.','Prefix totals are observed usage, not proof of final whole-cohort cost.']}
(ROOT/'results/improvement-v1/session-usage-v3-probes.json').write_text(json.dumps(report,indent=2));print(len(checks),'checks pass')
