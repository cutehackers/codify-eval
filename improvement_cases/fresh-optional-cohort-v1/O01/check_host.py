from pathlib import Path
import subprocess,json,time,shutil,hashlib
B=Path(__file__).resolve().parent.parent
for c in ['O01','O02']:
 base=B/c;repo=base/'repo';ev=base/'private/host_evidence/attempt-v2';ev.mkdir(parents=True,exist_ok=True)
 # Remove pure-helper imports unused only in private tests.
 p=base/'private/acceptance_test.dart';t=p.read_text()
 t=t.replace("import 'package:o01_fixture/search_plan.dart';\n",'') if c=='O01' else t.replace("import 'package:o02_fixture/export_selection.dart';\n",'')
 p.write_text(t)
 editable=[p.name for p in (base/'private/reference/lib').iterdir()]
 saved={f:(repo/'lib'/f).read_bytes() for f in editable}
 records=[]
 def run(label,args):
  started=time.time();p=subprocess.run(args,cwd=repo,text=True,capture_output=True,env={**__import__('os').environ,'CI':'true','FLUTTER_SUPPRESS_ANALYTICS':'true','DART_SUPPRESS_ANALYTICS':'true'},timeout=180)
  (ev/(label+'.stdout')).write_text(p.stdout);(ev/(label+'.stderr')).write_text(p.stderr)
  events=[]
  for line in p.stdout.splitlines():
   try: events.append(json.loads(line))
   except ValueError:pass
  ends=[e for e in events if isinstance(e,dict) and e.get('type')=='testDone' and not e.get('hidden',False)]
  rec={'label':label,'argv':args,'exit_status':p.returncode,'elapsed_seconds':round(time.time()-started,3),'completed_test_events':len(ends),'successful_test_events':sum(e.get('result')=='success' for e in ends),'failed_test_events':sum(e.get('result') in ['error','failure'] for e in ends),'source_sha256':{f:hashlib.sha256((repo/'lib'/f).read_bytes()).hexdigest() for f in editable}}
  records.append(rec);(ev/'commands.json').write_text(json.dumps(records,indent=2)+'\n');print(c,label,p.returncode,len(ends),flush=True)
  return p.returncode
 try:
  run('offline_pub_get',['flutter','pub','get','--offline'])
  run('starting_public',['flutter','test','--no-pub','--machine','test/contract_test.dart'])
  for f in editable:shutil.copyfile(base/'private/reference/lib'/f,repo/'lib'/f)
  shutil.copyfile(base/'private/acceptance_test.dart',repo/'test/author_acceptance_test.dart')
  run('reference_analyze',['flutter','analyze','--no-pub'])
  run('reference_public',['flutter','test','--no-pub','--machine','test/contract_test.dart'])
  run('reference_private',['flutter','test','--no-pub','--machine','test/author_acceptance_test.dart'])
  for control in sorted((base/'private/negative_controls').iterdir()):
   for f in editable:shutil.copyfile(control/'lib'/f,repo/'lib'/f)
   run('negative_'+control.name,['flutter','test','--no-pub','--machine','test/contract_test.dart','test/author_acceptance_test.dart'])
 finally:
  for f,content in saved.items():(repo/'lib'/f).write_bytes(content)
  (repo/'test/author_acceptance_test.dart').unlink(missing_ok=True)
  archive=base/'private/host_archive/attempt-v2';archive.mkdir(parents=True,exist_ok=True)
  for name in ['.dart_tool','build','pubspec.lock','.flutter-plugins','.flutter-plugins-dependencies']:
   p=repo/name
   if p.exists():shutil.move(str(p),str(archive/name))
