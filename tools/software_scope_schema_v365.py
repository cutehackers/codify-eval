"""W02 public documentation scope revision, with unchanged execution guards."""
import argparse
import hashlib
import json
from pathlib import Path
import audit
import collect_schema_v364
import dialogue_schema
import prepare
import report
import software_gui_schema as gui

ROOT = prepare.ROOT
VERSION = 'w02-public-scope-v3.6.5'
CASE = 'W02v365'
MANIFEST = ROOT / 'results/frozen-software-W02-scope-v3.6.5.json'
CORE = ROOT / 'results/frozen-core-scope-v3.6.5.json'
SCHEDULE = ROOT / 'results/schedule-C0-scope-v3.6.5.json'
PLAN = ROOT / 'results/software-W02-scope-revision-plan-v3.6.5.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_case():
    old = ROOT / 'software_cases/W02'
    new = ROOT / ('software_cases/' + CASE)
    old_files = {str(p.relative_to(old)): p for p in old.rglob('*') if p.is_file()}
    new_files = {str(p.relative_to(new)): p for p in new.rglob('*') if p.is_file()}
    if set(old_files) != set(new_files):
        raise ValueError('Scope revision changed fixture file membership')
    for name in old_files:
        if name not in {'metadata.json', 'repo/AGENTS.md'} and sha(old_files[name]) != sha(new_files[name]):
            raise ValueError('Scope revision changed app/oracle/reference/task: ' + name)
    before = json.loads(old_files['metadata.json'].read_text())
    after = json.loads(new_files['metadata.json'].read_text())
    expected = {**before, 'id': CASE, 'allowed_paths': before['allowed_paths'] + ['IMPLEMENTATION.md']}
    if after != expected:
        raise ValueError('Scope metadata changed outside identity/document permission')
    original = old_files['repo/AGENTS.md'].read_text()
    sentence = 'You may change lib/, pubspec.yaml, linux/, add new test/ or integration_test/ files and implementation documentation.'
    addition = ' Implementation documentation must use README.md, IMPLEMENTATION.md, or docs/. Other project-root documentation files are outside the allowed change scope.'
    if sentence not in original or new_files['repo/AGENTS.md'].read_text() != original.replace(sentence, sentence + addition):
        raise ValueError('Public scope changed outside exact document location clarification')
    return prepare.tree_hash(new)


def verify_registration():
    registration = json.loads(MANIFEST.read_text())
    required = {'tools/software_scope_schema_v365.py', 'results/software-W02-scope-revision-plan-v3.6.5.json',
                'results/schedule-C0-scope-v3.6.5.json', 'results/frozen-core-scope-v3.6.5.json'}
    pins = registration.get('source_sha256', {})
    if (registration.get('status') != 'frozen' or registration.get('version') != VERSION
            or not required <= set(pins) or registration.get('same_artifact_reclassification_allowed') is not False):
        raise ValueError('Scope revision is not completely frozen')
    for name, expected in pins.items():
        if sha(ROOT / name) != expected:
            raise ValueError('Frozen scope revision source changed: ' + name)
    if validate_case() != registration.get('case_hash'):
        raise ValueError('Scope fixture hash changed')
    plan = json.loads(PLAN.read_text())
    if registration.get('runs') != plan['replacement_runs']:
        raise ValueError('Scope cohort differs from preregistration')
    rows = registration['runs']
    if (len(rows) != 9 or {(x['condition'], x['repeat']) for x in rows}
            != {(c, n) for c in ('A', 'B', 'C0') for n in (1, 2, 3)}):
        raise ValueError('Scope revision requires all nine conditions/repeats')
    original = json.loads((ROOT / 'results/schedule-C0.json').read_text())['runs']
    selected = json.loads(SCHEDULE.read_text())['runs']
    mapping = dict(zip((x['run_id'] for x in plan['affected_runs_original']), rows))
    if len(selected) != 186 or selected != [mapping.get(x['run_id'], x) for x in original]:
        raise ValueError('Schedule changed outside all nine W02 replacements')
    gui.verify_registration()
    collect_schema_v364.verify_registration()
    return registration


def member(registration, run_id):
    rows = [x for x in registration['runs'] if x['run_id'] == run_id]
    if len(rows) != 1:
        raise ValueError('Run is outside the frozen W02 replacement cohort')
    return rows[0]


def qualified_prepare(condition, repeat):
    registration = verify_registration()
    run_id = f'software-{CASE}-{condition}-{repeat}'
    member(registration, run_id)
    if (ROOT / 'runtime' / run_id).exists() or (ROOT / 'results' / run_id).exists():
        raise ValueError('Scope replacement already exists; no actor retry')
    result = prepare.prepare(CASE, condition, repeat, 'software')
    path = ROOT / 'runtime' / run_id / 'run.json'
    metadata = json.loads(path.read_text())
    if metadata['case_hash'] != registration['case_hash']:
        raise ValueError('Prepared replacement case mismatch')
    # Keep the unchanged original controlled protocol core binding. The separate
    # scope registration owns this fixture revision and selected comparison matrix.
    metadata['scope_revision'] = {'version': VERSION, 'registration': str(MANIFEST),
                                  'registration_sha256': sha(MANIFEST), 'selected_core_sha256': sha(CORE)}
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
    return result


