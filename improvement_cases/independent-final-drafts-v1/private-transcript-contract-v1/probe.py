"""Synthetic contract checks only: no actors, containers, model calls or software re-execution."""
from pathlib import Path
import sys,json,hashlib,copy,re,time
ROOT=Path('/Users/junhyounglee/workspace/codify-eval')
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'tools'))
import improvement_q01_dialogue_core_v1 as core
BASE=ROOT/'improvement_cases/independent-final-drafts-v1'
OUT=Path(__file__).parent
started=time.monotonic()
# Only original case files recorded by previous private software qualification are preserved pins.
qualification_path=ROOT/'results/improvement-v1/independent-final-drafts-v1-qualification-private-v1.json'
qualification=json.loads(qualification_path.read_text())
pins=qualification['source_hashes']
def digest(b):return hashlib.sha256(b).hexdigest()
for name,expected in pins.items():assert digest((BASE/name).read_bytes())==expected
binding={'actor_native_id':'synthetic-actor','parent_native_id':'synthetic-parent','agent_path':'/synthetic-root/worker'}
def stamp(n):return f'2030-01-01T00:00:{n:02d}+00:00'
def event(n,kind,p):return {'timestamp':stamp(n),'type':kind,'payload':p}
def raw(events):return b''.join((json.dumps(e,ensure_ascii=False)+'\n').encode() for e in events)
def header():return event(0,'session_meta',{'id':'synthetic-actor','parent_thread_id':'synthetic-parent','agent_path':binding['agent_path']})
def turn(n,id,text,incoming='synthetic task',extra=()):
 return [event(n,'event_msg',{'type':'task_started','turn_id':id}),event(n+1,'turn_context',{'turn_id':id,'model':'gpt-6.1-sol','effort':'medium'}),event(n+2,'response_item',{'type':'agent_message','turn_id':id,'author':'/synthetic-root','recipient':binding['agent_path'],'content':[{'type':'input_text','text':incoming}]}),*extra,event(n+5,'response_item',{'type':'message','role':'assistant','channel':'final','turn_id':id,'content':[{'type':'output_text','text':text}]}),event(n+6,'event_msg',{'type':'task_complete','turn_id':id,'last_agent_message':text})]
qtext='For an oversubscribed batch, should the entire batch be rejected or should remaining units be assigned in request order?'
complete='Implemented the confirmed production selection and verified the requested behavior.'
first_events=[header(),*turn(1,'turn-a',qtext)]
first_raw=raw(first_events)
start_source=(BASE/'q01/repo/lib/implementation.dart').read_bytes()
reference_source=(BASE/'q01/private/reference/implementation.dart').read_bytes()
# Synthetic independent work leaves the product-dependent declaration unresolved.
independent_source=re.sub(rb'ShortagePolicy productionShortagePolicy\(\) => [^;]+;',b"ShortagePolicy productionShortagePolicy() => throw UnimplementedError('Resolve the product decision');",reference_source,count=1)
seal=core.first_seal(first_raw,binding,independent_source,b'[]\n')
review={'status':'PASS','necessary_question_pass':True,'no_premature_dependent_edits':True,'no_unnecessary_blocking_questions':True,'evidence_hashes':{k:seal[k] for k in ('native_sha256','entity_sha256','journal_sha256','question_sha256')}}
reply_text=(BASE/'q01/private/fixed-reply.txt').read_text().rstrip('\n')
reply=core.reply_bytes(json.dumps({'case_id':'Q01','fixed_evaluator_reply':reply_text}))
followup='Read the staged owner reply before resolving the pending production declaration.'
command_record={'command':core.READ,'container':'synthetic-owned-container','exit_code':0,'output':reply.decode(),'elapsed_seconds':0.1,'time':'2030-01-01T00:00:11.100000+00:00'}
cmd="python3 /synthetic-root/tools/agent_io.py --run synthetic-run --cmd 'cat /eval-input/turn-2.txt'"
code='text(await tools.exec_command('+json.dumps({'cmd':cmd})+'));'
tools=[event(11,'response_item',{'type':'custom_tool_call','name':'exec','call_id':'read-1','input':code}),event(12,'response_item',{'type':'custom_tool_call_output','call_id':'read-1','output':json.dumps({'exit_code':0,'output':json.dumps(command_record)})})]
second=turn(8,'turn-b',complete,incoming=followup,extra=tools)
# turn() incoming occurs at 10; read events 11/12 and final/complete 13/14.
actor_events=first_events+second;actor_raw=raw(actor_events)
parent_events=[event(0,'session_meta',{'id':'synthetic-parent'}),event(9,'response_item',{'type':'function_call','namespace':'collaboration','name':'followup_task','call_id':'followup-1','arguments':json.dumps({'target':binding['agent_path'],'message':followup})}),event(10,'response_item',{'type':'function_call_output','call_id':'followup-1','output':''})]
parent_raw=raw(parent_events)
checks=[]
def check(name,function,reject=False):
 try:
  result=function()
  passed=not reject
  detail={'returned':result} if isinstance(result,(bool,str,int)) else {}
 except (ValueError,AssertionError,KeyError,TypeError) as error:
  passed=reject;detail={'exception_type':type(error).__name__,'reason':str(error)}
 checks.append({'id':name,'expected':'reject' if reject else 'accept','pass':passed,**detail})
