"""Source-frozen A-only native qualification allocation, never a comparison.

Reuse the reviewed adaptive adapter in one isolated process. Qualification stays
false throughout these allocations. Successful controls require an independently
reviewed actual outcome before a later comparison freeze may assert it true.
"""
import argparse
import ast
import json
from pathlib import Path
import stat

import improvement_question_pilot_v5 as pilot
import improvement_question_watch_v9 as watch
import improvement_question_deadline_close_v1 as deadline_close
import improvement_question_prepare_v5 as preparation
import improvement_product_observation_v2 as product_observation
import improvement_question_lifecycle_v1 as strict_lifecycle
from improvement_software_artifacts_v3 import atomic_json

ROOT, legacy = pilot.ROOT, pilot.legacy
PHASE = 'control-probe-natural-question-runtime-v4'
FREEZE = ROOT / 'results/improvement-v1/fresh-natural-question-runtime-controls-freeze-v9.json'
REVIEW = ROOT / 'results/improvement-v1/fresh-natural-question-runtime-control-allocator-review-v9.json'
RUNTIME_REVIEW = ROOT / 'results/improvement-v1/fresh-natural-question-observer-deadline-review-v9.json'
CLOSER_REVIEW = ROOT / 'results/improvement-v1/fresh-natural-question-failure-close-review-v3.json'
FREEZE_REVIEW = ROOT / 'results/improvement-v1/fresh-natural-question-runtime-control-freeze-review-v9.json'
LIFECYCLE_REVIEW = ROOT / 'results/improvement-v1/fresh-natural-question-lifecycle-prelaunch-review-v1.json'
CLASSIFIER_REVIEW = ROOT / 'results/improvement-v1/fresh-question-product-observation-review-v2.json'
QUALITY_REVIEW = ROOT / 'results/improvement-v1/fresh-question-cohort-v2-qualification-outcome-review-v2.json'
DEADLINE_REVIEW = ROOT / 'results/improvement-v1/fresh-natural-question-deadline-close-v1-review-v1.json'
CASES = ('Q05', 'Q06')
ORIGINAL_NEXT = legacy.next_allocation
ORIGINAL_STAGE = pilot.stage


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




def source_key(path):
    path = Path(path)
    assert path.is_absolute()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)

def entity(path):
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode), 'Source must be a regular file: ' + str(path)
    return {'kind': 'file', 'mode': stat.S_IMODE(info.st_mode), 'bytes': info.st_size, 'sha256': legacy.sha(path)}


def case_entities(case):
    base = pilot.case_directory(case)
    result = {}
    for path in [base] + sorted(base.rglob('*')):
        relative = path.relative_to(base)
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            result[relative.as_posix()] = {'kind': 'directory', 'mode': stat.S_IMODE(info.st_mode)}
        else:
            result[relative.as_posix()] = entity(path)
    return result

def check_review(path, names, required=()):
    value = legacy.read(path)
    assert value['verdict'].lower() == 'pass' and not value['issues']
    verified = set()
    for field in ('source_hashes', 'source_pins', 'evidence_hashes', 'source_closure_sha256'):
        pins = value.get(field, {})
        for name, entry in pins.items():
            if isinstance(entry, dict) and 'kind' in entry:
                assert entry['kind']=='file', 'Supplied compatibility pin kind must be file: ' + name
            expected = entry['sha256'] if isinstance(entry, dict) else entry
            assert legacy.sha(ROOT / name) == expected, name
            info = (ROOT / name).lstat()
            assert stat.S_ISREG(info.st_mode), name
            if isinstance(entry, dict) and 'mode' in entry:
                expected_mode = int(entry['mode'], 8) if isinstance(entry['mode'], str) else entry['mode']
                assert type(expected_mode) is int and stat.S_IMODE(info.st_mode) == expected_mode, name
            if isinstance(entry, dict) and 'bytes' in entry:
                assert type(entry['bytes']) is int and info.st_size==entry['bytes'], name
            verified.add(ROOT / name)
            names.add(ROOT / name)
    for name, expected in value.get('source_entities', {}).items():
        source = ROOT / name
        assert isinstance(expected, dict) and set(expected) in ({'kind','mode','sha256'}, {'kind','mode','bytes','sha256'}), 'Exact review entity required'
        assert expected['kind']=='file' and type(expected['mode']) is int and ('bytes' not in expected or type(expected['bytes']) is int), 'Typed review entity required'
        actual=entity(source)
        assert json.dumps({k:actual[k] for k in expected},sort_keys=True)==json.dumps(expected,sort_keys=True), 'Review source entity changed: ' + name
        verified.add(source); names.add(source)
    for entry in value.get('typed_full_ast_sourceclosure_pins', []):
        source = Path(entry['path'])
        assert entry['kind'] == 'regular_file' and source.is_file() and not source.is_symlink()
        assert type(entry['bytes']) is int and source.stat().st_size == entry['bytes']
        assert type(entry['mode']) is int and stat.S_IMODE(source.stat().st_mode) == entry['mode']
        assert legacy.sha(source) == entry['sha256']
        verified.add(source); names.add(source)
    assert verified, 'Passing review requires nonempty verified source/evidence pins' 
    assert set(required) <= verified, 'Review missing required current source closure coverage'
    names.add(path)
    return value


