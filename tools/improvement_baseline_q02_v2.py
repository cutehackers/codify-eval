"""Baseline-only difficulty pilot, public-only actor inputs. No superiority comparison."""
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
FREEZE=ROOT/'results/improvement-v1/baseline-q02-freeze-v2.json'
PHASE='control-probe-baseline-q02-v2'
REVIEW=ROOT/'results/improvement-v1/baseline-q02-runner-review-v2.json'
CASE=ROOT/'improvement_cases/confirmatory/Q02'
RUN=PHASE+'-Q02-A-1'

class EvidencePending(prior.ActorNotTerminal):
    """Same terminal actor/container retained because diagnostics are not preserved."""

def case_directory(case):
    if case!='Q02':raise ValueError('This pilot owns only Q02')
    return CASE

def freeze():
    if FREEZE.exists():raise ValueError('Original pilot is already frozen')
    old=prior.check()
    review=json.loads(REVIEW.read_bytes());assert review['verdict']=='pass'
    receipt_path=ROOT/'results/improvement-v1/confirmation-qualification-v4/Q02/receipt.json'
    receipt=json.loads(receipt_path.read_bytes())
    assert receipt['status']=='behavior_qualified' and receipt['case_id']=='Q02'
    assert receipt['image_id']==old['image_id'] and receipt['source_hashes']==digest_tree(CASE)
    qualification=ROOT/'results/improvement-v1/Q02-behavior-qualification-review-v1.json'
    qreview=json.loads(qualification.read_bytes());assert qreview['verdict']=='pass'
    names=set(old['source_hashes'])|{str(REVIEW.relative_to(ROOT)),str(qualification.relative_to(ROOT)),str(receipt_path.relative_to(ROOT)),'tools/improvement_baseline_q02_v2.py'}
    for reviewed in (review,qreview):
        for name,expected in reviewed['source_hashes'].items():
            assert prior.sha(ROOT/name)==expected,name
            names.add(name)
    # Hash excluded oracle/reference bytes without inspecting their semantic contents.
    names.update(str(p.relative_to(ROOT)) for p in CASE.rglob('*') if p.is_file())
    value={'status':'frozen','stage':'baseline_only_difficulty_pilot','model':'gpt-6.1-sol','effort':'medium',
           'concurrency':1,'trajectory_seconds':1200,'retries':0,'conditions':['A'],'skill_hashes':{},
           'image_id':old['image_id'],'case_hashes':{'Q02':tree_hash(CASE)},
           'source_hashes':{name:prior.sha(ROOT/name) for name in sorted(names)},
           'sequence':[{'case_id':'Q02','condition':'A','repeat':1,'run_id':RUN}],
           'superiority_proven':False,'question_or_orchestration_qualified':False,
           'limits':['One baseline trajectory cannot estimate power or prove superiority','Pure service/domain behavior, no UI/device/production guarantee']}
    with FREEZE.open('x') as f:json.dump(value,f,indent=2)
    return value

def quiesce(run_id,metadata,agent_path):
    from collect import find_session
    from improvement_usage_v4 import snapshot
    out=ROOT/'results'/run_id;out.mkdir(exist_ok=True,parents=True)
    attempt=out/('quiescence-attempt-'+uuid.uuid4().hex+'.json')
    journal={'started_at':time.time(),'actual_actor_path':agent_path,'first_error':None,'state':'intent'}
    diagnostics.artifacts.atomic_json(attempt,journal,exclusive=True)
    try:
        source=find_session(agent_path)
        raw=source.read_bytes()
        source_copy=out/(attempt.stem+'-native.jsonl')
        with source_copy.open('xb') as f:f.write(raw)
        journal.update(native_source=str(source),source_copy=str(source_copy),source_prefix_bytes=len(raw),source_sha256=hashlib.sha256(raw).hexdigest())
        diagnostics.artifacts.atomic_json(attempt,journal)
        if not raw.endswith(b'\n'):raise prior.ActorNotTerminal('Incomplete native prefix; observe same source')
        observed=snapshot(raw,agent_path,str(source))
        if not observed['native_completion_observed']:raise prior.ActorNotTerminal('Actual original actor still not complete')
        identity=json.loads(subprocess.check_output(['docker','inspect',metadata['container']],text=True,timeout=30))[0]
        assert identity['Image']==metadata['image_id'] and identity['HostConfig']['NetworkMode']=='none'
        assert sorted(m['Source'] for m in identity['Mounts'])==sorted([str(ROOT/'runtime'/run_id/'repo'),str(ROOT/'runtime'/run_id/'control-inputs')])
        journal['identity_before']=identity;diagnostics.artifacts.atomic_json(attempt,journal)
        if identity['State']['Running']:
            try:subprocess.run(['docker','stop','-t','2',metadata['container']],capture_output=True,check=True,timeout=10)
            except (subprocess.TimeoutExpired,subprocess.CalledProcessError) as error:
                journal['original_stop_error']={'type':type(error).__name__,'message':str(error)}
                diagnostics.artifacts.atomic_json(attempt,journal)
                subprocess.run(['docker','kill',metadata['container']],capture_output=True,check=True,timeout=10)
        after=json.loads(subprocess.check_output(['docker','inspect',metadata['container']],text=True,timeout=30))[0]
        assert after['Id']==identity['Id'] and not after['State']['Running']
        journal['identity_after']=after;diagnostics.artifacts.atomic_json(attempt,journal)
        diff=out/(attempt.stem+'-docker-diff.txt')
        with diff.open('x') as f:subprocess.run(['docker','diff',metadata['container']],stdout=f,stderr=subprocess.PIPE,text=True,check=True,timeout=30)
        journal['docker_diff']=str(diff)
        diagnostics.preserve_tmp(out,metadata['container'],'product')
        journal.update(state='preserved',finished_at=time.time(),actor_filesystem_stopped=True)
        diagnostics.artifacts.atomic_json(attempt,journal)
        diagnostics.artifacts.atomic_json(out/'quiescence.json',journal)
        return out
    except prior.ActorNotTerminal as error:
        journal.update(state='native_pending_same_actor',first_error={'type':type(error).__name__,'message':str(error)},needed_container_retained=True)
        diagnostics.artifacts.atomic_json(attempt,journal)
        raise
    except Exception as error:
        journal.update(state='evidence_pending_same_resources',first_error={'type':type(error).__name__,'message':str(error)},needed_container_retained=True)
        diagnostics.artifacts.atomic_json(attempt,journal)
        raise EvidencePending('Original evidence failure preserved; reconcile same actor/container without restart: '+str(error)) from error

def configure():
    prior.FREEZE=FREEZE;prior.PHASE=PHASE;prior.case_directory=case_directory;prior.quiesce=quiesce
    return prior.check()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['freeze','prepare','collect','grade']);parser.add_argument('agent_path',nargs='?');args=parser.parse_args()
    if args.operation=='freeze':result=freeze()
    else:
        configure()
        if args.operation=='prepare':
            intent=ROOT/'results/improvement-v1/baseline-q02-launch-intent-v2.json'
            diagnostics.artifacts.atomic_json(intent,{'started_at':time.time(),'run_id':RUN,'actor_retries_allowed':0},exclusive=True)
            result=prior.launch('Q02','A')
        elif args.operation=='collect':result=prior.collect_run(RUN,args.agent_path)
        else:result=prior.grade_run(RUN)
    print(result if isinstance(result,str) else json.dumps(result,ensure_ascii=False))
