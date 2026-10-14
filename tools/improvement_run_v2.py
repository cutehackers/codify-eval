"""Bound, immutable development comparison; no confirmatory superiority claim."""
import argparse,gzip,hashlib,json,pathlib,shutil,subprocess
import prepare
from improvement_boundary_v1 import inspect_repo
from improvement_qualify_v1 import digest_tree
from improvement_qualify_v3 import COMMANDS
ROOT=prepare.ROOT;FREEZE=ROOT/'results/improvement-v1/development-freeze-v2.json';PHASE='control-probe-improvement-v2'
class ActorNotTerminal(Exception):pass

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def case_directory(c):
 if c not in {'D01','D02'}:raise ValueError('Unknown development case')
 return ROOT/'improvement_cases'/c

def freeze():
 if FREEZE.exists():raise ValueError('Already frozen')
 image=json.loads((ROOT/'runtime/image.json').read_text())['image_id'];coverage_path=ROOT/'results/improvement-v1/development-coverage-review-v2.json';coverage=json.loads(coverage_path.read_text());assert coverage['verdict']=='pass'
 names=['runtime/image.json','results/improvement-v1/candidate-freeze.json',str(coverage_path.relative_to(ROOT))]+[str(p.relative_to(ROOT)) for p in (ROOT/'tools').glob('*.py')]
 for c in ('D01','D02'):
  p=ROOT/'results/improvement-v1/qualification-v3'/c/'receipt.json';q=json.loads(p.read_text());assert q['status']=='pass' and q['case_id']==c and q['image_id']==image and q['commands']==list(COMMANDS)
  assert q['source_hashes']==digest_tree(case_directory(c));assert q['helper_sha256']==sha(ROOT/'tools/improvement_qualify_v3.py') and all(sha(ROOT/'tools'/n)==h for n,h in q['dependency_hashes'].items()) and set(q['dependency_hashes'])=={'improvement_qualify_v3.py','improvement_qualify_v1.py','improvement_boundary_v1.py'} and q['coverage_sha256']==sha(coverage_path)
  for rel,s in q['source_hashes'].items():assert coverage['source_hashes'][str((case_directory(c)/rel).relative_to(ROOT))]==s
  for row in q['variants']:
   for check in row['checks']:assert sha(check['output'])==check['sha256'];names.append(str(pathlib.Path(check['output']).relative_to(ROOT)))
  names.append(str(p.relative_to(ROOT)))
 candidate=json.loads((ROOT/'results/improvement-v1/candidate-freeze.json').read_text());assert candidate['files']=={str(p.relative_to(ROOT/'snapshots/C1')):sha(p) for p in (ROOT/'snapshots/C1').rglob('*') if p.is_file()}
 reviewer_path=ROOT/'results/improvement-v1/development-helper-review-v3.json';reviewer=json.loads(reviewer_path.read_text());assert reviewer['verdict']=='pass'
 for n,s in reviewer['source_hashes'].items():assert sha(ROOT/n)==s,n
 names.append(str(reviewer_path.relative_to(ROOT)))
 from collect_schema_v366 import verify_registration,MANIFEST,PARSER_RUNTIME
 registration=verify_registration();names.extend([str(MANIFEST.relative_to(ROOT)),'results/frozen-core-v3.6.json','results/frozen-native-schema-v3.6.1.json','results/frozen-escaped-template-collection-v3.6.2.json','results/frozen-software-gui-transport-v3.6.3.json','results/frozen-software-poll-presentation-v3.6.4.json'])
 names.extend(registration['source_sha256'])
 for manifest in list(names):
  if manifest.startswith('results/frozen') and manifest.endswith('.json'):
   value=json.loads((ROOT/manifest).read_text());names.extend(value.get('source_sha256',{}));names.extend(value.get('grader_hashes',{}))
 names.append(PARSER_RUNTIME['path']) if 'path' in PARSER_RUNTIME else None
 d={'status':'frozen','stage':'development only','model':'gpt-6.1-sol','effort':'medium','concurrency':1,'trajectory_seconds':1200,'retries':0,'conditions':['A','C0','C1'],'image_id':image,'case_hashes':{c:prepare.tree_hash(case_directory(c)) for c in ('D01','D02')},'skill_hashes':{c:prepare.tree_hash(ROOT/'snapshots'/c) for c in ('C0','C1')},'source_hashes':{n:sha(ROOT/n) for n in sorted(set(names))},'sequence':[{'case_id':c,'condition':cond,'repeat':1,'run_id':f'{PHASE}-{c}-{cond}-1'} for c,conds in [('D01',['C0','A','C1']),('D02',['A','C1','C0'])] for cond in conds]}
 FREEZE.write_text(json.dumps(d,indent=2));return d

