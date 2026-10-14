"""Frozen C9 exploratory pilot on P01. Not a confirmatory superiority comparison."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid
import improvement_run_v2 as prior
import improvement_software_broker_v7 as diagnostics
from prepare import tree_hash
from improvement_qualify_v1 import digest_tree

ROOT=prior.ROOT
FREEZE=ROOT/'results/improvement-v1/candidate-C9-P01-freeze-v1.json'
PHASE='control-probe-candidate-C9-P01-v1'
REVIEW=ROOT/'results/improvement-v1/candidate-C9-P01-runner-review-v1.json'
CASE=ROOT/'improvement_cases/pilot-expansion-v3/P01'
RUN=PHASE+'-P01-C9-1'

class EvidencePending(prior.ActorNotTerminal):
    """Same terminal actor/container retained because diagnostics are not preserved."""

def case_directory(case):
    if case!='P01':raise ValueError('This pilot owns only P01')
    return CASE

def freeze():
    if FREEZE.exists():raise ValueError('Original pilot is already frozen')
    old=prior.check()
    baseline_review=ROOT/'results/improvement-v1/baseline-P01-A-1-outcome-review-v1.json'
    observed=json.loads(baseline_review.read_bytes());assert observed['verdict']=='pass' and observed['report_pass']
    skill=ROOT/'snapshots/C9'
    assert skill.is_dir()
    candidate_provenance=ROOT/'results/improvement-v1/C9-development-freeze-v1.json'
    assert tree_hash(skill)==json.loads(candidate_provenance.read_bytes())['skill_hashes']['C9']
    review=json.loads(REVIEW.read_bytes());assert review['verdict']=='pass'
    receipt_path=ROOT/'results/improvement-v1/pilot-qualification-v3/P01/receipt.json'
    receipt=json.loads(receipt_path.read_bytes())
    assert receipt['status']=='behavior_qualified' and receipt['case_id']=='P01'
    assert receipt['image_id']==old['image_id'] and receipt['source_hashes']==digest_tree(CASE)
    qualification=ROOT/'results/improvement-v1/pilot-P01-behavior-review-v3.json'
    qreview=json.loads(qualification.read_bytes());assert qreview['verdict']=='pass'
    names=set(old['source_hashes'])|{str(REVIEW.relative_to(ROOT)),str(qualification.relative_to(ROOT)),str(receipt_path.relative_to(ROOT)),'tools/improvement_candidate_c9_p01_v1.py',str(baseline_review.relative_to(ROOT)),str(candidate_provenance.relative_to(ROOT))}
    for reviewed in (review,qreview):
        for name,expected in reviewed['source_hashes'].items():
            assert prior.sha(ROOT/name)==expected,name
            names.add(name)
    # Hash excluded oracle/reference bytes without inspecting their semantic contents.
    names.update(str(p.relative_to(ROOT)) for p in CASE.rglob('*') if p.is_file())
    names.update(str(p.relative_to(ROOT)) for p in skill.rglob('*') if p.is_file())
    value={'status':'frozen','stage':'exploratory_candidate_pilot','model':'gpt-6.1-sol','effort':'medium',
           'concurrency':1,'trajectory_seconds':1200,'retries':0,'conditions':['C9'],'skill_hashes':{'C9':tree_hash(skill)},
           'image_id':old['image_id'],'case_hashes':{'P01':tree_hash(CASE)},
           'source_hashes':{name:prior.sha(ROOT/name) for name in sorted(names)},
           'sequence':[{'case_id':'P01','condition':'C9','repeat':1,'run_id':RUN}],
           'superiority_proven':False,'question_or_orchestration_qualified':False,
           'primary_confirmation_reuse_allowed':False,'limits':['One exposed task cannot prove superiority; include every failed attempt and review cost; C0 and independent held-out tasks remain required','Pure service/domain behavior, no UI/device/production guarantee']}
    with FREEZE.open('x') as f:json.dump(value,f,indent=2)
    return value

# Reuse the exercised bounded preservation protocol without copying it.
from improvement_baseline_q02_v2 import quiesce

def configure():
    prior.FREEZE=FREEZE;prior.PHASE=PHASE;prior.case_directory=case_directory;prior.quiesce=quiesce
    return prior.check()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['freeze','prepare','collect','grade']);parser.add_argument('agent_path',nargs='?');args=parser.parse_args()
    if args.operation=='freeze':result=freeze()
    else:
        configure()
        if args.operation=='prepare':
            intent=ROOT/'results/improvement-v1/candidate-C9-P01-launch-intent-v1.json'
            diagnostics.artifacts.atomic_json(intent,{'started_at':time.time(),'run_id':RUN,'actor_retries_allowed':0},exclusive=True)
            result=prior.launch('P01','C9')
        elif args.operation=='collect':result=prior.collect_run(RUN,args.agent_path)
        else:result=prior.grade_run(RUN)
    print(result if isinstance(result,str) else json.dumps({k:v for k,v in result.items() if k not in {'source_hashes','checks','final'}},ensure_ascii=False))
