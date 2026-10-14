#!/usr/bin/env python3
"""Verify frozen fixtures and semantic negative controls in the pinned offline image."""
import argparse
import concurrent.futures
import hashlib
import json
import pathlib
import shutil
import subprocess
import time

ROOT=pathlib.Path(__file__).resolve().parents[1]
IMAGE='sha256:9751b1bbd374a218e0fe7dcd362e478f2b8bb5453dbed90658da8dd0b2be3638'
OUTPUT=ROOT/'fixtures/container-validation.json'
RUNTIME=ROOT/'runtime/validation'

def fixture_hashes():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT/'fixtures').rglob('*'))
            if p.is_file() and p!=OUTPUT}

JOB='''import json,pathlib,subprocess,time
result={'checks':[]}
def check(variant,args):
 start=time.time();p=subprocess.run(args,cwd='/cases/'+variant if variant else '/cases',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 result['checks'].append({'variant':variant,'command':args,'exit_code':p.returncode,'elapsed_seconds':round(time.time()-start,3),'output':p.stdout})
 return p.returncode
check(None,['flutter','--version','--machine'])
for variant in ('baseline','reference','negative_control'):
 if check(variant,['flutter','pub','get','--offline'])==0:
  check(variant,['flutter','test','test/acceptance_test.dart','--reporter','expanded'])
  if variant=='reference':check(variant,['flutter','analyze','--no-pub'])
pathlib.Path('/cases/result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
'''

def classify(check):
    if check['exit_code']==0:return 'pass'
    output=check['output']
    if any(token in output for token in ('Failed to load','Error: Method not found:','Error: Type','Error: Expected','Error: Undefined','Error: The method','Error: Not found:')):
        return 'compile_error'
    if 'Some tests failed' in output or 'Test failed' in output:
        return 'semantic_failure'
    return 'infrastructure_error'

def prepare_case(id):
    base=ROOT/'fixtures'/id;target=RUNTIME/id
    if target.exists():shutil.rmtree(target)
    for variant,source in [('baseline','repo'),('reference','reference'),('negative_control','reference')]:
        shutil.copytree(base/source,target/variant)
        shutil.copytree(base/'oracle/test',target/variant/'test',dirs_exist_ok=True)
    if id=='E05':
        path=target/'negative_control/lib/repository.dart'
        old='if (entry.id == id) return entry;'
        new='if (entry.id == id) return null;'
        text=path.read_text();assert old in text;path.write_text(text.replace(old,new))
        mutation={'path':'lib/repository.dart','description':'Return missing record for a valid ID while retaining every public class and import.'}
    else:
        differing=[]
        for gold in sorted((base/'reference/lib').rglob('*.dart')):
            relative=gold.relative_to(base/'reference');start=base/'repo'/relative
            if start.exists() and start.read_bytes()!=gold.read_bytes():differing.append(relative)
        assert differing,id
        relative=differing[0]
        shutil.copyfile(base/'repo'/relative,target/'negative_control'/relative)
        mutation={'path':str(relative),'description':'Restore starting implementation of this existing module; preserve other gold modules and all oracle tests.'}
    (target/'job.py').write_text(JOB)
    return target,mutation

def validate_case(id):
    target,mutation=prepare_case(id)
    command=['docker','run','--rm','--network','none','--cpus','2','--memory','3g','-v',str(target)+':/cases','--workdir','/cases',IMAGE,'python3','/cases/job.py']
    started=time.time();p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if not (target/'result.json').exists():return {'id':id,'docker_command':command,'docker_exit':p.returncode,'docker_output':p.stdout,'blocker':'container produced no result'}
    record=json.loads((target/'result.json').read_text());record.update({'id':id,'docker_command':command,'docker_exit':p.returncode,'docker_output':p.stdout,'elapsed_seconds':round(time.time()-started,3),'negative_control_mutation':mutation})
    for check in record['checks']:
        if check['command'][1]=='test':check['classification']=classify(check)
    def get(variant,op):return next((c for c in record['checks'] if c['variant']==variant and c['command'][1]==op),None)
    baseline=get('baseline','test');gold=get('reference','test');negative=get('negative_control','test');analyze=get('reference','analyze')
    record['baseline_semantic_failure']=bool(baseline and baseline.get('classification')=='semantic_failure')
    record['reference_pass']=bool(gold and gold['exit_code']==0 and analyze and analyze['exit_code']==0)
    record['negative_control_semantic_failure']=bool(negative and negative.get('classification')=='semantic_failure')
    record['all_dependencies_offline']=all(get(v,'pub') and get(v,'pub')['exit_code']==0 for v in ('baseline','reference','negative_control'))
    record['valid']=record['baseline_semantic_failure'] and record['reference_pass'] and record['negative_control_semantic_failure'] and record['all_dependencies_offline']
    if not record['valid']:
        record['blocker']='Full baseline oracle does not compile because starting E05 lacks requested EntryDetail. Gold and semantic negative control are graded independently.' if id=='E05' and baseline and baseline.get('classification')=='compile_error' else 'Inspect command outputs for failed validity criteria.'
    print(id,'baseline:',baseline.get('classification') if baseline else 'missing','gold:',record['reference_pass'],'negative:',negative.get('classification') if negative else 'missing',flush=True)
    return record

