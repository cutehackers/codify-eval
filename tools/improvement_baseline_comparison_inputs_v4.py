"""Prospective exploratory pilot inputs. No live allocation/admission authority.

The four domain clusters are development evidence, never an untouched final
sample. A separately reviewed driver must freeze this source and all fixtures,
candidate trees and lifecycle controls before allocation.
"""
from pathlib import Path
import random

import improvement_baseline_case_catalog_v1 as catalog

ROOT = Path(__file__).resolve().parents[1]
CASES = ('B01', 'B02', 'B03', 'B04')
CONDITIONS = ('A', 'C0', 'C23')
WORKER_CAPS = (0, 2)
SEED = 610623
require = catalog.require


def sequence():
    rows = []
    for cap in WORKER_CAPS:
        cohort = 'solo' if cap == 0 else 'voluntary'
        for case in CASES:
            for condition in CONDITIONS:
                rows.append({'case_id': case, 'condition': condition,
                             'worker_cap': cap, 'cohort': cohort, 'repeat': 1,
                             'run_id': f'baseline-development-v4-{cohort}-{case}-{condition}-1',
                             'actor_path': f'/root/baseline_development_v4_{cohort}_{case.lower()}_{condition.lower()}_1'})
    random.Random(SEED).shuffle(rows)
    return rows


def row_valid(row):
    require(type(row) is dict, 'Exact registered pilot row required')
    require(catalog.encoded(row) in [catalog.encoded(r) for r in sequence()],
            'Exact typed pilot case/condition/cohort/cap/repeat/namespace required')


def public_contract(row):
    row_valid(row)
    return catalog.declared_execution(row['case_id'], row['condition'], row['worker_cap'])


def case_directory(row):
    row_valid(row)
    return catalog.materializer.COHORT / row['case_id']


def public_task(row):
    contract = public_contract(row)
    public = catalog.materializer.canonical(ROOT / contract['public_root'])
    task = public / 'README.md'
    require('README.md' in contract['public_inventory'], 'Qualified public task required')
    catalog.historical.control.reviewed_entity(task, contract['public_inventory']['README.md'])
    text = task.read_text(encoding='utf-8')
    catalog.historical.control.reviewed_entity(task, contract['public_inventory']['README.md'])
    protocol = ('Implement the supplied public task. Use only the registered broker. '
                'Preserve unsuccessful checks and report actual evidence. The original '
                'shared 1200-second deadline includes preparation, every actor, questions, '
                'verification and cleanup. Ask only when a material decision is absent '
                'from the public contract. Stop at that question and wait for an '
                'explicitly authorized owner reply before implementing that decision. '
                'Do not infer an owner decision or request confirmation of an already '
                'specified decision.\n')
    if row['worker_cap'] == 0:
        protocol += ('This is the solo cohort. No worker allocation or delegation is '
                     'permitted. Integrate once and verify the final implementation.\n')
    else:
        protocol += ('This is the voluntary cohort. Choose zero, one or two cumulative '
                     'workers only when useful. Failed allocations also consume their '
                     'reserved slots. Write workers need disjoint editable scopes. '
                     'A read-only review may use an empty scope. Wait for genuine '
                     'completion, read every original contribution and explicitly '
                     'accept or reject it. Integrate once and verify the final result.\n')
    if row['condition'] != 'A':
        protocol = ('$codify\nUse the supplied skill at '
                    '/work/repo/.agents/skills/codify/SKILL.md and its referenced '
                    'resources. Every allocated worker receives that same skill. '
                    'Begin each worker goal with $codify and instruct it to read '
                    'the skill inside its checkout.\n' + protocol)
    return protocol + '\nPUBLIC TASK\n' + text
