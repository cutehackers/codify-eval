"""Source-frozen A-only native qualification allocation, never a comparison.

Reuse the reviewed adaptive adapter in one isolated process. Qualification stays
false throughout these allocations. Successful controls require an independently
reviewed actual outcome before a later comparison freeze may assert it true.
"""
import argparse
import ast
import json
from pathlib import Path
import subprocess

import improvement_question_pilot_v5 as pilot
import improvement_question_watch_v6 as watch
import improvement_question_prepare_v2 as preparation
from improvement_software_artifacts_v3 import atomic_json

ROOT, legacy = pilot.ROOT, pilot.legacy
PHASE = 'control-probe-natural-question-runtime-v1'
FREEZE = ROOT / 'results/improvement-v1/fresh-natural-question-runtime-controls-freeze-v1.json'
REVIEW = ROOT / 'results/improvement-v1/fresh-natural-question-runtime-control-allocator-review-v1.json'
RUNTIME_REVIEW = ROOT / 'results/improvement-v1/fresh-natural-question-runtime-static-review-v6.json'
CLOSER_REVIEW = ROOT / 'results/improvement-v1/fresh-natural-question-failure-close-review-v3.json'
QUALITY_REVIEW = ROOT / 'results/improvement-v1/fresh-question-cohort-v2-qualification-outcome-review-v2.json'
CASES = ('Q05', 'Q06')


def closure():
    pending = [Path(__file__).resolve()]; found = set()
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_bytes())):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) else []
            for name in names:
                local = ROOT / 'tools' / ((name or '').split('.')[0] + '.py')
                if local.is_file() and local not in found:
                    pending.append(local)
    return found


def check_review(path, names):
    value = legacy.read(path)
    assert value['verdict'].lower() == 'pass' and not value['issues']
    for field in ('source_hashes', 'source_pins', 'evidence_hashes', 'source_closure_sha256'):
        pins = value.get(field, {})
        for name, entry in pins.items():
            expected = entry['sha256'] if isinstance(entry, dict) else entry
            assert legacy.sha(ROOT / name) == expected, name
            names.add(ROOT / name)
    names.add(path)
    return value


def freeze():
    assert not FREEZE.exists(), 'Immutable prospective control freeze already exists'
    names = closure() | {ROOT / 'AGENTS.md', ROOT / 'docs/improvement-spec-v1.md', ROOT / 'runtime/image.json'}
    for path in (REVIEW, RUNTIME_REVIEW, CLOSER_REVIEW, QUALITY_REVIEW):
        check_review(path, names)
    registration = pilot.old.collector.verify()
    names.add(pilot.old.collector.MANIFEST)
    for name, digest in registration.get('source_hashes', {}).items():
        assert legacy.sha(ROOT / name) == digest
        names.add(ROOT / name)
    sequence = [{'case_id': case, 'condition': 'A', 'repeat': 1,
                 'run_id': f'{PHASE}-{case}-A-1'} for case in CASES]
    assert all(not (ROOT / 'runtime' / row['run_id']).exists()
               and not (ROOT / 'results' / row['run_id']).exists() for row in sequence)
    value = {'status': 'frozen', 'stage': 'native_runtime_qualification_control',
             'allocation_mode': 'runtime_qualification_control',
             'adaptive_runtime_qualified': False, 'comparison_eligible': False,
             'primary_confirmation_reuse_allowed': False, 'superiority_proven': False,
             'model': 'gpt-6.1-sol', 'effort': 'medium', 'trajectory_seconds': 1200,
             'actor_cap': 1, 'concurrency': 1, 'retries': 0, 'conditions': ['A'],
             'sequence': sequence, 'image_id': legacy.read(ROOT / 'runtime/image.json')['image_id'],
             'case_hashes': {case: preparation.tree_hash(pilot.case_directory(case)) for case in CASES},
             'skill_hashes': {}, 'source_hashes': {str(path.relative_to(ROOT)): legacy.sha(path) for path in sorted(names)},
             'limits': ['A-only source-frozen native controls. No candidate superiority or comparative evidence.',
                        'Natural behavior may exercise only some reply branches. Unobserved branches remain unqualified.',
                        'Actual original-clock startup, observer, native transport, source modes, grading and cleanup require outcome review.',
                        'Original1200 deadline is retained, never shortened, paused or reset. No retry.',
                        'Any subsequent comparison must use a separate prospectively frozen allocation after independent qualification.']}
    atomic_json(FREEZE, value, exclusive=True)
    return value


def configure():
    legacy.prior.FREEZE, legacy.prior.PHASE = FREEZE, PHASE
    legacy.prior.case_directory = pilot.case_directory
    value = legacy.prior.check()
    assert value['allocation_mode'] == 'runtime_qualification_control'
    assert value['adaptive_runtime_qualified'] is False and value['comparison_eligible'] is False
    assert value['primary_confirmation_reuse_allowed'] is False and value['superiority_proven'] is False
    assert value['model'] == 'gpt-6.1-sol' and value['effort'] == 'medium'
    assert value['image_id'] == legacy.read(ROOT / 'runtime/image.json')['image_id']
    assert value['trajectory_seconds'] == 1200 and value['actor_cap'] == 1
    assert value['concurrency'] == 1 and value['retries'] == 0
    expected = [{'case_id': case, 'condition': 'A', 'repeat': 1, 'run_id': f'{PHASE}-{case}-A-1'} for case in CASES]
    assert value['conditions'] == ['A'] and value['sequence'] == expected and value['skill_hashes'] == {}
    return value


def install():
    # Sequential process-local adaptation only. Frozen comparison source stays intact.
    pilot.FREEZE, pilot.PHASE, pilot.configure = FREEZE, PHASE, configure
    pilot.preparation = preparation
    pilot.failure_close.PHASE = PHASE
    watch.pilot = pilot


def launch(run):
    install(); configure()
    result = pilot.launch(run)
    folder, out = ROOT / 'runtime' / run, ROOT / 'results' / run
    metadata = legacy.read(folder / 'run.json')
    metadata.update(allocation_mode='runtime_qualification_control', comparison_eligible=False,
                    adaptive_runtime_qualified=False, primary_confirmation_reuse_allowed=False)
    atomic_json(folder / 'run.json', metadata)
    atomic_json(out / 'runtime-control-allocation.json', {'run_id': run, 'comparison_eligible': False,
               'adaptive_runtime_qualified': False, 'allocation_mode': 'runtime_qualification_control',
               'freeze_sha256': legacy.sha(FREEZE)}, exclusive=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('freeze', 'prepare', 'bind', 'first', 'decide', 'stage', 'collect', 'grade', 'abort', 'watch', 'authorize-close', 'close'))
    parser.add_argument('run', nargs='?'); parser.add_argument('extra', nargs='?')
    args = parser.parse_args()
    if args.action == 'freeze':
        result = freeze()
    else:
        install()
        if args.action == 'prepare': result = launch(args.run)
        elif args.action == 'watch': result = watch.supervise(args.run, args.extra)
        elif args.action == 'authorize-close': result = pilot.failure_close.authorize_close(args.run, args.extra)
        elif args.action == 'close': result = pilot.failure_close.close(args.run, RuntimeError(args.extra or 'original runtime control failure'))
        elif args.action in ('stage', 'grade'): result = getattr(pilot, args.action)(args.run)
        else: result = getattr(pilot, args.action)(args.run, args.extra)
    print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