def check():
 d=json.loads(FREEZE.read_text())
 for n,s in d['source_hashes'].items():assert sha(ROOT/n)==s,n
 for c,s in d['case_hashes'].items():assert prepare.tree_hash(case_directory(c))==s,c
 for c,s in d['skill_hashes'].items():assert prepare.tree_hash(ROOT/'snapshots'/c)==s,c
 return d

def bind(run_id,d):
 rows=[r for r in d['sequence'] if r['run_id']==run_id];assert len(rows)==1;row=rows[0];m=json.loads((ROOT/'runtime'/run_id/'run.json').read_text())
 assert all(m.get(k)==row[k] for k in ('run_id','case_id','condition','repeat'))
 assert m['phase']==PHASE and m['model']==d['model'] and m['effort']==d['effort'] and m['image_id']==d['image_id'] and m['case_hash']==d['case_hashes'][m['case_id']]
 assert m['skill_hash']==d['skill_hashes'].get(m['condition'])
 assert m['evaluation_core']=={'path':str(FREEZE),'sha256':sha(FREEZE)}
 return m

def launch(case,condition):
 d=check();target=f'{PHASE}-{case}-{condition}-1';next_row=None
 for row in d['sequence']:
  if not (ROOT/'results'/row['run_id']/'grade.json').exists():next_row=row;break
 assert next_row and next_row['run_id']==target,'Must launch next registered run'
 assert not subprocess.check_output(['docker','ps','-q','--filter','name=codify-'],text=True).strip(),'One live evaluation container at a time'
 prepare.case_directory=case_directory;r=prepare.prepare(case,condition,1,PHASE)
 p=ROOT/'runtime'/r['run_id']/'run.json';m=json.loads(p.read_text());m['evaluation_core']={'path':str(FREEZE),'sha256':sha(FREEZE)};m['time_limit_seconds']=1200;m['user_turn_limit']=1;p.write_text(json.dumps(m,indent=2));bind(r['run_id'],d);inspect_repo(ROOT/'runtime'/r['run_id']/'repo')
 import dispatch;return dispatch.dispatch(r['run_id'])

def terminal_error(run_id,m,category,error):
 out=ROOT/'results'/run_id;out.mkdir(parents=True,exist_ok=True);path=out/'grade.json'
 if path.exists():raise ValueError('Preserve prior terminal outcome')
 result={'run_id':run_id,'status':'evaluation_error' if category=='boundary' else 'infra_error','category':category,'reason':str(error),'behavior_pass':None,'overall_pass':None,'actor_retried':False}
 path.write_text(json.dumps(result,indent=2));return result