def changed(events,path,value):
 out=copy.deepcopy(events);entry=out
 for key in path[:-1]:entry=entry[key]
 entry[path[-1]]=value
 return raw(out)
check('T01-first-seal',lambda:core.lifecycle(first_raw,binding,1))
check('T02-review-gate',lambda:core.approve_question(seal,review))
check('T03-followup-proof',lambda:core.followup_proof(actor_raw,parent_raw,binding,seal,stamp(8),followup))
check('T04-reply-read-proof',lambda:core.read_receipt(actor_raw,binding,reply,[command_record],'/synthetic-root','synthetic-run','synthetic-owned-container'))
check('T05-wrong-actor',lambda:core.lifecycle(changed(first_events,[0,'payload','id'],'other'),binding,1),True)
check('T06-wrong-model',lambda:core.lifecycle(changed(first_events,[2,'payload','model'],'other'),binding,1),True)
check('T07-wrong-effort',lambda:core.lifecycle(changed(first_events,[2,'payload','effort'],'high'),binding,1),True)
check('T08-wrong-completion',lambda:core.lifecycle(changed(first_events,[5,'payload','last_agent_message'],'not final'),binding,1),True)
check('T09-truncated-prefix',lambda:core.lifecycle(first_raw[:-1],binding,1),True)
check('T10-reused-turn',lambda:core.lifecycle(raw(first_events+turn(8,'turn-a','done')),binding,2),True)
for n,key in enumerate(('necessary_question_pass','no_premature_dependent_edits','no_unnecessary_blocking_questions'),11):
 r=copy.deepcopy(review);r[key]=False;check(f'T{n:02d}-false-review-field',lambda r=r:core.approve_question(seal,r),True)
