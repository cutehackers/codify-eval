import copy,json,sys
from pathlib import Path
import improvement_inert_origin_v3 as q
import transport
ROOT=q.ROOT
A='control-probe-improvement-v2-D01-A-1';C='control-probe-improvement-v2-D01-C0-1'
def load(run):
 e=[json.loads(x) for x in (ROOT/'results'/run/'native-tools.jsonl').read_text().splitlines()]
 r=[json.loads(x) for x in (ROOT/'runtime'/run/'commands.jsonl').read_text().splitlines()]
 m=json.loads((ROOT/'runtime'/run/'run.json').read_text());return e,r,m
checks=[]
def check(name,good):
 if not good: raise AssertionError(name)
 checks.append(name)
e,r,m=load(A);a,origins=q.audit(e,r,m,str(ROOT));check('original_A_flag_only_removed',len(q.compare(A)['before'][0])==1 and a[0]==[] and len(origins)==1)
code=next(iter(origins));prefix=f'python3 {ROOT}/tools/agent_io.py --run {A} --cmd '
def js(tail):return 'text(await tools.exec_command({cmd:'+json.dumps(prefix+tail)+'}));'
for name,tail in [('command_substitution',"'x'$(id)"),('parameter_expansion',"'x'$HOME"),('backtick',"'x'`id`"),('semicolon',"'x';id"),('pipeline',"'x'|id"),('redirection',"'x'>f"),('newline',"'x'\nid"),('extra_argument',"'x' extra"),('glob',"'x'*"),('brace',"'x'{a,b}"),('tilde',"'x'~"),('escape',"'x'\\a"),('history',"'x'!"),('double_expansion',"'x'\"$HOME\""),('unbalanced',"'x")]: check(name,q.literal_command(js(tail),str(ROOT),A) is None)
check('extra_javascript',q.literal_command(code+'text(1);',str(ROOT),A) is None)
check('foreign_run',q.literal_command(code,str(ROOT),C) is None)
check('no_receipt',q.audit(e,[],m,str(ROOT))[0]==q.compare(A)['before'])
foreign=copy.deepcopy(r)
for row in foreign:row['container']='foreign'
check('foreign_receipt',q.audit(e,foreign,m,str(ROOT))[0]==q.compare(A)['before'])
future=copy.deepcopy(r)
for row in future:row['time']='2099-01-01T00:00:00+00:00'
check('nonchronological_receipt',q.audit(e,future,m,str(ROOT))[0]==q.compare(A)['before'])
for label,replacement in [('nonempty_stdin','x'),('foreign_session',999999)]:
 altered=copy.deepcopy(e)
 for row in altered:
  p=row.get('payload',{})
  if p.get('call_id')=='call_1e579c861faa46a883becd9fe2c40a5e' and p.get('type') in {'function_call','custom_tool_call'}:
   text=p.get('input',p.get('arguments',''));key='input' if 'input' in p else 'arguments'
   p[key]=text.replace('chars:""','chars:"x"') if label=='nonempty_stdin' else text.replace('48552','999999')
 check(label,len(q.audit(altered,r,m,str(ROOT))[0][0])==1)
original_call=next(x for x in e if x.get('payload',{}).get('input',x.get('payload',{}).get('arguments',''))==code)
duplicate=copy.deepcopy(original_call);duplicate['payload']['call_id']='unreceipted-duplicate'
check('duplicate_code_no_attribution',not q.origin_proofs(e+[duplicate],r,m,str(ROOT)))
original_output=next(x for x in e if x.get('payload',{}).get('call_id')==original_call['payload']['call_id'] and x.get('payload',{}).get('type') in {'function_call_output','custom_tool_call_output'})
reordered=[original_output]+[x for x in e if x is not original_output]
check('output_before_origin_rejected',not q.origin_proofs(reordered,r,m,str(ROOT)))
ce,cr,cm=load(C);check('actual_C0_violation_retained',q.audit(ce,cr,cm,str(ROOT))[0]==q.compare(C)['before'])
check('frozen_json_expected_audit_roundtrip',list(a)==json.loads(json.dumps(list(a))))
report={'status':'pass','checks':checks,'source_sha256':{str(p.relative_to(ROOT)):q.sha(p) for p in [Path(__file__),ROOT/'tools/improvement_inert_origin_v3.py',ROOT/'tools/transport.py',ROOT/'tools/collect_schema_v366.py']},'actor_reexecuted':False}
(ROOT/'results/improvement-v1/inert-origin-probes-v3.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
