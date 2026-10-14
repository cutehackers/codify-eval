"""Local deterministic qualification only. Never expose this directory to an evaluated agent."""
from pathlib import Path
import json
import os
import subprocess
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT.name
runs = []
targets = [('stub', ROOT / 'public'), ('reference', ROOT / 'private/reference')]
targets += [('fault:' + path.name, path) for path in sorted((ROOT / 'private/faults').iterdir())]
for name, target in targets:
    suites = [('private', ROOT / 'private/tests', 'test_*.py')]
    if name in ('stub', 'reference'):
        suites.append(('public', ROOT / 'public', 'test_smoke.py'))
    for suite, tests, pattern in suites:
        command = ['python3', '-B', '-m', 'unittest', 'discover', '-s', str(tests), '-p', pattern, '-v']
        env = dict(os.environ, PYTHONPATH=str(target), PYTHONDONTWRITEBYTECODE='1')
        # unittest discovery inserts public into sys.path, so run smoke against a
        # temporary directory containing only smoke tests, retaining target import.
        import tempfile
        import shutil
        with tempfile.TemporaryDirectory(prefix='representative-qualification-') as temp:
            if suite == 'public':
                shutil.copy2(tests / 'test_smoke.py', Path(temp) / 'test_smoke.py')
                command[6] = temp
            process = subprocess.run(command, cwd=temp, env=env, text=True, capture_output=True)
            match = re.search(r'Ran (\d+) test', process.stderr)
            runs.append({'target':name, 'suite':suite, 'command': 'PYTHONPATH=' + str(target) + ' ' + ' '.join(command), 'exit_code':process.returncode, 'tests_run':int(match.group(1)) if match else 0, 'stdout':process.stdout, 'stderr':process.stderr, 'public_discovery_note':'Smoke file copied alone to isolated temporary directory to prevent public stub shadowing selected target.' if suite=='public' else None})
expected = 8
assert all(r['tests_run'] == (expected if r['suite']=='private' else 1) for r in runs)
assert all(r['exit_code'] == (0 if r['target']=='reference' else 1) for r in runs)
coverage = {'INPUT': ['test_invalid_inputs_before_any_effect'], 'AUTH': ['test_permission_is_strict_and_before_read'], 'READ': ['test_missing_document', 'test_invalid_repository_document'], 'OUTPUT': ['test_success_preserves_valid_bytes_and_order', 'test_invalid_injected_output_never_persists', 'test_renderer_cannot_mutate_authoritative_document'], 'EFFECTS': ['test_success_preserves_valid_bytes_and_order', 'test_invalid_inputs_before_any_effect', 'test_dependency_errors_are_safe_and_unaudited'], 'ERRORS': ['test_dependency_errors_are_safe_and_unaudited']}
result = {'case':CASE, 'qualification_status':'qualified', 'editable_paths':['document_export.py'], 'expected_private_tests':expected, 'expected_public_tests':1, 'coverage':coverage, 'runs':runs, 'limitations':['No evaluated model runs or candidate-skill material were used.', 'Injected dependencies and in-memory state are evaluated, not production infrastructure.']}
(ROOT / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
print(CASE + ': reference private 8/8 and public 1/1 pass; stub and ' + str(len(targets)-2) + ' faults fail as expected')
