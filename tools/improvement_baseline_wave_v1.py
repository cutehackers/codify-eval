"""Prospective two-task baseline pilot wave, not candidate comparison or final power."""
import argparse,json,subprocess,time
from pathlib import Path
import improvement_baseline_q02_v2 as seed
from prepare import tree_hash
from improvement_qualify_v1 import digest_tree
prior=seed.prior
ROOT=prior.ROOT
FREEZE=ROOT/'results/improvement-v1/baseline-wave-freeze-v1.json'
REVIEW=ROOT/'results/improvement-v1/baseline-wave-runner-review-v1.json'
PHASE='control-probe-baseline-wave-v1'
CASES={'Q01':ROOT/'improvement_cases/confirmatory-v3/Q01','Q02':seed.CASE}
SEQUENCE=[{'case_id':c,'condition':'A','repeat':r,'run_id':f'{PHASE}-{c}-A-{r}',
           'outcome_review':f'results/improvement-v1/{PHASE}-{c}-A-{r}-outcome-review-v1.json'}
          for c,r in [('Q01',1),('Q02',2),('Q01',2)]]

def case_directory(case):
    if case not in CASES:raise ValueError('Only preregistered two baseline tasks')
    return CASES[case]

def freeze():
    if FREEZE.exists():raise ValueError('Pilot wave already frozen')
    previous=seed.configure()
    names=set(previous['source_hashes'])|{'tools/improvement_baseline_wave_v1.py',str(seed.FREEZE.relative_to(ROOT)),'results/improvement-v1/prospective-confirmation-sampling-design-v1.json'}
    reviews=[REVIEW,ROOT/'results/improvement-v1/Q01-v3-behavior-qualification-review-v1.json',ROOT/'results/improvement-v1/baseline-q02-A-1-outcome-review-v2.json']
    for path in reviews:
        reviewed=json.loads(path.read_bytes());assert reviewed['verdict']=='pass'
        for name,expected in reviewed['source_hashes'].items():
            assert prior.sha(ROOT/name)==expected,name
            names.add(name)
        names.add(str(path.relative_to(ROOT)))
    for case,version in [('Q01',5),('Q02',4)]:
        receipt_path=ROOT/f'results/improvement-v1/confirmation-qualification-v{version}/{case}/receipt.json'
        receipt=json.loads(receipt_path.read_bytes())
        assert receipt['status']=='behavior_qualified' and receipt['case_id']==case
        assert receipt['image_id']==previous['image_id'] and receipt['source_hashes']==digest_tree(CASES[case])
        names.add(str(receipt_path.relative_to(ROOT)))
        names.update(str(p.relative_to(ROOT)) for p in CASES[case].rglob('*') if p.is_file())
    value={k:v for k,v in previous.items() if k not in {'source_hashes','case_hashes','sequence'}}
    value.update(stage='baseline_only_two_task_wave',case_hashes={c:tree_hash(p) for c,p in CASES.items()},sequence=SEQUENCE,
                 source_hashes={name:prior.sha(ROOT/name) for name in sorted(names)},
                 prior_pilot_run=seed.RUN,independent_tasks_in_initial_wave=2,
                 primary_confirmation_reuse_allowed=False,final_N=None,
                 limits=['Initial wave yields two tasks with two attempts each, including retained first Q02. It cannot prove superiority or determine final power.','No question/delegation/GUI/device/production qualification.'])
    with FREEZE.open('x') as f:json.dump(value,f,indent=2)
    return value

def configure():
    prior.FREEZE=FREEZE;prior.PHASE=PHASE;prior.case_directory=case_directory;prior.quiesce=seed.quiesce
    return prior.check()

def launch(run_id):
    frozen=configure();next_row=None
    for row in frozen['sequence']:
        if not (ROOT/'results'/row['run_id']/'grade.json').exists():next_row=row;break
        review_path=ROOT/row['outcome_review']
        if not review_path.exists():raise ValueError('Previous outcome review required before next allocation')
        report=json.loads(review_path.read_bytes())
        assert report['run_id']==row['run_id'],'Review must bind original run'
    assert next_row and next_row['run_id']==run_id,'Follow frozen allocation order; do not restart original actors'
    assert not subprocess.check_output(['docker','ps','-q','--filter','name=codify-'],text=True,timeout=30).strip()
    intent=ROOT/'results/improvement-v1'/(run_id+'-launch-intent.json')
    seed.diagnostics.artifacts.atomic_json(intent,{'started_at':time.time(),'run_id':run_id,'actor_retries_allowed':0},exclusive=True)
    prior.prepare.case_directory=case_directory
    prepared=prior.prepare.prepare(next_row['case_id'],'A',next_row['repeat'],PHASE)
    path=ROOT/'runtime'/run_id/'run.json';metadata=json.loads(path.read_bytes())
    metadata.update(evaluation_core={'path':str(FREEZE),'sha256':prior.sha(FREEZE)},time_limit_seconds=1200,user_turn_limit=1)
    path.write_text(json.dumps(metadata,indent=2));prior.bind(run_id,frozen)
    prior.inspect_repo(ROOT/'runtime'/run_id/'repo')
    import dispatch
    return dispatch.dispatch(run_id)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['freeze','prepare','collect','grade']);parser.add_argument('run_id',nargs='?');parser.add_argument('agent_path',nargs='?');args=parser.parse_args()
    if args.operation=='freeze':
        result=freeze();print(json.dumps({'status':result['status'],'sequence':result['sequence'],'source_pin_count':len(result['source_hashes'])}))
    elif args.operation=='prepare':print(launch(args.run_id))
    else:
        configure();result=prior.collect_run(args.run_id,args.agent_path) if args.operation=='collect' else prior.grade_run(args.run_id)
        print(json.dumps({k:v for k,v in result.items() if k not in ['checks','final']}))
