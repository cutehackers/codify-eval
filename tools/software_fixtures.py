#!/usr/bin/env python3
"""Independent W01 real-Linux app grader and fixture validator.

Import grade_repo(repo, output) in another grader. The oracle and shared AT-SPI
helper are mounted only in the independent grading container, never the actor.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import time
import uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
CASE=ROOT/'software_cases/W01'
IMAGE='sha256:9751b1bbd374a218e0fe7dcd362e478f2b8bb5453dbed90658da8dd0b2be3638'
DEFAULT_OUTPUT=ROOT/'runtime/software-validation/W01-v2-review-repair'

def tree_hashes(folder):
    return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(pathlib.Path(folder).rglob('*')) if p.is_file() and not any(x in p.parts for x in ('.dart_tool','build','.git'))}

def fixture_source_hashes():
    return {'repo':tree_hashes(CASE/'repo'),'reference':tree_hashes(CASE/'reference'),'oracle':tree_hashes(CASE/'oracle'),
            'contract':{name:hashlib.sha256((CASE/name).read_bytes()).hexdigest() for name in ('task.md','metadata.json')},
            'grader':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('tools/software_fixtures.py','scripts/software_runtime.py')}}

def _command(args,output,cwd=None,timeout=600):
    actual=list(args);container=None
    if actual[:2]==['docker','run']:
        container='codify-w01-'+uuid.uuid4().hex[:12]
        actual[2:2]=['--name',container]
    start=time.time()
    try:
        p=subprocess.run(actual,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
        return {'command':actual,'exit_code':p.returncode,'elapsed_seconds':round(time.time()-start,3),'timeout_seconds':timeout,'timed_out':False,'output':p.stdout}
    except subprocess.TimeoutExpired as e:
        output=e.stdout.decode(errors='replace') if isinstance(e.stdout,bytes) else e.stdout or ''
        if container:
            try:
                cleanup=subprocess.run(['docker','rm','-f',container],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=30)
                output+='\nTimed out; container cleanup: '+cleanup.stdout
            except subprocess.TimeoutExpired:output+='\nContainer cleanup also timed out.'
        return {'command':actual,'exit_code':124,'elapsed_seconds':round(time.time()-start,3),'timeout_seconds':timeout,'timed_out':True,'output':output}

def _failure_status(check,sdk_preflight=False):
    if check.get('timed_out'):return 'fail'
    infrastructure_tokens=('Cannot connect to the Docker daemon','error during connect','No such image:','Unable to find image','exec: "flutter": executable file not found')
    if sdk_preflight or any(token in check['output'] for token in infrastructure_tokens):return 'infra_error'
    return 'fail'

def prepare_copy(repo,target):
    repo=pathlib.Path(repo);target=pathlib.Path(target)
    if target.exists():shutil.rmtree(target)
    shutil.copytree(repo,target,ignore=shutil.ignore_patterns('.dart_tool','build','.git','.flutter-plugins*'))
    return target

def grade_repo(repo,output,image=IMAGE,copy=True):
    """Build and grade a candidate by public UI. Returns complete independent evidence."""
    output=pathlib.Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    work=prepare_copy(repo,output/'work') if copy else pathlib.Path(repo).resolve()
    data=output/'data'
    if data.exists():shutil.rmtree(data)
    checks=[]
    base=['docker','run','--rm','--network','none','--cpus','2','--memory','4g','-v',str(work)+':/work/repo','--workdir','/work/repo',image]
    commands=[['flutter','--version','--machine'],['flutter','pub','get','--offline'],['flutter','analyze','--no-pub']]
    tests_added=any((work/'test').rglob('*.dart')) if (work/'test').exists() else False
    if tests_added:commands.append(['flutter','test','--no-pub'])
    commands.append(['flutter','build','linux','--release','--no-pub'])
    for command in commands:
        check=_command(base+command,output);checks.append(check)
        if check['exit_code'] and (command[1] in ('--version','pub','build') or check.get('timed_out')):
            result={'status':_failure_status(check,sdk_preflight=command[1]=='--version'),'checks':checks,'error':'candidate command failed or exceeded its bounded time limit','image':image,'network':'none','agent_tests_present':tests_added}
            (output/'grade.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    bundles=list((work/'build/linux').glob('*/release/bundle'))
    executable=[]
    for bundle in bundles:
        for path in bundle.iterdir():
            if path.is_file() and os.access(path,os.X_OK) and path.read_bytes()[:4]==b'\x7fELF':executable.append(path)
    if len(executable)!=1:raise RuntimeError('cannot uniquely discover Linux app executable: '+str(executable))
    container_executable='/work/repo/'+str(executable[0].relative_to(work))
    gui_base=['docker','run','--rm','--network','none','--cpus','2','--memory','3g','-v',str(work)+':/work/repo','-v',str(CASE/'oracle')+':/oracle:ro','-v',str(ROOT/'scripts')+':/grader/scripts:ro','-v',str(output)+':/evidence',image]
    # Shell receives only a fixed script; executable argument is a Docker argv env value.
    gui=gui_base[:-1]+['-e','EVAL_EXECUTABLE='+container_executable,gui_base[-1],'dbus-run-session','--','sh','-c','Xvfb :99 -screen 0 1280x900x24 > /evidence/xvfb.log 2>&1 & export DISPLAY=:99; sleep 1; python3 /oracle/gui_acceptance.py "$EVAL_EXECUTABLE" /evidence/ui /evidence/data']
    checks.append(_command(gui,output,timeout=120))
    ui=json.loads((output/'ui/gui-result.json').read_text()) if (output/'ui/gui-result.json').exists() else {'status':_failure_status(checks[-1]),'error':'external GUI command timed out' if checks[-1].get('timed_out') else 'external GUI command produced no result'}
    result={'status':'pass' if ui['status']=='pass' and all(c['exit_code']==0 for c in checks) else ui['status'] if ui['status']!='pass' else 'fail','image':image,'network':'none','checks':checks,'gui':ui,'source_hashes':tree_hashes(work),'agent_tests_present':tests_added,'agent_tests_skipped':not tests_added}
    (output/'grade.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

def mutate_reference(kind,target):
    target=prepare_copy(CASE/'reference',target);path=target/'lib/main.dart';text=path.read_text()
    if kind=='omit_restore':
        old='data.map((v) => Note.fromJson(v as Map<String, dynamic>))'
        new='data.take(0).map((v) => Note.fromJson(v as Map<String, dynamic>))'
        assert old in text;text=text.replace(old,new)
    elif kind=='duplicate_edit':
        pattern=r'next\[next.indexWhere\(\s*\(n\) => n.id == existing.id\)\] =\s*updated;'
        text,count=re.subn(pattern,'next.add(updated);',text);assert count==1
    elif kind=='ignore_delete':
        old='.where((n) => n.id != original.id)';assert old in text;text=text.replace(old,'.where((n) => true)')
    else:raise ValueError(kind)
    path.write_text(text);return target

def validate_fixture(output=DEFAULT_OUTPUT):
    output=pathlib.Path(output);output.mkdir(parents=True,exist_ok=True)
    original=fixture_source_hashes()
    records=[]
    for variant,source in [('baseline',CASE/'repo'),('reference',CASE/'reference')]:
        result=grade_repo(source,output/variant);records.append({'variant':variant,**result});print(variant,result['status'],flush=True)
    for kind in ('omit_restore','duplicate_edit','ignore_delete'):
        source=mutate_reference(kind,output/('source-'+kind));result=grade_repo(source,output/kind);records.append({'variant':kind,'semantic_mutation':kind,**result});print(kind,result['status'],result.get('gui',{}).get('error'),flush=True)
    unchanged=original==fixture_source_hashes()
    baseline=records[0];reference=records[1];controls=records[2:]
    valid=unchanged and baseline['status']=='fail' and baseline.get('gui',{}).get('status')=='fail' and reference['status']=='pass' and all(r['status']=='fail' and r.get('gui',{}).get('status')=='fail' and all(c['exit_code']==0 for c in r['checks'][:-1]) for r in controls)
    evidence={'version':2,'case':'W01','image':IMAGE,'network':'none','valid_fixture':valid,'source_bytes_unchanged':unchanged,'source_hashes':original,'records':records,'runtime_evidence_directory':str(output.resolve()),'suggested_limits':{'trajectory_minutes':60,'user_turns':8,'delegation':False,'reason':'Gold requires Linux scaffold/build, real file storage and external GUI cold restarts. Build/driver command durations are recorded; budget accommodates implementation and relevant verification.'},'evidence_tier':'external_linux_release_executable','scope_limits':['No Android/iOS device claims','No external provider or production deployment','Internal app structure and storage format remain unrestricted']}
    (output/'validation.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    summary={'version':2,'case':'W01','valid_fixture':valid,'source_bytes_unchanged':unchanged,'image':IMAGE,'network':'none','variants':[{'variant':r['variant'],'status':r['status'],'gui_requirements':r.get('gui',{}).get('requirements'), 'error':r.get('gui',{}).get('error'),'processes':r.get('gui',{}).get('processes'),'command_exit_codes':[c['exit_code'] for c in r['checks']],'elapsed_seconds':round(sum(c['elapsed_seconds'] for c in r['checks']),3)} for r in records],'runtime_evidence_directory':str(output.resolve()),'source_hashes':original,'suggested_limits':evidence['suggested_limits'],'evidence_tier':evidence['evidence_tier']}
    (CASE/'evidence.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return evidence

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['validate','grade']);p.add_argument('--repo');p.add_argument('--output',type=pathlib.Path,default=DEFAULT_OUTPUT);a=p.parse_args()
    if a.operation=='validate':r=validate_fixture(a.output);raise SystemExit(0 if r['valid_fixture'] else 1)
    if not a.repo:p.error('--repo is required for grade')
    r=grade_repo(a.repo,a.output);print(r['status']);raise SystemExit(0 if r['status']=='pass' else 1)
