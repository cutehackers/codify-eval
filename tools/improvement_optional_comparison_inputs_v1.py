"""Draft inputs for equal-permission voluntary orchestration development.

No allocation, freeze, native qualification or comparison is performed here.
A reviewed prospective driver must validate all case/skill/source pins first.
"""
from contextlib import contextmanager
from pathlib import Path
import random

import improvement_optional_runtime_v10 as runtime

ROOT = Path(__file__).resolve().parents[1]
CASES = ('O01', 'O02')
CONDITIONS = ('A', 'C0', 'C16')
SEED = 610613


def sequence():
    rows = [{'case_id': case, 'condition': condition, 'repeat': 1,
             'run_id': f'optional-development-v1-{case}-{condition}-1',
             'actor_path': f'/root/optional_development_v1_{case.lower()}_{condition.lower()}_1'}
            for case in CASES for condition in CONDITIONS]
    random.Random(SEED).shuffle(rows)
    return rows


def row_valid(row):
    runtime.require(runtime.encoded(row) in [runtime.encoded(r) for r in sequence()],
                    'Exact registered case, condition, repeat and actor name required')


def case_directory(row):
    row_valid(row)
    return ROOT / 'improvement_cases/fresh-optional-cohort-v1' / row['case_id']


def public_task(row):
    case = case_directory(row)
    protocol = ('Implement the supplied public task. Choose zero, one or two cumulative workers '
                'only when their contribution is useful. The same permissions and shared original '
                '1200-second deadline apply to every condition. No worker is required. '
                'Use only the registered broker. Write workers need disjoint editable scopes. '
                'A read-only review may use an empty scope. Wait for genuine worker completion, '
                'read every original view and explicitly accept or reject each contribution. '
                'Integrate once, then verify the final implementation. Preserve unsuccessful '
                'checks and report actual evidence. Do not ask to confirm decisions already '
                'specified by the public task.\n')
    if row['condition'] != 'A':
        protocol = ('$codify\nUse the supplied skill at '
                    '/work/repo/.agents/skills/codify/SKILL.md and its referenced resources. '
                    'Every allocated worker receives the same supplied skill. Begin each worker '
                    'goal with $codify and instruct it to read this skill inside its checkout.\n'
                    + protocol)
    return protocol + '\nPUBLIC TASK\n' + (case / 'public/request.md').read_text()


@contextmanager
def skill_export(row, folder):
    """Add a selected skill during runtime.create, inside its original clock.

    The initial root export precedes provision/Git baseline/registry snapshots.
    Subsequent worker exports preserve that complete protected starting tree.
    This process-local hook is restored on success and failure. It never stages
    a pre-clock working copy or modifies a qualified runtime source file.
    """
    case = case_directory(row)
    folder = Path(folder).resolve()
    original = runtime.source.export

    def exported(starting, inventory, destination, deadline):
        result = original(starting, inventory, destination, deadline)
        if (row['condition'] != 'A'
                and Path(starting).resolve() == (case / 'repo').resolve()
                and Path(destination).resolve() == folder / 'root/repo'):
            skill = ROOT / 'snapshots' / row['condition']
            target = Path(destination) / '.agents/skills/codify'
            target.parent.mkdir(parents=True, exist_ok=True)
            original(skill, runtime.source.inventory(skill, deadline), target, deadline)
        return result

    runtime.source.export = exported
    try:
        yield
    finally:
        runtime.source.export = original
