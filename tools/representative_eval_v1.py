"""Small prepare/grade helper for the human-approved six representative cases.

No native agent dispatch, session authorization framework, model calls or Docker.
Public repositories and frozen graders are separate. Native evidence is retained
by the calling ROOT and later collected as actual observations, not self-report.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'results/improvement-v1/representative-eval-v1-manifest.json'
PYTHON='/Users/junhyounglee/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root):
    result={}
    for p in sorted(Path(root).rglob('*')):
        relative=p.relative_to(root)
        if any(part in ('.git','__pycache__','.pytest_cache') for part in relative.parts):continue
        if p.is_symlink():raise ValueError('Source symlink forbidden: '+str(relative))
        if p.is_file():result[str(relative)]={'bytes':p.stat().st_size,'mode':p.stat().st_mode&0o777,'sha256':digest(p)}
    return result


def load_manifest():
    d=json.loads(MANIFEST.read_text())
    if d['helper_sha256']!=digest(__file__):raise ValueError('Frozen helper changed')
    if d['unittest_runner_sha256']!=digest(ROOT/'tools/representative_unittest_runner_v1.py'):
        raise ValueError('Frozen unittest runner changed')
    interpreter=d['interpreter']
    actual_version=subprocess.run([PYTHON,'--version'],check=True,capture_output=True,text=True,timeout=10).stdout.strip()
    if interpreter!={'path':PYTHON,'version':actual_version,'sha256':digest(PYTHON)}:
        raise ValueError('Frozen absolute Python interpreter changed')
    for case,record in d['cases'].items():
        if inventory(ROOT/record['path'])!=record['inventory']:raise ValueError('Frozen case changed: '+case)
    for condition,record in d['skills'].items():
        if record is not None and inventory(ROOT/record['path'])!=record['inventory']:
            raise ValueError('Frozen skill changed: '+condition)
    return d


def row_folder(case,condition):
    if case not in ('R1','R2','R3','R4','R5','R6') or condition not in ('A','C0','C24'):
        raise ValueError('Registered representative case and condition required')
    return ROOT/'runtime/representative-v1'/f'{case}-{condition}-1'


def save_new(path,value):
    with Path(path).open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')


def prepare(case,condition):
    begin=time.time();manifest=load_manifest();folder=row_folder(case,condition)
    folder.mkdir(parents=True,exist_ok=False)
    record=manifest['cases'][case];public=ROOT/record['path']/'public';repo=folder/'repo'
    shutil.copytree(public,repo)
    selected=manifest['skills'][condition]
    if selected is not None:shutil.copytree(ROOT/selected['path'],repo/'.agents/skills/codify')
    for argv in (['git','init','-q',str(repo)],['git','-C',str(repo),'config','user.name','Evaluation'],
                 ['git','-C',str(repo),'config','user.email','evaluation@localhost'],
                 ['git','-C',str(repo),'add','.'],['git','-C',str(repo),'commit','-qm','Initial isolated fixture']):
        subprocess.run(argv,check=True,capture_output=True,timeout=30)
    state={'schema_version':1,'case':case,'condition':condition,'repo':str(repo),
        'manifest_sha256':digest(MANIFEST),'started_at':begin,'deadline':begin+1200,
        'initial_inventory':inventory(repo),'editable_paths':record['editable_paths'],
        'expected_private_tests':record['expected_private_tests'],'actual_model_dispatched':False}
    save_new(folder/'preparation.json',state)
    return {'repo':str(repo),'deadline':state['deadline'],'model':'gpt-6.1-sol','reasoning':'medium',
            'preparation_sha256':digest(folder/'preparation.json')}


def grade(case,condition,preparation_sha256):
    manifest=load_manifest();folder=row_folder(case,condition)
    if type(preparation_sha256) is not str or not re.fullmatch('[0-9a-f]{64}',preparation_sha256) or digest(folder/'preparation.json')!=preparation_sha256:
        raise ValueError('Original ROOT-observed preparation hash required')
    state=json.loads((folder/'preparation.json').read_text())
    record=manifest['cases'][case]
    if state['case']!=case or state['condition']!=condition or state['repo']!=str(folder/'repo') or state['editable_paths']!=record['editable_paths'] or state['expected_private_tests']!=record['expected_private_tests']:
        raise ValueError('Original preparation row/scope/count differs from frozen manifest')
    if state['manifest_sha256']!=digest(MANIFEST):raise ValueError('Original manifest changed')
    if (folder/'grading.json').exists():raise ValueError('Grade cannot repeat or hide original result')
    repo=Path(state['repo']);current=inventory(repo);initial=state['initial_inventory']
    changed=sorted(p for p in set(current)|set(initial) if current.get(p)!=initial.get(p))
    outside=sorted(set(changed)-set(state['editable_paths']))
    private=ROOT/manifest['cases'][case]['path']/'private/tests'
    result_path=folder/'unittest-completion.json'
    if result_path.exists():raise ValueError('Prior private unittest result exists; no repeat')
    argv=[PYTHON,'-B',str(ROOT/'tools/representative_unittest_runner_v1.py'),str(private),str(result_path)]
    remaining=min(120,max(1,int(state['deadline']-time.time())))
    env={**os.environ,'PYTHONPATH':str(repo),'PYTHONDONTWRITEBYTECODE':'1'}
    started=time.time();timed_out=False
    try:
        result=subprocess.run(argv,cwd=repo,env=env,capture_output=True,text=True,timeout=remaining)
        stdout,stderr,code=result.stdout,result.stderr,result.returncode
    except subprocess.TimeoutExpired as e:
        timed_out=True;code=124
        stdout=e.stdout or '';stderr=e.stderr or ''
        if isinstance(stdout,bytes):stdout=stdout.decode(errors='replace')
        if isinstance(stderr,bytes):stderr=stderr.decode(errors='replace')
    (folder/'private-tests.stdout').write_text(stdout);(folder/'private-tests.stderr').write_text(stderr)
    completion=None;normal_complete=False;count=None
    try:
        completion=json.loads(result_path.read_text())
        count=completion['tests_run']
        normal_complete=(type(count) is int and count==state['expected_private_tests']
            and completion['discovered']==count and completion['normal_runner_completion'] is True
            and completion['was_successful'] is True and all(type(completion[k]) is int and completion[k]==0
                for k in ('failures','errors','skipped','expected_failures','unexpected_successes')))
    except (OSError,ValueError,KeyError,TypeError):pass
    # Graders may not mutate public source or selected skill.
    unchanged_after=inventory(repo)==current
    frozen_inputs_unchanged=True;freeze_error=None
    try:load_manifest()
    except (ValueError,OSError) as error:
        frozen_inputs_unchanged=False;freeze_error=str(error)
    outcome={'schema_version':1,'case':case,'condition':condition,'private_test_argv':argv,
        'exit_code':code,'timed_out':timed_out,'tests_observed':count,
        'unittest_completion':completion,'normal_test_completion':normal_complete,
        'expected_private_tests':state['expected_private_tests'],'changed_paths':changed,
        'outside_scope':outside,'grader_did_not_mutate_source':unchanged_after,
        'frozen_inputs_unchanged':frozen_inputs_unchanged,'freeze_error':freeze_error,
        'software_pass':code==0 and normal_complete and count==state['expected_private_tests'] and not outside and unchanged_after and frozen_inputs_unchanged,
        'original_clock_started_at':state['started_at'],'finished_at':time.time(),
        'whole_seconds':time.time()-state['started_at'],'grading_seconds':time.time()-started,
        'deadline_exceeded':time.time()>state['deadline'],'token_gate':False,
        'native_usage_observed':False,'population_superiority_claim':False}
    if outcome['deadline_exceeded']:outcome['software_pass']=False
    save_new(folder/'grading.json',outcome)
    return outcome


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['prepare','grade'])
    p.add_argument('case');p.add_argument('condition');p.add_argument('--preparation-sha256');a=p.parse_args()
    result=prepare(a.case,a.condition) if a.operation=='prepare' else grade(a.case,a.condition,a.preparation_sha256)
    print(json.dumps(result,sort_keys=True))