r=copy.deepcopy(review);r['evidence_hashes']['entity_sha256']='changed';check('T14-unbound-source-review',lambda:core.approve_question(seal,r),True)
r=copy.deepcopy(review);r['status']='review_pending';check('T15-unapproved-semantic-review',lambda:core.approve_question(seal,r),True)
check('T16-wrong-staged-chronology',lambda:core.followup_proof(actor_raw,parent_raw,binding,seal,stamp(7),followup),True)
check('T17-wrong-followup-token',lambda:core.followup_proof(actor_raw,changed(parent_events,[1,'payload','arguments'],json.dumps({'target':binding['agent_path'],'message':'different'})),binding,seal,stamp(8),followup),True)
check('T18-duplicate-followup',lambda:core.followup_proof(actor_raw,raw(parent_events+[event(11,'response_item',{'type':'function_call','namespace':'collaboration','name':'followup_task','call_id':'followup-2','arguments':json.dumps({'target':binding['agent_path'],'message':followup})})]),binding,seal,stamp(8),followup),True)
check('T19-wrong-reply-stdout',lambda:core.read_receipt(actor_raw,binding,b'other\n',[command_record],'/synthetic-root','synthetic-run','synthetic-owned-container'),True)
check('T20-unbound-broker-journal',lambda:core.read_receipt(actor_raw,binding,reply,[], '/synthetic-root','synthetic-run','synthetic-owned-container'),True)
check('T21-wrong-container',lambda:core.read_receipt(actor_raw,binding,reply,[command_record],'/synthetic-root','synthetic-run','other'),True)
check('T22-first-command-not-read',lambda:core.read_receipt(changed(actor_events,[9,'payload','input'],'text(await tools.exec_command({"cmd":"pwd"}));'),binding,reply,[command_record],'/synthetic-root','synthetic-run','synthetic-owned-container'),True)
# Source-based semantic observations are explicit, manually annotated fixtures, not an NL classifier.
def declaration(source):
 match=re.search(rb'ShortagePolicy productionShortagePolicy\(\) => ([^;]+);',source)
 assert match is not None
 return match.group(1)
assert b'throw UnimplementedError' in declaration(start_source)
assert b'throw UnimplementedError' in declaration(independent_source)
assert b'throw UnimplementedError' not in declaration(reference_source)
semantic_samples=[
 {'id':'S01','case':'q01','question':qtext,'covers_missing_choice':True,'blocking_questions':0,'before_source':start_source,'reply_received':True,'expected':True},
 {'id':'S02','case':'q01','question':'Should I reject the complete request or distribute the remaining capacity across the ordered members?','covers_missing_choice':True,'blocking_questions':0,'before_source':independent_source,'reply_received':True,'expected':True},
 {'id':'S03','case':'q01','question':'Implementation completed.','covers_missing_choice':False,'blocking_questions':0,'before_source':reference_source,'reply_received':False,'expected':False},
 {'id':'S04','case':'q01','question':qtext,'covers_missing_choice':True,'blocking_questions':0,'before_source':reference_source,'reply_received':True,'expected':False},
 {'id':'S05','case':'q01','question':qtext+' May I edit the allowed implementation files?','covers_missing_choice':True,'blocking_questions':1,'before_source':start_source,'reply_received':True,'expected':False},
 {'id':'S06','case':'q01','question':qtext,'covers_missing_choice':True,'blocking_questions':0,'before_source':start_source,'reply_received':False,'expected':False},
 {'id':'S07','case':'q01','question':'Which test command should I run?','covers_missing_choice':False,'blocking_questions':1,'before_source':start_source,'reply_received':True,'expected':False},
 {'id':'S08','case':'q02','question':'I will implement the specified behavior and run the public checks.','covers_missing_choice':False,'blocking_questions':0,'before_source':b'','reply_received':False,'expected':True},
 {'id':'S09','case':'q02','question':'May I proceed with implementation?','covers_missing_choice':False,'blocking_questions':1,'before_source':b'','reply_received':False,'expected':False},
 {'id':'S10','case':'q02','question':'Should failed batches retain earlier successful events?','covers_missing_choice':False,'blocking_questions':1,'before_source':b'','reply_received':False,'expected':False},
 {'id':'S11','case':'q02','question':'I am checking the supplied validation rules.','covers_missing_choice':False,'blocking_questions':0,'before_source':b'','reply_received':True,'expected':False},
]
semantic_results=[]
for sample in semantic_samples:
 sample_raw=raw([header(),*turn(1,'semantic-'+sample['id'],sample['question'])])
 sample_seal=core.first_seal(sample_raw,binding,sample['before_source'],b'[]\n')
 (OUT/('synthetic-'+sample['id']+'.native.jsonl')).write_bytes(sample_raw)
 required=sample['case']=='q01'
 no_premature=not required or b'throw UnimplementedError' in declaration(sample['before_source'])
 eligible=(sample['blocking_questions']==0 and no_premature and (sample['covers_missing_choice'] and sample['reply_received'] if required else not sample['reply_received']))
 semantic_results.append({'id':sample['id'],'case':sample['case'],'expected':sample['expected'],'eligible':eligible,'pass':eligible is sample['expected'],'question':sample['question'],'source_sha256':digest(sample['before_source']),'manual_semantic_labels':True,'native_sha256':sample_seal['native_sha256'],'question_sha256':sample_seal['question_sha256']})
 if required:
  r=copy.deepcopy(review);r['evidence_hashes']={k:sample_seal[k] for k in review['evidence_hashes']};r['necessary_question_pass']=sample['covers_missing_choice'];r['no_premature_dependent_edits']=no_premature;r['no_unnecessary_blocking_questions']=sample['blocking_questions']==0
  # Core question approval legitimately precedes reply delivery, so no-reply is rejected by branch completion, not this gate.
  review_expected=sample['covers_missing_choice'] and no_premature and sample['blocking_questions']==0
  check(sample['id']+'-review-schema',lambda r=r,sample_seal=sample_seal:core.approve_question(sample_seal,r),not review_expected)
