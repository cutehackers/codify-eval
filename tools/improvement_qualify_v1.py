"""External qualification of prospective cases, separate from frozen evaluation core."""
import argparse,hashlib,json,pathlib,shutil,subprocess,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
def digest_tree(p):
 return {str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(p.rglob('*')) if f.is_file() and not any(t in {'.git','.dart_tool','build','__pycache__'} for t in f.relative_to(p).parts)}
def qualify(case):
 case=pathlib.Path(case).resolve();case.relative_to(ROOT/'improvement_cases')
 name=case.name;out=ROOT/'results/improvement-v1/qualification'/name
 if out.exists():raise ValueError('Preserve existing qualification; new revision required')
 out.mkdir(parents=True);image=json.loads((ROOT/'runtime/image.json').read_text())['image_id'];rows=[]
 variants=[('start',None),('gold',case/'reference')]+[(p.name,p) for p in sorted((case/'negative').iterdir()) if p.is_dir()]
 assert len(variants)>=3,'Need at least one meaningful negative variant'
 frozen=digest_tree(case)
 for label,overlay in variants:
  run=ROOT/'runtime/improvement-qualification'/name/label;repo=run/'repo';shutil.copytree(case/'repo',repo)
  if overlay:
   assert (overlay/'lib').exists()
   shutil.copytree(overlay/'lib',repo/'lib',dirs_exist_ok=True)
  shutil.copytree(case/'oracle/test',repo/'test',dirs_exist_ok=True)
  container='codify-improvement-qualify-'+name.lower()+'-'+label.lower()
  subprocess.run(['docker','run','-d','--name',container,'--network','none','-v',str(repo)+':/work/repo','-w','/work/repo',image,'sleep','infinity'],check=True,capture_output=True)
  row={'variant':label,'checks':[]}
  try:
   for command in ('flutter pub get --offline','flutter test --reporter expanded','flutter analyze --no-pub'):
    started=time.monotonic();proc=subprocess.run(['docker','exec',container,'timeout','180s','bash','-lc',command],capture_output=True,text=True,timeout=190)
    logfile=out/(label+'-'+str(len(row['checks']))+'.log');logfile.write_text(proc.stdout+proc.stderr)
    row['checks'].append({'command':command,'exit_code':proc.returncode,'elapsed_seconds':time.monotonic()-started,'output':str(logfile),'sha256':hashlib.sha256(logfile.read_bytes()).hexdigest()})
  finally:subprocess.run(['docker','rm','-f',container],check=True,capture_output=True)
  tests=row['checks'][1];log=pathlib.Path(tests['output']).read_text();row['behavior_failure_observed']=tests['exit_code']!=0 and ('Expected:' in log or 'TestFailure' in log) and 'Failed to load' not in log
  row['qualified']=all(c['exit_code']==0 for c in row['checks']) if label=='gold' else row['checks'][0]['exit_code']==0 and row['behavior_failure_observed']
  rows.append(row);print(name,label,row['qualified'],flush=True)
 assert frozen==digest_tree(case),'Qualification changed fixture source'
 receipt={'case_id':name,'image_id':image,'source_hashes':frozen,'helper_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'variants':rows,'status':'pass' if all(r['qualified'] for r in rows) else 'fail','public_oracle_coverage_review':'pending','runtime_tier':'Dart behavior through Flutter test; no actual GUI claim'}
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2));return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('case');a=p.parse_args();r=qualify(a.case);raise SystemExit(0 if r['status']=='pass' else 1)
