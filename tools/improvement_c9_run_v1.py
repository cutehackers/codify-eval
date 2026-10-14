"""Uninstalled C9 development on reused D cases, never confirmatory proof."""
import argparse
import json

import improvement_run_v2 as prior
from prepare import tree_hash

ROOT = prior.ROOT
FREEZE = ROOT / 'results/improvement-v1/C9-development-freeze-v1.json'
PHASE = 'control-probe-improvement-c9-v1'

def freeze():
    if FREEZE.exists():
        raise ValueError('Already frozen')
    # Verify the unchanged original execution/grading prerequisites first.
    prior.check()
    previous_path = ROOT / 'results/improvement-v1/C8-development-freeze-v1.json'
    previous = json.loads(previous_path.read_text())
    assert previous['candidate'] == 'C8' and previous['status'] == 'frozen'
    for name, digest in previous['source_hashes'].items():
        assert prior.sha(ROOT / name) == digest, name
    reviews = ['results/improvement-v1/C9-static-review-v1.json',
               'results/improvement-v1/C9-runner-review-v1.json']
    pins = set(previous['source_hashes']) | {
        str(previous_path.relative_to(ROOT)), 'tools/improvement_c9_run_v1.py',
        'results/improvement-v1/C9-development-rationale-v1.json',
        'results/improvement-v1/C7-static-review-v1.json',
        'results/improvement-v1/C8-summary-helper-review-v1.json',
        'results/improvement-v1/C8-development-summary-v1.json'}
    for name in reviews:
        review = json.loads((ROOT / name).read_text())
        assert review['verdict'] in ('pass', 'PASS'), name
        for source, digest in review['source_hashes'].items():
            assert prior.sha(ROOT / source) == digest, source
        pins.add(name)
        pins.update(review['source_hashes'])
    candidate = ROOT / 'snapshots/C9'
    files = {str(p.relative_to(candidate)): prior.sha(p)
             for p in candidate.rglob('*') if p.is_file()}
    pins.update(str(p.relative_to(ROOT)) for p in candidate.rglob('*') if p.is_file())
    for row in previous['sequence']:
        for name in ('grade.json', 'usage.json', 'native-tools.jsonl', 'artifact-seal.json'):
            pins.add('results/' + row['run_id'] + '/' + name)
    value = {k: v for k, v in previous.items() if k not in {
        'source_hashes', 'sequence', 'skill_hashes', 'conditions',
        'candidate', 'candidate_files', 'historical_comparators'}}
    value.update(stage='adaptive development only; reused cases and historical comparisons',
        candidate='C9', conditions=['C9'], candidate_files=files,
        skill_hashes={'C9': tree_hash(candidate)}, installed=False, superiority_proven=False,
        historical_comparators=previous['historical_comparators'] + previous['sequence'],
        source_hashes={name: prior.sha(ROOT / name) for name in sorted(pins)},
        sequence=[{'case_id': case, 'condition': 'C9', 'repeat': 1,
                   'run_id': PHASE + '-' + case + '-C9-1'} for case in ('D01', 'D02')])
    with FREEZE.open('x') as stream:
        json.dump(value, stream, indent=2)
    return value

def configure():
    prior.FREEZE = FREEZE
    prior.PHASE = PHASE
    return prior.check()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('freeze')
    for operation in ('prepare', 'collect', 'grade'):
        command = sub.add_parser(operation)
        command.add_argument('target')
        if operation == 'collect':
            command.add_argument('agent_path')
    args = parser.parse_args()
    if args.action == 'freeze':
        result = freeze()
    else:
        configure()
        result = (prior.launch(args.target, 'C9') if args.action == 'prepare' else
                  prior.collect_run(args.target, args.agent_path) if args.action == 'collect' else
                  prior.grade_run(args.target))
    print(result if isinstance(result, str) else json.dumps(result, ensure_ascii=False))
