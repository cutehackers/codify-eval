"""Adaptive C6 development only; reuses frozen v2 execution primitives.

Historical A/C0/C1 attempts stay intact. Reused development cases and sequential
historical timings cannot establish confirmatory superiority.
"""
import argparse,json
from pathlib import Path
import improvement_run_v2 as prior
from prepare import tree_hash
ROOT=prior.ROOT
FREEZE=ROOT/'results/improvement-v1/C6-development-freeze-v1.json'
PHASE='control-probe-improvement-c6-v1'

def freeze():
    if FREEZE.exists():raise ValueError('Already frozen')
    base=prior.check()
    review_path=ROOT/'results/improvement-v1/C6-static-review-v1.json'
    review=json.loads(review_path.read_text());assert review['verdict']=='pass'
    for name,digest in review['source_hashes'].items():assert prior.sha(ROOT/name)==digest,name
    runner_review_path=ROOT/'results/improvement-v1/C6-runner-review-v1.json'
    runner_review=json.loads(runner_review_path.read_text());assert runner_review['verdict']=='pass'
    for name,digest in runner_review['source_hashes'].items():assert prior.sha(ROOT/name)==digest,name
    candidate=ROOT/'snapshots/C6';files={str(p.relative_to(candidate)):prior.sha(p) for p in candidate.rglob('*') if p.is_file()}
    pin_names=set(base['source_hashes'])|{str(prior.FREEZE.relative_to(ROOT)),str(review_path.relative_to(ROOT)),'tools/improvement_c6_run_v1.py','results/improvement-v1/C6-development-rationale-v1.json'}
    pin_names.add(str(runner_review_path.relative_to(ROOT)))
    pin_names.update(runner_review['source_hashes'])
    pin_names.update(str(p.relative_to(ROOT)) for p in candidate.rglob('*') if p.is_file())
    for row in base['sequence']:
        out=ROOT/'results'/row['run_id']
        for name in ['grade.json','usage.json','native-tools.jsonl','artifact-seal.json']:pin_names.add(str((out/name).relative_to(ROOT)))
    c3_freeze=ROOT/'results/improvement-v1/C3-development-freeze-v1.json'
    c3=json.loads(c3_freeze.read_text())
    for name,digest in c3['source_hashes'].items():assert prior.sha(ROOT/name)==digest,name
    pin_names.add(str(c3_freeze.relative_to(ROOT)))
    for row in c3['sequence']:
        out=ROOT/'results'/row['run_id']
        for name in ['grade.json','usage.json','native-tools.jsonl','artifact-seal.json']:pin_names.add(str((out/name).relative_to(ROOT)))
    c4_freeze=ROOT/'results/improvement-v1/C4-development-freeze-v1.json'
    c4=json.loads(c4_freeze.read_text())
    for name,digest in c4['source_hashes'].items():assert prior.sha(ROOT/name)==digest,name
    pin_names.add(str(c4_freeze.relative_to(ROOT)))
    pin_names.update(c4['source_hashes'])
    for row in c4['sequence']:
        out=ROOT/'results'/row['run_id']
        for name in ['grade.json','usage.json','native-tools.jsonl','artifact-seal.json']:pin_names.add(str((out/name).relative_to(ROOT)))
    for name in ['results/improvement-v1/C4-development-summary-v4.json',
                 'tools/improvement_c4_summary_v4.py',
                 'results/improvement-v1/C4-summary-helper-review-v4.json',
                 'results/improvement-v1/D01-C4-1-outcome-review-v1.json',
                 'results/improvement-v1/D02-C4-1-outcome-review-v1.json',
                 'results/improvement-v1/C5-design-review-v1.json']:
        pin_names.add(name)
    d={k:v for k,v in base.items() if k not in {'source_hashes','sequence','skill_hashes','conditions'}}
    d.update(stage='adaptive development only; reused cases; historical comparator attempts preserved',candidate='C6',conditions=['C6'],candidate_files=files,skill_hashes={'C6':tree_hash(candidate)},historical_comparators=base['sequence']+c3['sequence']+c4['sequence'],baseline_freeze_sha256=prior.sha(prior.FREEZE),superiority_proven=False,source_hashes={name:prior.sha(ROOT/name) for name in sorted(pin_names)},sequence=[{'case_id':c,'condition':'C6','repeat':1,'run_id':f'{PHASE}-{c}-C6-1'} for c in ['D01','D02']])
    with FREEZE.open('x') as f:json.dump(d,f,indent=2)
    return d

def configure():
    prior.FREEZE=FREEZE;prior.PHASE=PHASE
    return prior.check()

if __name__=='__main__':
    p=argparse.ArgumentParser();subs=p.add_subparsers(dest='action',required=True);subs.add_parser('freeze')
    a=subs.add_parser('prepare');a.add_argument('case')
    a=subs.add_parser('collect');a.add_argument('run');a.add_argument('agent_path')
    a=subs.add_parser('grade');a.add_argument('run');args=p.parse_args()
    if args.action=='freeze':result=freeze()
    else:
        configure()
        result=prior.launch(args.case,'C6') if args.action=='prepare' else prior.collect_run(args.run,args.agent_path) if args.action=='collect' else prior.grade_run(args.run)
    print(result if isinstance(result,str) else json.dumps(result,ensure_ascii=False))
