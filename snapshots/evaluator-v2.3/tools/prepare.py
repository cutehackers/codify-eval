"""Prepare an isolated per-trajectory container and a neutral agent request."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
MODEL='gpt-6.1-sol'

def case_directory(case_id:str)->Path:
    return ROOT/('software_cases' if case_id.startswith('W') else 'contract_cases' if case_id.startswith('S') else 'fixtures')/case_id

def tree_hash(path:Path)->str:
    digest=hashlib.sha256()
    for item in sorted(path.rglob('*')):
        if item.is_file() and not any(p in {'.git','.dart_tool','build','__pycache__'} for p in item.relative_to(path).parts):
            digest.update(item.relative_to(path).as_posix().encode()+b'\0'+item.read_bytes())
    return digest.hexdigest()

def prepare(case_id:str,condition:str,repeat:int=1,phase:str='pilot')->dict:
    case_root=case_directory(case_id)
    case=json.loads((case_root/'metadata.json').read_text())
    run_id=f'{phase}-{case_id}-{condition}-{repeat}'
    run_root=ROOT/'runtime'/run_id
    if run_root.exists(): raise ValueError(f'Run already exists: {run_id}; preserve original evidence')
    repo=run_root/'repo'
    shutil.copytree(case_root/'repo',repo)
    seed_files={p.relative_to(repo).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in repo.rglob('*') if p.is_file()}
    dirty=case.get('initial_dirty')
    if dirty:
        (repo/dirty['path']).write_text(dirty['head_content'])
    git=['git','-C',str(repo)]
    for command in [['init','-q'],['config','user.name','Evaluation Fixture'],['config','user.email','fixture@localhost'],['add','.'],['commit','-q','-m','Fixture baseline']]:
        subprocess.run(git+command,check=True,capture_output=True)
    if dirty: (repo/dirty['path']).write_text(dirty['working_content'])
    skill_hash=None
    if condition!='A':
        source=ROOT/'snapshots'/condition
        if not source.exists(): raise ValueError(f'Missing frozen skill {condition}')
        shutil.copytree(source,repo/'.agents/skills/codify')
        skill_hash=tree_hash(source)
    image=json.loads((ROOT/'runtime/image.json').read_text())['image_id']
    container='codify-'+run_id.lower()
    subprocess.run(['docker','run','-d','--name',container,'--network','none',
        '-v',f'{repo}:/work/repo','-w','/work/repo',image,'sleep','infinity'],check=True,capture_output=True)
    metadata={'run_id':run_id,'case_id':case_id,'condition':condition,'repeat':repeat,'phase':phase,
        'model':MODEL,'effort':'medium','container':container,'image_id':image,'skill_hash':skill_hash,
        'case_hash':tree_hash(case_root),'seed_files':seed_files,'started_at':time.time(),'status':'prepared',
        'agent_path':None,'turns':[]}
    if case_id.startswith('W'):
        limits=case['proposed_limits']
        metadata.update(time_limit_seconds=limits['trajectory_minutes']*60,user_turn_limit=limits['user_turns'])
    (run_root/'run.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    task=case.get('turn_requests',[None])[0] or (case_root/'task.md').read_text()
    # Keep task semantics the same; explicit skill selection is the treatment.
    task=task.replace('$codify ', '') if condition=='A' else task
    if condition!='A' and '$codify' not in task: task='$codify\n'+task
    controls=f'''You are the implementation owner for one independent software task. Use only the task artifacts in the isolated container. The initial request follows below.
All repository inspection, file changes, git inspection and verification MUST use this command interface through exec_command:
python3 {ROOT}/tools/agent_io.py --run {run_id} --cmd '<shell command inside the container>'
The container working directory is /work/repo. Flutter, Dart, Python and git are installed. Use flutter pub get --offline when resolving dependencies. Network access is disabled. Do not read host files, scripts, skill catalogs, other runs or other tools/connectors. Do not inspect the command-interface implementation. It is only the transport. Do not read oracle or reference implementations; none are provided in the container. Do not spawn agents for this bounded task. Keep the original user scope, implement and verify the requested observable behavior. No commits. Reply in Korean with the outcome and actual verification evidence. If a consequential decision is missing, ask the concrete question and wait; do not invent acceptance or authorization. Do not disclose thoughts or private reasoning.
'''
    # Model-level tools exist outside the container; external transcript audit enforces this boundary.
    if condition!='A':
        controls+='Use the provided Codify skill at /work/repo/.agents/skills/codify/SKILL.md and only its referenced resources when relevant.\n'
    prompt=controls+'\nUSER TASK\n'+task
    (run_root/'request.txt').write_text(prompt)
    metadata['prompt_hash']=hashlib.sha256(prompt.encode()).hexdigest()
    (run_root/'run.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    return {'run_id':run_id,'prompt_file':str(run_root/'request.txt'),'container':container,'model':MODEL,'effort':'medium'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('case');p.add_argument('condition');p.add_argument('--repeat',type=int,default=1);p.add_argument('--phase',default='pilot')
    a=p.parse_args();print(json.dumps(prepare(a.case,a.condition,a.repeat,a.phase),ensure_ascii=False))