def freeze():
    assert not FREEZE.exists(), 'Immutable prospective control freeze already exists'
    names = closure() | {ROOT / 'AGENTS.md', ROOT / 'docs/improvement-spec-v1.md', ROOT / 'runtime/image.json'}
    for path in (REVIEW, FREEZE_REVIEW, RUNTIME_REVIEW, CLOSER_REVIEW, DEADLINE_REVIEW, QUALITY_REVIEW, CLASSIFIER_REVIEW, LIFECYCLE_REVIEW):
        check_review(path, names, closure() if path == REVIEW else (Path(__file__).resolve(), ROOT / 'tools/improvement_question_prepare_v5.py') if path == FREEZE_REVIEW else (ROOT / 'tools/improvement_question_lifecycle_v1.py',) if path == LIFECYCLE_REVIEW else ())
    assert legacy.read(QUALITY_REVIEW)['qualification_pass'] is True
    assert legacy.read(QUALITY_REVIEW)['all_owned_controls_removed'] is True
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
             'runtime_control_scenarios': {'Q05': 'normal', 'Q06': 'normal'},
             'cleanup_observation_seconds': 180,
             'sequence': sequence, 'image_id': legacy.read(ROOT / 'runtime/image.json')['image_id'],
             'case_hashes': {case: preparation.tree_hash(pilot.case_directory(case)) for case in CASES},
             'skill_hashes': {}, 'case_entities': {case: case_entities(case) for case in CASES},
             'source_entities': {source_key(path): entity(path) for path in sorted(names)},
             'source_hashes': {source_key(path): legacy.sha(path) for path in sorted(names)},
             'limits': ['A-only source-frozen native controls. No candidate superiority or comparative evidence.',
                        'Public-task normal controls with conditional approved reply on the original clock. No candidate advantage is inferred.',
                        'Prospective fourth control series retains all prior evidence; no candidate confirmation or actor retry.',
                        'Coordinator must prepare, start observer and spawn without yielding a turn; first observation must remain within30s.',
                        'Actual original-clock startup, observer, native transport, source modes, grading and cleanup require outcome review.',
                        'Original1200 deadline is retained, never shortened, paused or reset. No retry.',
                        'Any subsequent comparison must use a separate prospectively frozen allocation after independent qualification.']}
    atomic_json(FREEZE, value, exclusive=True)
    return value


