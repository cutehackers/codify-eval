import json,hashlib,shutil,subprocess,time,re,tarfile,os
from pathlib import Path
root=Path('improvement_cases/fresh-question-cohort-v2').resolve()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for case in ['Q05','Q06']:
 base=root/case; oldmeta=json.loads((base/'metadata.json').read_text()); history=base/'private/historical/v1'
 assert not history.exists(),'Historical v1 exists; refusing overwrite'
 history.mkdir(parents=True)
 shutil.copy2(base/'private/negative-controls/N03.dart',history/'N03.dart')
 shutil.copytree(base/'private/preliminary-logs',history/'preliminary-logs')
 for name in ['metadata.json','authoring-provenance.json']:shutil.copy2(base/name,history/name)
 manifest={'revision':'v1 historical immutable evidence','files':{str(p.relative_to(history)):sha(p) for p in sorted(history.rglob('*')) if p.is_file()}}
 (history/'sha256-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 for p in history.rglob('*'):
  if p.is_file():p.chmod(0o444)
 for p in sorted([p for p in history.rglob('*') if p.is_dir()],reverse=True):p.chmod(0o555)
 history.chmod(0o555)
 control=base/'private/negative-controls/N03.dart'; text=control.read_text()
 if case=='Q05':
  old="    final previous = store.recorded(request.warehouseId, request.orderId);\n    if (previous != null && previous.signature == 'invalid signature sentinel') {\n      return previous.signature == signature ? previous.outcome : const Outcome('conflict');\n    }\n"
  assert old in text;text=text.replace(old,'')
 else:
  assert '    final ids = <String>{};\n' in text and '(ids.add(id) && id.isEmpty)' in text
  text=text.replace('    final ids = <String>{};\n','').replace(' || (ids.add(id) && id.isEmpty)','')
 control.write_text(text)
 logs=base/'private/preliminary-logs/revision-v2'; assert not logs.exists();logs.mkdir()
 repo=base/'repo'; stub=(repo/'lib/implementation.dart').read_text(); records=[]
 def run(label,args):
  start=time.time()
  try:
   result=subprocess.run(args,cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
   output=result.stdout;code=result.returncode
  except subprocess.TimeoutExpired as e:
   output=(e.stdout or b'').decode() if isinstance(e.stdout,bytes) else (e.stdout or '');code=124
  (logs/(label+'.log')).write_text(output)
  record={'label':label,'command':args,'exit_code':code,'seconds':round(time.time()-start,3),'log':'private/preliminary-logs/revision-v2/'+label+'.log'}
  if label=='N03-full':
   record['failed_test_ids']=re.findall(r': ((?:P|A)\d\d) [^\n]*\[E\]',output)
   totals=re.findall(r'\+(\d+)(?: -(\d+))?: (?:All tests passed!|Some tests failed\.)',output)
   if totals:
    passed,failed=totals[-1];record.update({'passed_count':int(passed),'failed_count':int(failed or 0),'executed_count':int(passed)+int(failed or 0)})
  records.append(record);print(case,label,code,record.get('failed_test_ids'),flush=True);return code
 try:
  resolved=run('offline-resolve',['flutter','--no-version-check','--suppress-analytics','pub','get','--offline'])
  if resolved==0:
   (repo/'lib/implementation.dart').write_text(control.read_text())
   (repo/'test/acceptance_test.dart').write_text((base/'private/acceptance_test.dart').read_text())
   run('N03-analyze',['dart','analyze','lib','test'])
   run('N03-full',['flutter','--no-version-check','--suppress-analytics','test','--no-pub','--reporter','expanded'])
 finally:
  (repo/'lib/implementation.dart').write_text(stub)
  (repo/'test/acceptance_test.dart').unlink(missing_ok=True)
  generated=[repo/name for name in ['.dart_tool','build','pubspec.lock'] if (repo/name).exists()]
  if generated:
   with tarfile.open(base/'private/preliminary-host-artifacts-revision-v2.tar.gz','w:gz',dereference=False) as tar:
    for p in generated:tar.add(p,arcname=p.name)
   for p in generated:
    if p.is_dir():shutil.rmtree(p)
    else:p.unlink()
  summary={'revision':'N03 v2 only','qualification':False,'records':records}
  (logs/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 expected=['A02','P06','P07'] if case=='Q05' else ['P06']
 full=next(r for r in records if r['label']=='N03-full');analyze=next(r for r in records if r['label']=='N03-analyze')
 assert analyze['exit_code']==0
 assert full['exit_code']==1 and sorted(full['failed_test_ids'])==sorted(expected)
 assert full['executed_count']==oldmeta['full_test_count']
 for rel,h in oldmeta['sha256_inventory'].items():
  if rel not in ['private/negative-controls/N03.dart','authoring-provenance.json']:
   assert sha(base/rel)==h,('Protected prior file changed',case,rel)
 for rel,h in manifest['files'].items():assert sha(history/rel)==h
 provenance=json.loads((base/'authoring-provenance.json').read_text())
 provenance['revision_v2']={'additional_authorized_read':'results/improvement-v1/fresh-question-cohort-v2-static-review-v1.json (own fixtures only)','issues_addressed':['R01'] if case=='Q05' else ['R02'],'change':'Only N03 control replaced: omitted recorded-order lookup/handling' if case=='Q05' else 'Only N03 control replaced: omitted duplicate-ID set/check','historical_evidence':'private/historical/v1 (copied before replacement, read-only files/directories)','new_logs':'private/preliminary-logs/revision-v2','public_reference_oracle_other_controls':'Bytes unchanged; prior inventory verified','status':'authored_unqualified'}
 (base/'authoring-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 metadata=oldmeta
 metadata['negative_controls']['N03']['defect']='Recorded-order lookup and handling omitted' if case=='Q05' else 'Duplicate-ID set and validation omitted'
 metadata['negative_controls']['N03']['revision']='v2'
 metadata['negative_controls']['N03']['observed_host_failed_test_ids']=full['failed_test_ids']
 metadata['historical_notes']={'v1':'private/historical/v1 preserves original N03, all preliminary logs, metadata including prior inventory, provenance and a snapshot hash manifest. Copied and made read-only before replacement. Original preliminary logs remain unchanged.','v2':'Only N03 changed in each fixture. New analyzer/full-test evidence and host artifacts have distinct revision-v2 paths. No reference/other-control checks rerun.','new_evidence':'private/preliminary-logs/revision-v2/summary.json','current_N03_sha256':sha(control),'historical_N03_sha256':sha(history/'N03.dart'),'exact_failure_ids_preserved':True}
 metadata['inventory_rule']='SHA-256 of every fixture file other than the top-level metadata.json itself, including historical metadata and all revision evidence. Compressed host artifacts are evidence only and never mounted. Authoring inventory, not frozen qualification.'
 metadata['sha256_inventory']={str(p.relative_to(base)):sha(p) for p in sorted(base.rglob('*')) if p.is_file() and p!=base/'metadata.json'}
 (base/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
 print(case,'current_N03',sha(control),'metadata',sha(base/'metadata.json'),flush=True)