E05_PROBE="""import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';
void main() {
  testWidgets('existing list API opens record body', (tester) async {
    final repository=EntryRepository(const [Entry(42,'첫 기록','첫 본문'),Entry(91,'둘째 기록','둘째 본문')]);
    await tester.pumpWidget(EntryApp(repository:repository));
    await tester.tap(find.byKey(const ValueKey('entry-91')));
    await tester.pumpAndSettle();
    expect(find.text('둘째 본문'),findsOneWidget);
  });
}
"""
# ValueKey is provided by foundation through material, not by flutter_test.
E05_PROBE="import 'package:flutter/material.dart';\n"+E05_PROBE

def supplements(result):
    target=RUNTIME/'E05/baseline_navigation_probe'
    if target.exists():shutil.rmtree(target)
    shutil.copytree(ROOT/'fixtures/E05/repo',target)
    (target/'test').mkdir();(target/'test/acceptance_test.dart').write_text(E05_PROBE)
    commands=[]
    for args in (['flutter','pub','get','--offline'],['flutter','test','test/acceptance_test.dart','--reporter','expanded']):
        command=['docker','run','--rm','--network','none','--cpus','2','--memory','3g','-v',str(target)+':/work/repo','--workdir','/work/repo',IMAGE,*args]
        started=time.time();p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        commands.append({'variant':'baseline_navigation_probe','command':args,'docker_command':command,'exit_code':p.returncode,'elapsed_seconds':round(time.time()-started,3),'output':p.stdout})
    commands[-1]['classification']=classify(commands[-1])
    case=next(r for r in result['cases'] if r['id']=='E05')
    case['supporting_baseline_navigation_probe']={'source':E05_PROBE,'source_sha256':hashlib.sha256(E05_PROBE.encode()).hexdigest(),'uses_existing_public_api_only':True,'checks':commands,'semantic_failure':commands[-1]['classification']=='semantic_failure','limitation':'Supports navigation omission detection; full baseline oracle still fails compilation due to absent requested EntryDetail.'}
    command=['docker','run','--rm','--network','none',IMAGE,'sh','-c','command -v xvfb-run; command -v clang; command -v cmake; command -v ninja; pkg-config --modversion gtk+-3.0; flutter config --list']
    p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    result['linux_integration_inspection']['capability_check']={'command':command,'exit_code':p.returncode,'output':p.stdout}
    result['summary']['supporting_baseline_semantic_failures']=sum(r.get('supporting_baseline_navigation_probe',{}).get('semantic_failure',False) for r in result['cases'])
    result['summary']['baseline_with_semantic_evidence']=sum(r.get('baseline_semantic_failure',False) or r.get('supporting_baseline_navigation_probe',{}).get('semantic_failure',False) for r in result['cases'])
    result['fixture_hashes_after']=fixture_hashes();result['fixture_bytes_unchanged']=result['fixture_hashes_before']==result['fixture_hashes_after']
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('E05 supporting probe:',commands[-1]['classification'],flush=True)
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--ids',nargs='*');p.add_argument('--supplement-only',action='store_true');args=p.parse_args()
    if args.supplement_only:
        result=supplements(json.loads(OUTPUT.read_text()))
        return 0 if result['fixture_bytes_unchanged'] and result['summary']['baseline_with_semantic_evidence']==len(result['cases']) else 1
    ids=args.ids or [f'E{i:02}' for i in range(1,13)]+[f'H{i:02}' for i in range(1,5)]
    before=fixture_hashes();start=time.time();RUNTIME.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:records=list(pool.map(validate_case,ids))
    after=fixture_hashes()
    result={'image':IMAGE,'network':'none','max_parallel_containers':2,'elapsed_seconds':round(time.time()-start,3),'fixture_hashes_before':before,'fixture_hashes_after':after,'fixture_bytes_unchanged':before==after,'cases':records,'summary':{'case_count':len(records),'baseline_semantic_failures':sum(r.get('baseline_semantic_failure',False) for r in records),'gold_passes':sum(r.get('reference_pass',False) for r in records),'negative_control_semantic_failures':sum(r.get('negative_control_semantic_failure',False) for r in records),'valid_cases':sum(r.get('valid',False) for r in records)},'linux_integration_inspection':{'capabilities_verified_by_readonly_command':['command -v xvfb-run','command -v clang','command -v cmake','command -v ninja','pkg-config --modversion gtk+-3.0','flutter config --list'],'observed_capabilities':{'xvfb-run':'/usr/bin/xvfb-run','clang':'/usr/bin/clang','cmake':'/usr/bin/cmake','ninja':'/usr/bin/ninja','gtk_version':'3.24.41','enable_linux_desktop':True},'cases':['E05','E12'],'framework':'Flutter','starting_platform_scaffold':False,'required_actions':['Create Linux platform scaffold in throwaway copy using flutter create --platforms=linux .','Add SDK integration_test dependency in grader copy','Author integration harness invoking original public app API','Use xvfb-run flutter test integration_test/... -d linux in pinned image'],'provided_image_capabilities':['Linux Flutter artifacts precached','xvfb','GTK development libraries','clang','cmake','ninja','pkg-config'],'executed':False,'limitation':'Widget acceptance is executed. Linux app integration is only inspected here; integration grader belongs to root.'}}
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    result=supplements(result)
    print(json.dumps(result['summary']),flush=True)
    return 0 if before==after and all(r.get('valid') for r in records) else 1
if __name__=='__main__':raise SystemExit(main())
