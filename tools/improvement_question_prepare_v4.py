"""Public-only deliberate runtime controls. Never software/comparative outcomes."""
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import time

from prepare import ROOT, tree_hash
from improvement_software_artifacts_v3 import atomic_json
from improvement_question_branch_v3 import INITIAL_TRANSPORT, CASES


def case_directory(case_id):
    assert case_id in CASES
    return ROOT / 'improvement_cases/fresh-question-cohort-v2' / case_id


def prepare(case_id, condition, repeat=1, phase='control-probe-natural-question-v1'):
    assert case_id in CASES and condition in {'A', 'C0', 'C16'}
    assert phase in {'control-probe-natural-question-v1', 'control-probe-natural-question-runtime-v1', 'control-probe-natural-question-runtime-v2', 'control-probe-natural-question-runtime-v3'} and repeat == 1
    if phase in {'control-probe-natural-question-runtime-v1', 'control-probe-natural-question-runtime-v2', 'control-probe-natural-question-runtime-v3'}:
        assert condition == 'A', 'Qualification controls never allocate a candidate'
    case = case_directory(case_id)
    run_id = f'{phase}-{case_id}-{condition}-{repeat}'
    folder = ROOT / 'runtime' / run_id
    assert not folder.exists()
    repo = folder / 'repo'
    shutil.copytree(case / 'repo', repo)
    seed = {p.relative_to(repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in repo.rglob('*') if p.is_file()}
    git = ['git', '-C', str(repo)]
    for command in (['init', '-q'], ['config', 'user.name', 'Evaluation Fixture'],
                    ['config', 'user.email', 'fixture@localhost'], ['add', '.'],
                    ['commit', '-q', '-m', 'Fixture baseline']):
        subprocess.run(git + command, check=True, capture_output=True)
    skill_hash = None
    if condition != 'A':
        skill = ROOT / 'snapshots' / condition
        shutil.copytree(skill, repo / '.agents/skills/codify')
        skill_hash = tree_hash(skill)
    image = json.loads((ROOT / 'runtime/image.json').read_bytes())['image_id']
    controls = folder / 'control-inputs'
    controls.mkdir()
    container = 'codify-' + run_id.lower()
    subprocess.run(['docker', 'run', '-d', '--name', container, '--network', 'none',
                    '-v', f'{repo}:/work/repo', '-v', f'{controls}:/eval-input:ro',
                    '-w', '/work/repo', image, 'sleep', 'infinity'],
                   check=True, capture_output=True, timeout=30)
    metadata = {'run_id': run_id, 'case_id': case_id, 'condition': condition,
                'repeat': repeat, 'phase': phase, 'model': 'gpt-6.1-sol', 'effort': 'medium',
                'container': container, 'image_id': image, 'skill_hash': skill_hash,
                'case_hash': tree_hash(case), 'seed_files': seed, 'started_at': time.time(),
                'status': 'prepared', 'agent_path': None, 'turns': []}
    task = (case / 'public/request.md').read_text()
    if condition != 'A':
        task = '$codify\n' + task
    prompt = (
        'You are the implementation owner for one independent software task. '
        'Use only the supplied task artifacts in the isolated container.\n'
        'All repository inspection, edits, git inspection and verification MUST use '
        'this command interface through exec_command:\n'
        f"python3 {ROOT}/tools/agent_io.py --run {run_id} --cmd '<shell command inside the container>'\n"
        'The container working directory is /work/repo. Flutter, Dart, Python and git '
        'are installed. Use flutter pub get --offline for dependencies. Network is disabled. '
        'Do not read host files, scripts, skill catalogs, other runs, oracle or reference files. '
        'Do not inspect the command-interface implementation or use other tools/connectors. '
        'Do not spawn agents for this bounded task. No commits. Implement and verify the '
        'requested behavior within the original scope. Reply in Korean with actual evidence. '
        'Do not disclose private reasoning.\n'
        'If exec_command returns a session_id, poll only that returned session using '
        'a standalone text(await tools.write_stdin(...)) with a literal session_id and '
        'empty or omitted chars. Do not combine polling with another tool.\n'
        + INITIAL_TRANSPORT + '\n')
    if condition != 'A':
        prompt += ('Use the provided Codify skill at /work/repo/.agents/skills/codify/SKILL.md '
                   'and only its referenced resources when relevant.\n')
    prompt += '\nUSER TASK\n' + task
    if phase == 'control-probe-natural-question-runtime-v3':
        assert condition == 'A'
        mode = 'deadline' if case_id == 'Q05' else 'failure'
        if mode == 'deadline':
            prompt = (
                'This is a deliberate owned-product deadline runtime control, not a software outcome evaluation. '
                'The initial host request read is complete. Do not inspect or modify the repository, use '
                'connectors, run commands, spawn agents, or message anyone. Your next tool call must be '
                'clock.sleep with duration_ms=60000. Repeat this same60-second native wait thirty times '
                'without sending a final answer before all thirty waits complete. The root owns the original '
                '1200-second allocation clock and will interrupt you. Each individual wait is at most60s. '
                'Do not reset, infer, extend or manage that clock. After all waits finish, report their elapsed '
                'times only. This is the sole allowed diagnostic tool channel.'
            )
        else:
            prompt = (
                'This is a deliberate owned-product failure runtime control, not a software outcome evaluation. '
                'The initial host request read is complete. Your next action must be exactly one functions.exec '
                'call that executes the following command through tools.exec_command and text()s its result:\n'
                f"python3 {ROOT}/tools/agent_io.py --run {run_id} --cmd 'exit 7'\n"
                'This is a deliberate command failure. Report its actual inner exit status in Korean and finish. '
                'Do not retry it, inspect or modify repository files, run another command, poll unless this '
                'specific command returned a live session_id, use connectors, spawn agents, or message anyone.'
            )
        metadata['runtime_control_scenario'] = mode
    (folder / 'request.txt').write_text(prompt)
    metadata['prompt_hash'] = hashlib.sha256(prompt.encode()).hexdigest()
    atomic_json(folder / 'run.json', metadata, exclusive=True)
    return {'run_id': run_id, 'prompt_file': str(folder / 'request.txt'),
            'container': container, 'model': 'gpt-6.1-sol', 'effort': 'medium'}
