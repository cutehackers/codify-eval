#!/usr/bin/env python3
"""Grade and validate canonical W02 cases without regenerating frozen sources.

software_cases/W02/{repo,reference,oracle,task.md,metadata.json} are canonical.
There is intentionally no build/authoring operation that can overwrite them.
No model evaluation or network access occurs here.
"""
from pathlib import Path
import json
import shutil
import subprocess
import os
ROOT=Path(__file__).resolve().parents[1]
CASE=ROOT/'software_cases/W02'
IMAGE='sha256:9751b1bbd374a218e0fe7dcd362e478f2b8bb5453dbed90658da8dd0b2be3638'

def grade_repo(repo, output, image=IMAGE, copy=True):
    """Independent offline build, existing regression and actual-process GUI evidence."""
    import hashlib
    import time
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    repo=Path(repo).resolve()
    work=output/'work' if copy else repo
    if copy:
        if work.exists():shutil.rmtree(work)
        shutil.copytree(repo,work,ignore=shutil.ignore_patterns('.git','.dart_tool','build','.flutter-plugins*'))
    checks=[]
    protected={}
    for relative in ['test/existing_regression_test.dart','lib/user_banner.dart']:
        actual=repo/relative;seed=CASE/'repo'/relative
        protected[relative]=actual.is_file() and actual.read_bytes()==seed.read_bytes()
    def command(args, timeout=600):
        start=time.monotonic()
        import uuid
        name='codify-w02-'+uuid.uuid4().hex[:12]
        args=args[:2]+['--name',name]+args[2:]
        try:
            process=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
            record={'command':args,'exit_code':process.returncode,'elapsed_seconds':round(time.monotonic()-start,3),'output':process.stdout,'timeout_seconds':timeout}
        except subprocess.TimeoutExpired as error:
            output_text=error.stdout or ''
            if isinstance(output_text,bytes):output_text=output_text.decode('utf-8',errors='replace')
            try:
                cleanup=subprocess.run(['docker','rm','--force',name],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
                cleanup_exit=cleanup.returncode
            except (subprocess.TimeoutExpired,OSError):
                cleanup_exit=124
            record={'command':args,'exit_code':124,'timed_out':True,'elapsed_seconds':round(time.monotonic()-start,3),'output':output_text,'timeout_seconds':timeout,'cleanup_exit_code':cleanup_exit}
        except OSError as error:
            record={'command':args,'exit_code':127,'elapsed_seconds':round(time.monotonic()-start,3),'output':str(error),'infrastructure_error':True,'timeout_seconds':timeout}
        checks.append(record)
        return record
    base=['docker','run','--rm','--network','none','--cpus','2','--memory','4g','-v',str(work)+':/work/repo','--workdir','/work/repo',image]
    for args in [['flutter','--version','--machine'],['flutter','pub','get','--offline'],['flutter','analyze','--no-pub'],['flutter','test','--no-pub'],['flutter','build','linux','--release','--no-pub']]:
        check=command(base+args)
        if check['exit_code'] and args[1] in ['pub','build']:
            result={'status':'infra_error' if check.get('infrastructure_error') else 'fail','checks':checks,'protected_files':protected,'image':image,'network':'none','error':'candidate preparation failed'}
            (output/'grade.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
            return result
    binaries=[]
    for bundle in (work/'build/linux').glob('*/release/bundle'):
        for p in bundle.iterdir():
            if p.is_file() and os.access(p,os.X_OK) and p.read_bytes()[:4]==b'\x7fELF':binaries.append(p)
    if len(binaries)!=1:
        result={'status':'fail','error':'cannot uniquely discover release executable','checks':checks,'protected_files':protected}
        (output/'grade.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    executable='/work/repo/'+str(binaries[0].relative_to(work))
    gui=['docker','run','--rm','--network','none','--cpus','2','--memory','3g','-v',str(work)+':/work/repo','-v',str(CASE/'oracle')+':/oracle:ro','-v',str(ROOT/'scripts')+':/grader/scripts:ro','-v',str(output)+':/evidence','-e','EVAL_EXECUTABLE='+executable,image,'dbus-run-session','--','sh','-c','Xvfb :99 -screen 0 1280x900x24 > /evidence/xvfb.log 2>&1 & export DISPLAY=:99; sleep 1; python3 /oracle/gui_acceptance.py "$EVAL_EXECUTABLE" /evidence/ui /evidence/data']
    runtime_helper_sha256=hashlib.sha256((ROOT/'scripts/software_runtime.py').read_bytes()).hexdigest()
    command(gui,timeout=120)
    ui=json.loads((output/'ui/gui-result.json').read_text()) if (output/'ui/gui-result.json').exists() else {'status':'fail','error':'missing GUI evidence or bounded GUI timeout'}
    result={'status':'pass' if all(c['exit_code']==0 for c in checks) and all(protected.values()) and ui['status']=='pass' else 'infra_error' if ui['status']=='infra_error' else 'fail','checks':checks,'protected_files':protected,'image':image,'network':'none','gui':ui,'runtime_helper_sha256':runtime_helper_sha256,'release_executable':{'path':str(binaries[0].relative_to(work)),'bytes':binaries[0].stat().st_size,'sha256':hashlib.sha256(binaries[0].read_bytes()).hexdigest()},'source_hashes':{str(p.relative_to(work)):hashlib.sha256(p.read_bytes()).hexdigest() for p in work.rglob('*') if p.is_file() and not any(x in p.parts for x in ['.git','.dart_tool','build'])}}
    (output/'grade.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

def validate_fixture(output=None):
    output=Path(output or ROOT/'runtime/software-validation/W02/v2');output.mkdir(parents=True,exist_ok=True)
    import hashlib
    source_hashes={variant:{str(p.relative_to(CASE/variant)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (CASE/variant).rglob('*') if p.is_file() and '__pycache__' not in p.parts} for variant in ['repo','reference','oracle']}
    records=[]
    for variant,source in [('baseline',CASE/'repo'),('reference',CASE/'reference')]:
        result=grade_repo(source,output/variant);records.append({'variant':variant,**result});print(variant,result['status'],flush=True)
    mutant=output/'source-no-archive'
    shutil.copytree(CASE/'reference',mutant,dirs_exist_ok=True)
    path=mutant/'lib/todo_controller.dart';text=path.read_text();assert 'copyWith(archived: true)' in text or 'copyWith(archived:true)' in text
    path.write_text(text.replace('copyWith(archived: true)','copyWith(archived: false)').replace('copyWith(archived:true)','copyWith(archived:false)'))
    result=grade_repo(mutant,output/'no-archive');records.append({'variant':'no_archive','semantic_mutation':'disable archive state transition',**result})
    valid=records[0]['status']=='fail' and records[0].get('gui',{}).get('status')=='fail' and records[1]['status']=='pass' and records[2]['status']=='fail' and records[2].get('gui',{}).get('status')=='fail' and all(c['exit_code']==0 for c in records[2]['checks'][:-1])
    current_hashes={variant:{str(p.relative_to(CASE/variant)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (CASE/variant).rglob('*') if p.is_file() and '__pycache__' not in p.parts} for variant in ['repo','reference','oracle']}
    unchanged=current_hashes==source_hashes
    valid=valid and unchanged
    evidence={'source_bytes_unchanged':unchanged,'case':'W02','artifact_version':'v2','valid_fixture':valid,'source_hashes':source_hashes,'image':IMAGE,'network':'none','records':records,'evidence_tier':'external_linux_release_executable','scope_limits':['No Android/iOS or provider claims','Policy reply timing is evaluated from actor transcript, not this standalone runtime grader'],'suggested_limits':{'trajectory_minutes':60,'user_turns':8,'delegation':False}}
    (output/'validation.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    summary={k:v for k,v in evidence.items() if k!='records'}
    summary['runtime_evidence_directory']=str(output.resolve())
    summary['variants']=[{'variant':r['variant'],'status':r['status'],'protected_files':r['protected_files'],'gui_requirements':r.get('gui',{}).get('requirements'),'error':r.get('gui',{}).get('error'),'processes':r.get('gui',{}).get('processes'),'command_exit_codes':[c['exit_code'] for c in r['checks']],'elapsed_seconds':round(sum(c['elapsed_seconds'] for c in r['checks']),3)} for r in records]
    (CASE/'evidence.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return evidence

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['grade','validate']);parser.add_argument('--repo');parser.add_argument('--output');args=parser.parse_args()
    if args.operation=='validate':raise SystemExit(0 if validate_fixture(args.output)['valid_fixture'] else 1)
    else:
        if not args.repo or not args.output:parser.error('grade requires --repo and --output')
        result=grade_repo(args.repo,args.output);print(result['status']);raise SystemExit(0 if result['status']=='pass' else 1)