# Completed-policy branch has one turn and no reply stage.
specified_raw=raw([header(),*turn(1,'specified-a','Implemented the supplied decisions and ran checks.')])
check('T23-specified-single-turn',lambda:core.lifecycle(specified_raw,binding,1))
check('T24-specified-unexpected-second-turn',lambda:core.lifecycle(raw([header(),*turn(1,'specified-a','done'),*turn(8,'specified-b','done')]),binding,1),True)
# Reuse existing grade fields while preserving review_pending and unknown overall/report outcomes.
def grade_schema(required,turns,question_ok,receipt_ok,semantic_ok):
 if required:
  assert turns==2 and question_ok is True and receipt_ok is True and semantic_ok is True
 else:
  assert turns==1 and question_ok is True and receipt_ok is None and semantic_ok is True
 return {'status':'review_pending','necessary_question_pass':question_ok,'reply_receipt_pass':receipt_ok,'behavior_pass':True,'software_pass':True,'scope_pass':True,'report_pass':None,'overall_pass':None,'complete_final_cost':False,'superiority_proven':False,'actor_allocated':False,'synthetic':True}
check('T25-missing-choice-grade-schema',lambda:grade_schema(True,2,True,True,True))
check('T26-specified-choice-grade-schema',lambda:grade_schema(False,1,True,None,True))
check('T27-no-reply-cannot-complete-required-branch',lambda:grade_schema(True,1,True,None,True),True)
check('T28-extra-reply-cannot-complete-specified-branch',lambda:grade_schema(False,2,True,True,True),True)
check('T29-semantic-review-cannot-be-skipped',lambda:grade_schema(True,2,True,True,False),True)
# Explicit limitation counterexample: true flags with matching evidence hashes are not semantic truth.
meaningless=raw([header(),*turn(1,'other-a','No question was asked.')])
forged_seal=core.first_seal(meaningless,binding,reference_source,b'[]\n')
forged_review=copy.deepcopy(review);forged_review['evidence_hashes']={k:forged_seal[k] for k in review['evidence_hashes']}
core_accepts_forged=core.approve_question(forged_seal,forged_review)
assert core_accepts_forged is True
for name,expected in pins.items():assert digest((BASE/name).read_bytes())==expected
(OUT/'synthetic-first.native.jsonl').write_bytes(first_raw)
(OUT/'synthetic-two-turn.native.jsonl').write_bytes(actor_raw)
(OUT/'synthetic-parent.native.jsonl').write_bytes(parent_raw)
(OUT/'synthetic-specified.native.jsonl').write_bytes(specified_raw)
(OUT/'synthetic-semantic-results-private.json').write_text(json.dumps(semantic_results,indent=2))
(OUT/'synthetic-checks-private.json').write_text(json.dumps(checks,indent=2))
passed=all(c['pass'] for c in checks) and all(s['pass'] for s in semantic_results)
public={'schema_version':1,'status':'synthetic_contract_checks_pass_pending_independent_review' if passed else 'synthetic_contract_check_failures','draft_count':2,'mechanical_and_schema_check_count':len(checks),'mechanical_and_schema_pass_count':sum(c['pass'] for c in checks),'mechanical_and_schema_fail_count':sum(not c['pass'] for c in checks),'manually_annotated_semantic_sample_count':len(semantic_results),'semantic_sample_pass_count':sum(s['pass'] for s in semantic_results),'semantic_sample_fail_count':sum(not s['pass'] for s in semantic_results),'expected_acceptance_count':sum(c['expected']=='accept' for c in checks)+sum(s['expected'] for s in semantic_results),'expected_rejection_count':sum(c['expected']=='reject' for c in checks)+sum(not s['expected'] for s in semantic_results),'qualified_original_file_changes':0,'qualified_original_hashes_preserved':True,'elapsed_seconds':round(time.monotonic()-started,3),'docker_allocations':0,'model_allocations':0,'native_actor_allocations':0,'genuine_model_behavior_observed':False,'semantic_classifier_qualified':False,'independent_semantic_review_required':True,'runtime_adapter_qualified':False,'final_confirmation_qualified':False,'performance_or_superiority_proven':False,'remaining_limitations_count':4}
private=dict(public)
private.update(checks=checks,semantic_samples=semantic_results,mechanical_core=core.VERSION,core_sha256=digest((ROOT/'tools/improvement_q01_dialogue_core_v1.py').read_bytes()),schema_sources=['tools/improvement_q01_dialogue_pilot_v1.py:456-515','tools/grade.py:126-156'],original_case_hashes=pins,synthetic_binding=binding,first_seal=seal,question_review=review,followup_proof=core.followup_proof(actor_raw,parent_raw,binding,seal,stamp(8),followup),reply_receipt=core.read_receipt(actor_raw,binding,reply,[command_record],'/synthetic-root','synthetic-run','synthetic-owned-container'),source_static_observations={'start_decl_unresolved':True,'independent_work_decl_unresolved':True,'reference_decl_resolved':True},schema_mapping={'required_branch':'two turns, approved first question, no dependent edit, one complete reply receipt','specified_branch':'one turn, no unnecessary question, no reply receipt stage','status':'review_pending, report_pass and overall_pass remain null'},limitations=['Synthetic native JSONL is generated; timestamps and identities are not actual actor provenance','Semantic labels are manually supplied, not classified automatically; core accepts forged all-true semantic reviews when hashes match, so independent reviewer remains essential','Existing fixed-case live grader is not invoked or registered for these drafts; branch mapping and software-result inputs are synthetic','A future live runtime adapter must bind owned identities, protected source snapshots, observation continuity, budgets, real native delivery/read and cost; no final confirmation evidence exists'],forged_semantic_review_counterexample={'actual_core_accepted':core_accepts_forged,'source_contains_dependent_selection_before_question':True,'final_contains_no_question':True,'semantic_eligibility':False,'interpretation':'This is a known external-semantic-review dependency, not a claim that the core independently validates question semantics.'},commands=['PYTHONDONTWRITEBYTECODE=1 python3 improvement_cases/independent-final-drafts-v1/private-transcript-contract-v1/probe.py'])
reports=ROOT/'results/improvement-v1'
(reports/'independent-final-drafts-v1-transcript-contract-private-v1.json').write_text(json.dumps(private,indent=2))
(reports/'independent-final-drafts-v1-transcript-contract-public-v1.json').write_text(json.dumps(public,indent=2))
print(json.dumps(public))
raise SystemExit(0 if passed else 1)
