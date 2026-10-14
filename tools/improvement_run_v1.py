"""Versioned adapter for new development cases, preserving prior frozen tools."""
import argparse,hashlib,json,pathlib,sys
import prepare
ROOT=prepare.ROOT

def case_directory(case_id):
 p=ROOT/'improvement_cases'/case_id
 if not p.is_dir():raise ValueError('Not an allowed development case')
 return p

def freeze_development():
 dest=ROOT/'results/improvement-v1/development-freeze.json'
 if dest.exists():raise ValueError('Development comparison already frozen')
 cases=['D01','D02'];conditions=['A','C0','C1']
 for c in cases:
  q=json.loads((ROOT/'results/improvement-v1/qualification'/c/'receipt.json').read_text())
  if q['status']!='pass':raise ValueError('Unqualified fixture '+c)
 coverage=json.loads((ROOT/'results/improvement-v1/development-coverage-review.json').read_text())
 if coverage['verdict']!='pass':raise ValueError('Public coverage not independently qualified')
 names=['tools/improvement_run_v1.py','tools/improvement_qualify_v1.py','tools/prepare.py','tools/dispatch.py','tools/agent_io.py','tools/collect_schema_v366.py','tools/grade.py','tools/transport.py','results/improvement-v1/candidate-freeze.json','results/improvement-v1/development-coverage-review.json']
 data={'status':'frozen','stage':'development only; no confirmatory superiority claim','model':'gpt-6.1-sol','effort':'medium','concurrency':1,'trajectory_seconds':1200,'retries':0,'conditions':conditions,'case_hashes':{c:prepare.tree_hash(case_directory(c)) for c in cases},'skill_hashes':{c:prepare.tree_hash(ROOT/'snapshots'/c) for c in conditions if c!='A'},'source_hashes':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names},'sequence':[{'case_id':c,'condition':cond,'repeat':1,'run_id':f'control-probe-improvement-v1-{c}-{cond}-1'} for c,conds in [('D01',['C0','A','C1']),('D02',['A','C1','C0'])] for cond in conds]}
 dest.write_text(json.dumps(data,indent=2));return data

def check():
 p=ROOT/'results/improvement-v1/development-freeze.json';d=json.loads(p.read_text())
 for name,sha in d['source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
 for c,sha in d['case_hashes'].items():assert prepare.tree_hash(case_directory(c))==sha,c
 for c,sha in d['skill_hashes'].items():assert prepare.tree_hash(ROOT/'snapshots'/c)==sha,c
 return p,d

def launch(case,condition):
 p,d=check();assert condition in d['conditions'];assert case in d['case_hashes'];prepare.case_directory=case_directory
 r=prepare.prepare(case,condition,1,'control-probe-improvement-v1')
 meta_path=ROOT/'runtime'/r['run_id']/'run.json';meta=json.loads(meta_path.read_text());meta['evaluation_core']={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()};meta['time_limit_seconds']=1200;meta['user_turn_limit']=1;meta_path.write_text(json.dumps(meta,indent=2))
 import dispatch
 return dispatch.dispatch(r['run_id'])

def grade_run(run_id):
 check();import grade
 grade.case_directory=case_directory;return grade.grade(run_id)
if __name__=='__main__':
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True);sub.add_parser('freeze');l=sub.add_parser('prepare');l.add_argument('case');l.add_argument('condition');g=sub.add_parser('grade');g.add_argument('run');args=p.parse_args()
 result=freeze_development() if args.action=='freeze' else launch(args.case,args.condition) if args.action=='prepare' else grade_run(args.run)
 print(result if isinstance(result,str) else json.dumps(result,ensure_ascii=False))