def qualified_grade(run_id):
    registration = verify_registration()
    row = member(registration, run_id)
    metadata_path = ROOT / 'runtime' / run_id / 'run.json'
    metadata = json.loads(metadata_path.read_text())
    if any(metadata.get(key) != row[field] for key, field in
           [('run_id', 'run_id'), ('case_id', 'case'), ('phase', 'phase'), ('condition', 'condition'), ('repeat', 'repeat')]):
        raise ValueError('Replacement identity mismatch')
    if (metadata.get('case_hash') != registration['case_hash'] or metadata.get('scope_revision') !=
            {'version': VERSION, 'registration': str(MANIFEST), 'registration_sha256': sha(MANIFEST),
             'selected_core_sha256': sha(CORE)}):
        raise ValueError('Replacement preparation is not qualified')
    models = metadata.get('model_evidence', [])
    if not models or any(x != {'model': 'gpt-6.1-sol', 'effort': 'medium'} for x in models):
        raise ValueError('Actual actor model mismatch')
    destination = ROOT / 'results' / run_id
    audit_path = destination / 'software-gui-transport-audit-v3.6.5.json'
    if audit_path.exists() or (destination / 'grade.json').exists():
        raise ValueError('Existing grade/audit preserved; no automatic regrade')
    with gui.derivative_mount():
        result = dialogue_schema.qualified_grade(run_id)
    commands = [x['command'] for x in result.get('runtime_evidence', {}).get('checks', [])
                if 'dbus-run-session' in x.get('command', [])]
    mount = str(gui.DERIVATIVE_ROOT / 'scripts') + ':/grader/scripts:ro'
    matched = all([argv[i + 1] for i, value in enumerate(argv[:-1])
                   if value == '-v' and argv[i + 1].endswith(':/grader/scripts:ro')] == [mount]
                  for argv in commands) if commands else None
    grade_path = destination / 'grade.json'
    proof = {'version': VERSION, 'run_id': run_id, 'actual_model_evidence': models,
             'wrapper_sha256': sha(Path(__file__)), 'registration_sha256': sha(MANIFEST),
             'gui_registration_sha256': sha(gui.MANIFEST), 'derivative_sha256': sha(ROOT / gui.DERIVATIVE),
             'run_metadata_sha256': sha(metadata_path), 'expected_gui_mount': mount,
             'actual_gui_docker_argv': commands, 'gui_executed': bool(commands),
             'mount_matches_registered_derivative': matched, 'status': result.get('status'),
             'grade_artifact': {'path': str(grade_path), 'sha256': sha(grade_path)},
             'control_audit_modified': False, 'frozen_grader_result_modified': False}
    with audit_path.open('x') as stream:
        json.dump(proof, stream, ensure_ascii=False, indent=2)
    if matched is False:
        raise ValueError('Actual GUI mount differs from the registered derivative')
    return result


def selected_report():
    verify_registration()
    original_read = report.read_json
    target = ROOT / 'results/schedule-C0.json'
    report.read_json = lambda path: original_read(SCHEDULE if Path(path) == target else path)
    try:
        result = report.aggregate('C0')
    finally:
        report.read_json = original_read
    result.update(schedule_sha256=sha(SCHEDULE), selected_schedule=str(SCHEDULE),
                  original_schedule_sha256=sha(target), scope_revision_registration_sha256=sha(MANIFEST))
    return result


def selected_audit():
    verify_registration()
    original_read = audit.read
    target = ROOT / 'results/schedule-C0.json'
    audit.read = lambda path: original_read(SCHEDULE if Path(path) == target else path)
    try:
        result = audit.audit('C0', CORE.name)
    finally:
        audit.read = original_read
    result.update(selected_schedule=str(SCHEDULE), selected_schedule_sha256=sha(SCHEDULE),
                  scope_revision_registration_sha256=sha(MANIFEST))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['verify', 'prepare', 'grade', 'report', 'audit'])
    parser.add_argument('--condition', choices=['A', 'B', 'C0'])
    parser.add_argument('--repeat', type=int, choices=[1, 2, 3])
    parser.add_argument('--run')
    args = parser.parse_args()
    if args.action == 'prepare':
        value = qualified_prepare(args.condition, args.repeat)
    elif args.action == 'grade':
        value = qualified_grade(args.run)
    elif args.action == 'report':
        value = selected_report()
    elif args.action == 'audit':
        value = selected_audit()
    else:
        value = {'status': 'qualified', 'version': verify_registration()['version']}
    print(json.dumps(value, ensure_ascii=False))
