"""Registered shared GUI driver mount, leaving frozen graders and cases intact."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import dialogue_schema
import grade
import software_fixtures
import w02_fixtures
from prepare import ROOT

VERSION = 'software-gui-transport-v3.6.3'
PLAN = ROOT/'results/software-gui-transport-revision-plan-v3.6.3.json'
MANIFEST = ROOT/'results/frozen-software-gui-transport-v3.6.3.json'
DERIVATIVE_ROOT = ROOT/'results/gui-transport-v3.6.3/runtime'
DERIVATIVE = 'results/gui-transport-v3.6.3/runtime/scripts/software_runtime.py'
REQUIRED_PINS = {'tools/software_gui_schema.py', 'tools/software_gui_schema_probes.py', DERIVATIVE,
    'scripts/software_runtime.py', 'tools/software_fixtures.py', 'tools/w02_fixtures.py',
    'tools/grade.py', 'tools/prepare.py', 'tools/finalize.py', 'tools/collect.py', 'tools/transport.py',
    'tools/dialogue_control.py', 'tools/dialogue_schema.py', 'tools/collect_schema.py',
    'results/frozen-core-v3.6.json', 'results/frozen-native-schema-v3.6.1.json',
    'results/frozen-escaped-template-collection-v3.6.2.json', 'results/frozen-software-cohort-launch-v3.6.2.json',
    'results/frozen-software-cohort-restart-v3.6.2.json', 'results/software-cohort-restart-registration-v3.6.2.json',
    'results/software-gui-transport-revision-plan-v3.6.3.json',
    'results/software-W01-input-driver-validity-review-v3.6.2.json', 'docs/spec.md'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def candidate_preflight():
    """Qualification-only source check. Does not authorize formal actor grading."""
    plan = json.loads(PLAN.read_text())
    rows = plan.get('affected_cohort', [])
    expected = {f'software-{case}-{condition}-{repeat}' for case in ('W01','W02')
                for condition in ('A','B','C0') for repeat in (1,2,3)}
    if (len(rows) != 18 or {row.get('run_id') for row in rows} != expected
            or plan.get('replacement_actors_started') != 0 or plan.get('historical_results_reclassification') is not False):
        raise ValueError('GUI qualification requires preregistered complete all18 cohort')
    frozen_restart = json.loads((ROOT/'results/frozen-software-cohort-restart-v3.6.2.json').read_text())
    original_registration = json.loads((ROOT/'results/software-cohort-restart-registration-v3.6.2.json').read_text())
    if rows != frozen_restart.get('runs') or rows != original_registration.get('runs'):
        raise ValueError('GUI cohort differs from original preregistered order')
    for row in rows:
        match = re.fullmatch(r'software-(W01|W02)-(A|B|C0)-([123])', row['run_id'])
        canonical = {'run_id':row['run_id'],'phase':'software','case':match.group(1),
                     'condition':match.group(2),'repeat':int(match.group(3))}
        if row != canonical:raise ValueError('GUI cohort row fields disagree with canonical run identity')
    for name, sha in plan['source_sha256'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('Preregistered original GUI source changed: '+name)
    old = (ROOT/'scripts/software_runtime.py').read_text()
    new = (ROOT/DERIVATIVE).read_text()
    start = old.index('    def enter('); end = old.index('    def present(', start)
    new_start = new.index('    def enter('); new_end = new.index('    def present(', new_start)
    if old[:start] != new[:new_start] or old[end:] != new[new_end:]:
        raise ValueError('GUI derivative changed outside GuiDriver.enter')
    for manifest_name in ('results/frozen-software-cohort-launch-v3.6.2.json',
                          'results/frozen-software-cohort-restart-v3.6.2.json', 'results/frozen-core-v3.6.json','results/frozen-native-schema-v3.6.1.json',
                          'results/frozen-escaped-template-collection-v3.6.2.json'):
        frozen = json.loads((ROOT/manifest_name).read_text())
        if manifest_name.endswith('frozen-core-v3.6.json'):
            if frozen.get('core_version') != 'v3.6' or frozen.get('freeze_revision') != 2:
                raise ValueError('Wrong frozen core')
            pins = frozen['grader_hashes']
        else:
            if manifest_name.endswith(('frozen-native-schema-v3.6.1.json','frozen-escaped-template-collection-v3.6.2.json')) and frozen.get('status') != 'frozen':
                raise ValueError('Unfrozen supplemental registration')
            pins = frozen['source_sha256']
        for name, sha in pins.items():
            if digest(ROOT/name) != sha:raise ValueError('Frozen source changed: '+name)
    return plan


def verify_registration():
    try:
        registration = json.loads(MANIFEST.read_text())
    except (OSError, ValueError) as error:
        raise ValueError('GUI adapter registration unavailable') from error
    pins = registration.get('source_sha256', {})
    if (registration.get('version') != VERSION or registration.get('status') != 'frozen'
            or not isinstance(pins, dict) or not REQUIRED_PINS <= set(pins)):
        raise ValueError('GUI adapter is not completely frozen')
    for name, expected in pins.items():
        if digest(ROOT/name) != expected:raise ValueError('Registered GUI source changed: '+name)
    plan = candidate_preflight()
    replacements = registration.get('replacement_run_ids', [])
    if (registration.get('affected_cohort') != plan['affected_cohort'] or len(replacements) != 18
            or replacements != [row['run_id'] for row in plan['affected_cohort']]
            or len(set(replacements)) != 18 or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',x) for x in replacements)):
        raise ValueError('GUI registration must qualify the uniform full all18 replacement cohort')
    return registration


@contextmanager
def derivative_mount():
    """Only the shared /grader/scripts source root changes for both frozen fixtures."""
    original = software_fixtures.ROOT, w02_fixtures.ROOT
    cases = software_fixtures.CASE, w02_fixtures.CASE
    if original != (ROOT, ROOT):raise ValueError('Unexpected active fixture root override')
    software_fixtures.ROOT = w02_fixtures.ROOT = DERIVATIVE_ROOT
    try:
        yield
    finally:
        software_fixtures.ROOT, w02_fixtures.ROOT = original
        if (software_fixtures.CASE, w02_fixtures.CASE) != cases:
            raise ValueError('Frozen case constants changed during GUI grading')


def qualified_grade(run_id):
    registration = verify_registration()
    if run_id not in registration['replacement_run_ids']:
        raise ValueError('Run is outside registered all18 GUI replacement cohort')
    index = registration['replacement_run_ids'].index(run_id)
    expected = registration['affected_cohort'][index]
    metadata = json.loads((ROOT/'runtime'/run_id/'run.json').read_text())
    if any(metadata.get(key) != expected[field] for key, field in (('run_id','run_id'),('phase','phase'),('case_id','case'),('condition','condition'),('repeat','repeat'))):
        raise ValueError('Replacement run identity disagrees with registered cohort')
    audit_path = ROOT/'results'/run_id/'software-gui-transport-audit-v3.6.3.json'
    if audit_path.exists():raise ValueError('Preserve existing immutable GUI transport audit before grading')
    models = metadata.get('model_evidence', [])
    if not models or any(model != {'model':'gpt-6.1-sol','effort':'medium'} for model in models):
        raise ValueError('Unqualified actual actor model identity')
    # Existing native schema qualification remains responsible for controlled input.
    with derivative_mount():
        result = dialogue_schema.qualified_grade(run_id) if metadata.get('dialogue_protocol') else grade.grade(run_id)
    evidence = result.get('runtime_evidence', {})
    gui_commands = [check['command'] for check in evidence.get('checks', [])
                    if 'dbus-run-session' in check.get('command', [])]
    expected_mount = str(DERIVATIVE_ROOT/'scripts')+':/grader/scripts:ro'
    valid_mount = all([argv[i+1] for i, value in enumerate(argv[:-1])
                       if value=='-v' and argv[i+1].endswith(':/grader/scripts:ro')] == [expected_mount]
                      for argv in gui_commands) if gui_commands else None
    grade_path = ROOT/'results'/run_id/'grade.json'
    runtime_grade = ROOT/'runtime/software-grading'/run_id/'grade.json'
    proof = {'version':VERSION,'run_id':run_id,'case_id':metadata['case_id'],
             'condition':metadata['condition'],'repeat':metadata['repeat'],
             'agent_path':metadata.get('agent_path'),'native_session_id':metadata.get('session_id'),
             'actual_model_evidence':models,'wrapper_sha256':digest(Path(__file__)),
             'derivative_sha256':digest(ROOT/DERIVATIVE),'registration_sha256':digest(MANIFEST),
             'frozen_core_sha256':digest(ROOT/'results/frozen-core-v3.6.json'),
             'run_metadata_sha256':digest(ROOT/'runtime'/run_id/'run.json'),
             'expected_gui_mount':expected_mount,'actual_gui_docker_argv':gui_commands,
             'gui_executed':bool(gui_commands),'mount_matches_registered_derivative':valid_mount,
             'status':result.get('status'),'behavior_pass':result.get('behavior_pass'),
             'grade_artifact':{'path':str(grade_path),'sha256':digest(grade_path)},
             'runtime_grade_artifact':{'path':str(runtime_grade),'sha256':digest(runtime_grade)} if runtime_grade.is_file() else None,
             'control_audit_modified':False,'frozen_grader_result_modified':False}
    if valid_mount is False:proof['qualification_fault']='Actual GUI Docker mount differs from registered derivative'
    audit_path.parent.mkdir(parents=True,exist_ok=True)
    with audit_path.open('x') as stream:json.dump(proof,stream,ensure_ascii=False,indent=2)
    if valid_mount is False:raise ValueError(proof['qualification_fault'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser();parser.add_argument('run_id');args=parser.parse_args()
    print(json.dumps(qualified_grade(args.run_id),ensure_ascii=False))
