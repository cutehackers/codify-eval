import json,subprocess,time,re
from pathlib import Path
root=Path('improvement_cases/fresh-question-cohort-v2').resolve()
for case in ['Q05','Q06']:
 base=root/case; repo=base/'repo'; logs=base/'private/preliminary-logs'; logs.mkdir(exist_ok=True)
 records=[]
 def run(label,args):
  start=time.time()
  try:
   p=subprocess.run(args,cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
   output=p.stdout; code=p.returncode
  except subprocess.TimeoutExpired as e:
   output=(e.stdout or b'').decode() if isinstance(e.stdout,bytes) else (e.stdout or ''); code=124
  (logs/(label+'.log')).write_text(output)
  records.append({'label':label,'command':args,'exit_code':code,'seconds':round(time.time()-start,3),'log':'private/preliminary-logs/'+label+'.log'})
  print(case,label,code,flush=True)
  return code
 stub=(repo/'lib/implementation.dart').read_text()
 try:
  resolve=run('offline-resolve',['flutter','--no-version-check','--suppress-analytics','pub','get','--offline'])
  if resolve==0:
   run('starting-analyze',['dart','analyze','lib','test'])
   run('starting-public',['flutter','--no-version-check','--suppress-analytics','test','--no-pub','--reporter','expanded','test/contract_test.dart'])
   (repo/'test/acceptance_test.dart').write_text((base/'private/acceptance_test.dart').read_text())
   for name,path in [('reference',base/'private/reference.dart')]+[(n,base/'private/negative-controls'/f'{n}.dart') for n in ['N01','N02','N03','N04']]:
    (repo/'lib/implementation.dart').write_text(path.read_text())
    run(name+'-analyze',['dart','analyze','lib','test'])
    run(name+'-full',['flutter','--no-version-check','--suppress-analytics','test','--no-pub','--reporter','expanded'])
 finally:
  (repo/'lib/implementation.dart').write_text(stub)
  (repo/'test/acceptance_test.dart').unlink(missing_ok=True)
  (logs/'summary.json').write_text(json.dumps({'kind':'host preliminary only','records':records},indent=2)+'\n')
