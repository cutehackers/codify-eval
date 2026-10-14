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
    probe=phase.startswith('control-probe')
    if not probe and phase not in {'primary','auxiliary','software','heldout'}:
        raise ValueError('Choose a preregistered comparison phase or a control-probe phase')
    core_path=ROOT/'results/frozen-core-v3.6.json'
    evaluation_core=None
    if core_path.exists():
        evaluation_core={'path':str(core_path),'sha256':hashlib.sha256(core_path.read_bytes()).hexdigest()}
    elif not probe:
        raise ValueError('Frozen evaluation core v3.6 must exist before comparison preparation')
    cohort=None
    if case_id=='S03' and phase=='auxiliary':
        cohort_path=ROOT/'results/controlled-dialogue-cohort-v3.6.json'
        registered=json.loads(cohort_path.read_text())
        if run_id not in {entry['run_id'] for entry in registered['runs']}:
            raise ValueError('Run is not in the preregistered controlled dialogue cohort')
        cohort={'path':str(cohort_path),'sha256':hashlib.sha256(cohort_path.read_bytes()).hexdigest()}
    rules=case.get('decision_rules',[])
    fixed_second_turn=len(case.get('turn_requests',[]))>1 or (
        isinstance(rules,list) and bool(rules) and
        any(isinstance(rules[0].get(key),str) for key in ('reply','choice')))
    if fixed_second_turn:
        # Import lazily: dialogue_control uses preparation's shared path helpers.
        from dialogue_control import (PROTOCOL, INPUT_PATH, READ_COMMAND, followup,
                                      source_selector, expected_input, container_evidence)
        selector=source_selector(case)
        controlled_input=expected_input(case,selector)
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
    controls_directory=run_root/'control-inputs'
    controls_directory.mkdir()
    subprocess.run(['docker','run','-d','--name',container,'--network','none',
        '-v',f'{repo}:/work/repo','-v',f'{controls_directory}:/eval-input:ro',
        '-w','/work/repo',image,'sleep','infinity'],check=True,capture_output=True)
    metadata={'run_id':run_id,'case_id':case_id,'condition':condition,'repeat':repeat,'phase':phase,
        'model':MODEL,'effort':'medium','container':container,'image_id':image,'skill_hash':skill_hash,
        'case_hash':tree_hash(case_root),'seed_files':seed_files,'started_at':time.time(),'status':'prepared',
        'agent_path':None,'turns':[]}
    if evaluation_core is not None:
        metadata['evaluation_core']=evaluation_core
    if fixed_second_turn:
        metadata['dialogue_protocol']={
            'protocol':PROTOCOL,'selector':selector,
            'source_metadata':str(case_root/'metadata.json'),
            'source_metadata_sha256':hashlib.sha256((case_root/'metadata.json').read_bytes()).hexdigest(),
            'input_sha256':hashlib.sha256(controlled_input).hexdigest(),
            'input_path':str(controls_directory/'turn-2.txt'),
            'container_input_path':INPUT_PATH,'read_command':READ_COMMAND,
            'followup_sha256':hashlib.sha256(followup(run_id).encode()).hexdigest(),
            'tool_hashes':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                           for name in ('tools/dialogue_control.py','tools/grade.py')},
            'container_identity':container_evidence(metadata,controls_directory)}
        if cohort is not None:
            metadata['dialogue_protocol']['cohort']=cohort
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
If a command-interface exec_command returns a session_id, you may poll only that returned session using tools.write_stdin with empty or omitted chars. This is solely to read the same command's eventual result. Do not send input, poll any other session, or combine polling with another tool. Use a literal session_id and one standalone text(await tools.write_stdin(...)) call.
'''
    # Dialogue is transported by the evaluator, not actor-to-coordinator tools.
    if case.get('decision_rules') or len(case.get('turn_requests',[]))>1:
        controls+='For a missing product decision, state the concrete question in your FINAL response and end the turn. Do not use collaboration messaging, wait/sleep tools, request-input tools or other channels to ask or wait. The evaluator will deliver the fixed human answer as a follow-up in this same session. An unresolved question is not permission to implement the policy.\n'
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