def quiesce(run_id,m,agent_path):
 from collect import find_session
 try:source=find_session(agent_path)
 except ValueError as error:raise ActorNotTerminal(str(error)) from error
 events=[json.loads(l) for l in source.read_text().splitlines()]
 if not any(e['type']=='event_msg' and e.get('payload',{}).get('type')=='task_complete' for e in events):raise ActorNotTerminal('Native actor has no normal completion; re-observe the same actual agent handle')
 out=ROOT/'results'/run_id;out.mkdir(parents=True,exist_ok=True)
 identity=json.loads(subprocess.check_output(['docker','inspect',m['container']],text=True))[0]
 assert identity['Image']==m['image_id'] and identity['HostConfig']['NetworkMode']=='none'
 assert sorted(x['Source'] for x in identity['Mounts'])==sorted([str(ROOT/'runtime'/run_id/'repo'),str(ROOT/'runtime'/run_id/'control-inputs')])
 if identity['State']['Running']:subprocess.run(['docker','stop','-t','2',m['container']],check=True,capture_output=True)
 after=json.loads(subprocess.check_output(['docker','inspect',m['container']],text=True))[0];assert not after['State']['Running']
 (out/'quiescence.json').write_text(json.dumps({'identity_before':identity,'identity_after':after,'normal_native_source':str(source),'native_source_sha256':sha(source),'actor_filesystem_stopped':True},indent=2))
 # Preserve non-mounted diagnostic data; caches and SDK state are reproducible.
 with (out/'docker-diff.txt').open('w') as f:subprocess.run(['docker','diff',m['container']],check=True,stdout=f,text=True)
 proc=subprocess.Popen(['docker','cp',m['container']+':/tmp','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 with gzip.open(out/'container-tmp.tar.gz','wb') as f:shutil.copyfileobj(proc.stdout,f)
 err=proc.stderr.read();assert proc.wait()==0,err
 return out

def collect_run(run_id,agent_path):
 d=check();m=bind(run_id,d)
 if (ROOT/'results'/run_id/'turns.json').exists() or (ROOT/'results'/run_id/'grade.json').exists():raise ValueError('Preserve first collection/outcome')
 try:
  quiesce(run_id,m,agent_path)
  repo=ROOT/'runtime'/run_id/'repo';inspect_repo(repo);seal=digest_tree(repo)
  from collect_schema_v366 import qualified_collect
  result=qualified_collect(run_id,agent_path)
  inspect_repo(repo);assert digest_tree(repo)==seal
  (ROOT/'results'/run_id/'artifact-seal.json').write_text(json.dumps({'files':seal,'container_stopped':True,'native_agent_path':agent_path},indent=2))
  from improvement_usage_v1 import usage
  cost=usage(agent_path);cost['role']='product';(ROOT/'results'/run_id/'usage.json').write_text(json.dumps(cost,indent=2));return result
 except ActorNotTerminal:
  raise
 except Exception as error:
  result=terminal_error(run_id,m,'boundary' if isinstance(error,ValueError) and 'Unsafe actor artifact' in str(error) else 'collection',error)
  from improvement_usage_v1 import usage
  cost=usage(agent_path);cost['role']='product';(ROOT/'results'/run_id/'usage.json').write_text(json.dumps(cost,indent=2));return result
 finally:
  if (ROOT/'results'/run_id/'grade.json').exists():subprocess.run(['docker','rm','-f',m['container']],check=True,capture_output=True)

def full_grade(run,case_dir,directory):
 import grade
 graded=ROOT/'runtime/grading'/run['run_id']
 if graded.exists():raise ValueError('Preserve previous grading copy')
 inspect_repo(directory/'repo');shutil.copytree(directory/'repo',graded,ignore=shutil.ignore_patterns('.git','.dart_tool','build','__pycache__','.agents'))
 shutil.copytree(case_dir/'oracle/test',graded/'test',dirs_exist_ok=True);inspect_repo(graded)
 container='grade-'+run['run_id'].lower();subprocess.run(['docker','run','-d','--name',container,'--network','none','-v',str(graded)+':/work/repo','-w','/work/repo',run['image_id'],'sleep','infinity'],check=True,capture_output=True)
 try:return [grade.execute(container,command) for command in COMMANDS]
 finally:subprocess.run(['docker','rm','-f',container],check=True,capture_output=True)

def grade_run(run_id):
 d=check();m=bind(run_id,d)
 if (ROOT/'results'/run_id/'grade.json').exists() or (ROOT/'runtime/grading'/run_id).exists():raise ValueError('No unregistered regrade')
 assert m['status']=='collected' and len(m['turns'])==1
 try:
  identity=json.loads(subprocess.check_output(['docker','inspect',m['container']],text=True))[0];assert not identity['State']['Running']
  inspect_repo(ROOT/'runtime'/run_id/'repo');seal=json.loads((ROOT/'results'/run_id/'artifact-seal.json').read_text());assert digest_tree(ROOT/'runtime'/run_id/'repo')==seal['files']
  import grade;grade.case_directory=case_directory;grade.grade_flutter=full_grade
  result=grade.grade(run_id)
 except Exception as error:
  result=terminal_error(run_id,m,'grading',error)
 finally:
  subprocess.run(['docker','rm','-f',m['container']],check=True,capture_output=True)
 if m.get('elapsed_seconds',float('inf'))>d['trajectory_seconds']:
  result.update(status='fail',overall_pass=False,time_limit_exceeded=True);(ROOT/'results'/run_id/'grade.json').write_text(json.dumps(result,indent=2))
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();subs=p.add_subparsers(dest='action',required=True);subs.add_parser('freeze');l=subs.add_parser('prepare');l.add_argument('case');l.add_argument('condition');g=subs.add_parser('grade');g.add_argument('run');c=subs.add_parser('collect');c.add_argument('run');c.add_argument('agent_path');a=p.parse_args()
 r=freeze() if a.action=='freeze' else launch(a.case,a.condition) if a.action=='prepare' else collect_run(a.run,a.agent_path) if a.action=='collect' else grade_run(a.run);print(r if isinstance(r,str) else json.dumps(r,ensure_ascii=False))
