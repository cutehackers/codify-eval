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
coverage = {'INPUT': ['test_validate_all_before_effects'], 'STATE': ['test_shortage_is_atomic_and_sorted', 'test_conflicting_retry_preserves_state'], 'NORMALIZE': ['test_aggregate_and_sort_success', 'test_repeated_sku_shortage_uses_total'], 'SUCCESS': ['test_aggregate_and_sort_success', 'test_return_value_does_not_alias_saved_receipt'], 'RETRY': ['test_normalized_retry_no_double_debit', 'test_conflicting_retry_preserves_state'], 'SHORTAGE': ['test_shortage_is_atomic_and_sorted', 'test_repeated_sku_shortage_uses_total', 'test_shortage_not_saved_retry_after_replenishment']}
result = {'case':CASE, 'qualification_status':'qualified', 'editable_paths':['reservation.py'], 'expected_private_tests':expected, 'expected_public_tests':1, 'coverage':coverage, 'runs':runs, 'limitations':['No evaluated model runs or candidate-skill material were used.', 'Injected dependencies and in-memory state are evaluated, not production infrastructure.']}
(ROOT / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
print(CASE + ': reference private 8/8 and public 1/1 pass; stub and ' + str(len(targets)-2) + ' faults fail as expected')
