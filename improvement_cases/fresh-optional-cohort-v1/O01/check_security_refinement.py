from pathlib import Path
import subprocess,os,time,json,hashlib,shutil
b=Path(__file__).resolve().parent;r=b/'repo';ev=b/'private/host_evidence/attempt-v3';ev.mkdir(parents=True)
files=[p.name for p in (b/'private/reference/lib').iterdir()];saved={f:(r/'lib'/f).read_bytes() for f in files};records=[]
def run(label,args):
 start=time.time();p=subprocess.run(args,cwd=r,capture_output=True,text=True,timeout=180,env={**os.environ,'CI':'true','FLUTTER_SUPPRESS_ANALYTICS':'true','DART_SUPPRESS_ANALYTICS':'true'})
 (ev/(label+'.stdout')).write_text(p.stdout);(ev/(label+'.stderr')).write_text(p.stderr)
 events=[]
 for line in p.stdout.splitlines():
  try:
   x=json.loads(line)
   if isinstance(x,dict):events.append(x)
  except ValueError:pass
 ends=[x for x in events if x.get('type')=='testDone' and not x.get('hidden',False)];names={x['test']['id']:x['test']['name'] for x in events if x.get('type')=='testStart'}
 rec={'label':label,'argv':args,'exit_status':p.returncode,'elapsed_seconds':round(time.time()-start,3),'completed_test_events':len(ends),'successful_test_events':sum(x.get('result')=='success' for x in ends),'failed_test_events':sum(x.get('result') in ['error','failure'] for x in ends),'failed_tests':[names.get(x['testID']) for x in ends if x.get('result') in ['error','failure']],'source_sha256':{str(q.relative_to(r)):hashlib.sha256(q.read_bytes()).hexdigest() for q in r.rglob('*.dart') if '/lib/' in str(q) or '/test/' in str(q)}}
 records.append(rec);(ev/'commands.json').write_text(json.dumps(records,indent=2)+'\n');print(label,p.returncode,len(ends),flush=True)
try:
 run('offline_pub_get',['flutter','pub','get','--offline'])
 for f in files:shutil.copyfile(b/'private/reference/lib'/f,r/'lib'/f)
 shutil.copyfile(b/'private/acceptance_test.dart',r/'test/author_acceptance_test.dart')
 run('reference_analyze',['flutter','analyze','--no-pub'])
 run('reference_combined',['flutter','test','--no-pub','--machine','test/contract_test.dart','test/author_acceptance_test.dart'])
 for f in files:shutil.copyfile(b/'private/negative_controls/security_permission_bypass/lib'/f,r/'lib'/f)
 run('negative_security_permission_bypass',['flutter','test','--no-pub','--machine','test/contract_test.dart','test/author_acceptance_test.dart'])
finally:
 for f,data in saved.items():(r/'lib'/f).write_bytes(data)
 (r/'test/author_acceptance_test.dart').unlink(missing_ok=True)
 a=b/'private/host_archive/attempt-v3';a.mkdir(parents=True)
 for name in ['.dart_tool','build','pubspec.lock','.flutter-plugins','.flutter-plugins-dependencies']:
  q=r/name
  if q.exists():shutil.move(str(q),str(a/name))
