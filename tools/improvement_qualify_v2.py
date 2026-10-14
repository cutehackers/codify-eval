"""Machine event qualification with independently registered negative test identities."""
import argparse,hashlib,json,pathlib,shutil,subprocess,time
from improvement_boundary_v1 import inspect_repo
from improvement_qualify_v1 import digest_tree,ROOT
COMMANDS=('flutter pub get --offline','flutter test --no-pub --machine','flutter analyze --no-pub')
def failed_tests(log):
 tests={};failed=set();events=[]
 for line in log.splitlines():
  try:e=json.loads(line)
  except ValueError:continue
  events.append(e)
  if e.get('type')=='testStart':tests[e['test']['id']]=e['test']['name']
  if e.get('type')=='testDone' and e.get('result') in {'failure','error'}:failed.add(e['testID'])
 names=[tests[i] for i in failed if i in tests]
 compile_fault=any('loading ' in n for n in names) or any(e.get('type')=='error' and any(t in e.get('error','') for t in ('Failed to load','Compilation failed','Error when reading')) for e in events)
 infrastructure_fault=any(e.get('type')=='error' and any(t in str(e.get('error','')).lower() for t in ('timeoutexception','timed out','timeout after','test timed out','failed to load','compilation failed')) for e in events)
 suite_terminal=any(e.get('type')=='done' for e in events)
 return names,compile_fault or infrastructure_fault or not suite_terminal

def qualify(case):
 case=pathlib.Path(case).resolve();case.relative_to(ROOT/'improvement_cases');name=case.name
 coverage_path=ROOT/'results/improvement-v1/development-coverage-review-v2.json';coverage=json.loads(coverage_path.read_text());assert coverage['verdict']=='pass'
 frozen=digest_tree(case)
 for rel,sha in frozen.items():assert coverage['source_hashes'][str((case/rel).relative_to(ROOT))]==sha
 expected=coverage['expected_failing_tests'][name];out=ROOT/'results/improvement-v1/qualification-v2'/name
 if out.exists():raise ValueError('Preserve existing qualification')
 out.mkdir(parents=True);image=json.loads((ROOT/'runtime/image.json').read_text())['image_id'];rows=[]
 variants=[('start',None),('gold',case/'reference')]+[(p.name,p) for p in sorted((case/'negative').iterdir()) if p.is_dir()]
 for label,overlay in variants:
  run=ROOT/'runtime/improvement-qualification-v2'/name/label;repo=run/'repo';shutil.copytree(case/'repo',repo)
  if overlay:shutil.copytree(overlay/'lib',repo/'lib',dirs_exist_ok=True)
  shutil.copytree(case/'oracle/test',repo/'test',dirs_exist_ok=True);inspect_repo(repo)
  container='codify-improvement-qualify-v2-'+name.lower()+'-'+label.lower();subprocess.run(['docker','run','-d','--name',container,'--network','none','-v',str(repo)+':/work/repo','-w','/work/repo',image,'sleep','infinity'],check=True,capture_output=True)
  row={'variant':label,'checks':[]}
  try:
   for command in COMMANDS:
    started=time.monotonic();proc=subprocess.run(['docker','exec',container,'timeout','180s','bash','-lc',command],capture_output=True,text=True,timeout=190)
    logfile=out/(label+'-'+str(len(row['checks']))+'.log');logfile.write_text(proc.stdout+proc.stderr)
    row['checks'].append({'command':command,'exit_code':proc.returncode,'elapsed_seconds':time.monotonic()-started,'output':str(logfile),'sha256':hashlib.sha256(logfile.read_bytes()).hexdigest()})
  finally:subprocess.run(['docker','rm','-f',container],check=True,capture_output=True)
  names,compile_fault=failed_tests(pathlib.Path(row['checks'][1]['output']).read_text());row['failing_tests']=names;row['compile_fault']=compile_fault
  row['qualified']=all(c['exit_code']==0 for c in row['checks']) if label=='gold' else row['checks'][0]['exit_code']==0 and row['checks'][1]['exit_code']==1 and not compile_fault and bool(set(expected[label])&set(names))
  rows.append(row);print(name,label,row['qualified'],flush=True)
 assert frozen==digest_tree(case)
 receipt={'case_id':name,'image_id':image,'source_hashes':frozen,'helper_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'dependency_hashes':{n:hashlib.sha256((ROOT/'tools'/n).read_bytes()).hexdigest() for n in ('improvement_qualify_v2.py','improvement_qualify_v1.py','improvement_boundary_v1.py')},'coverage_sha256':hashlib.sha256(coverage_path.read_bytes()).hexdigest(),'variants':rows,'status':'pass' if all(r['qualified'] for r in rows) else 'fail','commands':list(COMMANDS),'runtime_tier':'Dart behavior through Flutter test; no actual GUI claim'}
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2));return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('case');a=p.parse_args();r=qualify(a.case);raise SystemExit(0 if r['status']=='pass' else 1)