def configure():
    legacy.prior.FREEZE, legacy.prior.PHASE = FREEZE, PHASE
    legacy.prior.case_directory = pilot.case_directory
    value = legacy.prior.check()
    assert value['source_entities'] and set(value['source_entities']) == set(value['source_hashes'])
    for name, expected in value['source_entities'].items():
        assert json.dumps(entity(ROOT / name), sort_keys=True) == json.dumps(expected, sort_keys=True), name
    assert json.dumps({case: case_entities(case) for case in CASES}, sort_keys=True) == json.dumps(value['case_entities'], sort_keys=True)
    assert value['allocation_mode'] == 'runtime_qualification_control'
    assert value['adaptive_runtime_qualified'] is False and value['comparison_eligible'] is False
    assert value['primary_confirmation_reuse_allowed'] is False and value['superiority_proven'] is False
    assert value['model'] == 'gpt-6.1-sol' and value['effort'] == 'medium'
    assert value['image_id'] == legacy.read(ROOT / 'runtime/image.json')['image_id']
    assert type(value['trajectory_seconds']) is int and value['trajectory_seconds'] == 1200
    assert type(value['actor_cap']) is int and value['actor_cap'] == 1
    assert type(value['concurrency']) is int and value['concurrency'] == 1
    assert type(value['retries']) is int and value['retries'] == 0
    expected = [{'case_id': case, 'condition': 'A', 'repeat': 1, 'run_id': f'{PHASE}-{case}-A-1'} for case in CASES]
    assert value['runtime_control_scenarios'] == {'Q05': 'normal', 'Q06': 'normal'}
    assert type(value['cleanup_observation_seconds']) is int and value['cleanup_observation_seconds'] == 180
    assert value['conditions'] == ['A'] and json.dumps(value['sequence'],sort_keys=True)==json.dumps(expected,sort_keys=True) and value['skill_hashes'] == {}
    return value


def guarded_stage(run):
    deadline_close.require_delivery_open(run)
    return ORIGINAL_STAGE(run)


def next_allocation(value):
    for row in value['sequence']:
        run = row['run_id']; out = ROOT / 'results' / run
        path = out / 'grade.json'
        if not path.exists():
            return row
        outcome = legacy.read(path)
        if outcome.get('deadline_aborted') is True:
            metadata = legacy.read(ROOT / 'runtime' / run / 'run.json')
            deadline_close.verify_closed(out, metadata)
        else:
            # Keep the original normal/failure raw, usage, ownership and grader
            # checks. Only this version's new deadline receipt has a new consumer.
            try:
                ORIGINAL_NEXT(dict(value, sequence=[row]))
            except ValueError as error:
                assert str(error) == 'All preregistered allocations already terminal'
            else:
                raise AssertionError('Prior normal allocation unexpectedly open')
    raise ValueError('All preregistered allocations already terminal')


def install():
    # Sequential process-local adaptation only. Frozen comparison source stays intact.
    # All reused core functions resolve this stricter lifecycle in this process.
    pilot.core.lifecycle=strict_lifecycle.lifecycle
    pilot.core.turn_id=strict_lifecycle.turn_id
    pilot.FREEZE, pilot.PHASE, pilot.configure = FREEZE, PHASE, configure
    pilot.preparation = preparation
    pilot.product_observation = product_observation
    pilot.failure_close.PHASE = PHASE
    watch.pilot = pilot
    deadline_close.PHASE = PHASE
    legacy.next_allocation = next_allocation
    pilot.stage = guarded_stage


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
    parser.add_argument('action', choices=('freeze', 'prepare', 'bind', 'first', 'decide', 'stage', 'collect', 'grade', 'abort', 'watch', 'authorize-close', 'close', 'commit-deadline', 'authorize-deadline'))
    parser.add_argument('run', nargs='?'); parser.add_argument('extra', nargs='?')
    args = parser.parse_args()
    if args.action == 'freeze':
        result = freeze()
    else:
        install()
        if args.action == 'prepare': result = launch(args.run)
        elif args.action == 'watch': result = watch.supervise(args.run, args.extra)
        elif args.action == 'commit-deadline': result = deadline_close.commit(args.run, args.extra)
        elif args.action == 'authorize-deadline': result = deadline_close.authorize(args.run, args.extra)
        elif args.action == 'abort': result = deadline_close.close(args.run, args.extra)
        elif args.action == 'authorize-close': result = pilot.failure_close.authorize_close(args.run, args.extra)
        elif args.action == 'close': result = pilot.failure_close.close(args.run, RuntimeError(args.extra or 'original runtime control failure'))
        elif args.action in ('stage', 'grade'): result = getattr(pilot, args.action)(args.run)
        else: result = getattr(pilot, args.action)(args.run, args.extra)
    print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
