"""Scope fixture equivalence and one-shot lifecycle guard qualification."""
import contextlib
import fnmatch
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import software_scope_schema_v365 as scope


def run():
    checks = []
    def check(name, value):
        checks.append({'name': name, 'pass': bool(value)})
        if not value:
            raise AssertionError(name)
    def rejects(name, operation):
        try:
            operation()
        except (ValueError, OSError):
            check(name, True)
        else:
            check(name, False)
    root = scope.ROOT
    case_hash = scope.validate_case()
    check('Only declared metadata/public documentation changes', bool(case_hash))
    old = json.loads((root / 'software_cases/W02/metadata.json').read_text())
    new = json.loads((root / 'software_cases/W02v365/metadata.json').read_text())
    allowed = lambda name: any(fnmatch.fnmatch(name, p) for p in new['allowed_paths'])
    for name in ['IMPLEMENTATION.md', 'README.md', 'docs/implementation.md', 'lib/todo.dart',
                 'test/archive_test.dart', 'integration_test/user_flow_test.dart']:
        check('Publicly allowed path: ' + name, allowed(name))
    for name in ['AGENTS.md', 'UNRELATED.md', 'tools/script.py', 'secrets.json', 'new_feature.txt']:
        check('Undisclosed/unrelated root path rejected: ' + name, not allowed(name))
    check('Protected regression/banner criteria unchanged', new['protected_paths'] == old['protected_paths'])
    check('Policy input/storage/runtime/required checks unchanged', all(new[k] == v for k, v in old.items()
          if k not in {'id', 'allowed_paths'}))
    plan = json.loads(scope.PLAN.read_text())
    check('All A/B/C0 by three replacements', len(plan['replacement_runs']) == 9 and
          {(x['condition'], x['repeat']) for x in plan['replacement_runs']}
          == {(c, n) for c in ('A', 'B', 'C0') for n in (1, 2, 3)})
    selected = json.loads(scope.SCHEDULE.read_text())['runs']
    original = json.loads((root / 'results/schedule-C0.json').read_text())['runs']
    mapping = {x['original_run_id']: x['replacement_run_id'] for x in plan['mapping']}
    check('186 members; only declared nine replacements', len(selected) == 186 and
          all(b == a if a['run_id'] not in mapping else
              b == {**a, 'case': scope.CASE, 'run_id': mapping[a['run_id']]}
              for a, b in zip(original, selected)))
    row = plan['replacement_runs'][0]
    registration = {'runs': plan['replacement_runs'], 'case_hash': case_hash}
    rejects('Foreign cohort member rejected', lambda: scope.member(registration, 'foreign'))
    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        manifest = temp / 'manifest.json'; manifest.write_text('{}')
        core = temp / 'core.json'; core.write_text('{}')
        source_grade = temp / 'results' / row['run_id'] / 'grade.json'
        metadata_path = temp / 'runtime' / row['run_id'] / 'run.json'
        metadata_path.parent.mkdir(parents=True)
        source_grade.parent.mkdir(parents=True)
        digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).is_file() else 'unneeded-proof-source'
        metadata = {'run_id': row['run_id'], 'case_id': row['case'], 'condition': row['condition'],
                    'repeat': row['repeat'], 'phase': row['phase'], 'case_hash': case_hash,
                    'model_evidence': [{'model': 'gpt-6.1-sol', 'effort': 'medium'}],
                    'scope_revision': {'version': scope.VERSION, 'registration': str(manifest),
                                       'registration_sha256': digest(manifest), 'selected_core_sha256': digest(core)}}
        def save(value):
            metadata_path.write_text(json.dumps(value))
        mount = str(scope.gui.DERIVATIVE_ROOT / 'scripts') + ':/grader/scripts:ro'
        def fake_grade(run_id):
            value = {'status': 'review_pending', 'behavior_pass': True, 'scope_pass': True,
                     'runtime_evidence': {'checks': [{'command': ['docker', 'run', '-v', mount,
                                                                  'image', 'dbus-run-session']}]}}
            source_grade.write_text(json.dumps(value))
            return value
        with patch.object(scope, 'ROOT', temp), patch.object(scope, 'MANIFEST', manifest),\
             patch.object(scope, 'CORE', core), patch.object(scope, 'sha', digest),\
             patch.object(scope, 'verify_registration', return_value=registration),\
             patch.object(scope.gui, 'derivative_mount', side_effect=contextlib.nullcontext),\
             patch.object(scope.dialogue_schema, 'qualified_grade', side_effect=fake_grade):
            for key, value in [('case_id', 'W02'), ('case_hash', 'changed'), ('condition', 'foreign'),
                               ('phase', 'heldout'), ('model_evidence', []),
                               ('model_evidence', [{'model': 'gpt-6-sol', 'effort': 'medium'}]),
                               ('scope_revision', {})]:
                save({**metadata, key: value})
                rejects('Grade guard: ' + key + ':' + str(value), lambda: scope.qualified_grade(row['run_id']))
            save(metadata)
            result = scope.qualified_grade(row['run_id'])
            audit = json.loads((source_grade.parent / 'software-gui-transport-audit-v3.6.5.json').read_text())
            check('Exact registered GUI mount required and recorded', audit['mount_matches_registered_derivative'] is True)
            check('Pre-report grade hash preserved', audit['grade_artifact']['sha256'] == digest(source_grade))
            check('No result or controlled audit mutation', result['scope_pass'] is True and audit['control_audit_modified'] is False)
            rejects('Existing grade/audit cannot be overwritten', lambda: scope.qualified_grade(row['run_id']))
            rejects('Existing actor preparation cannot be retried', lambda: scope.qualified_prepare(row['condition'], row['repeat']))
    return {'version': scope.VERSION, 'verdict': 'pass', 'checks': checks,
            'case_hash': case_hash, 'wrapper_sha256': scope.sha(Path(scope.__file__)),
            'probe_source_sha256': scope.sha(Path(__file__)),
            'actions': 'Static fixture/allowlist checks and isolated mocked lifecycle. No actor or app execution.'}


if __name__ == '__main__':
    output = scope.ROOT / 'results/software-W02-scope-qualification-v3.6.5.json'
    if output.exists():
        raise ValueError('Preserve existing qualification before another attempt')
    result = run()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'verdict': result['verdict'], 'checks': len(result['checks'])}))
