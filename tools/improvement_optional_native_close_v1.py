"""Coordinator-triggered normal native closure, preservation and fresh grading.

Caller must supply its authenticated original current inventory source/call and
commit to no further member deliveries. No native actors are dispatched here.
Prelaunch reviewed/frozen caller and observer qualification are separate gates.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import time

from collect import find_session
import improvement_optional_native_audit_v1 as audit
import improvement_optional_broker_v10 as broker
import improvement_optional_runtime_v9 as runtime
import improvement_q04_verifier_v5 as verifier
from improvement_software_artifacts_v3 import atomic_json,encoded

ROOT=Path(__file__).resolve().parents[1]
require=audit.require


def capture(path,limit):
    path=Path(path);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);require(stat.S_ISREG(before.st_mode) and before.st_size<=limit,'Bounded original source required')
        chunks=[];remaining=before.st_size
        while remaining:
            piece=os.read(fd,min(1024*1024,remaining));require(bool(piece),'Native source truncated while capturing')
            chunks.append(piece);remaining-=len(piece)
        after=os.fstat(fd);current=path.lstat()
        require(stat.S_ISREG(current.st_mode) and (before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)==(current.st_dev,current.st_ino)
                and min(after.st_size,current.st_size)>=before.st_size,'Native source replaced or truncated during capture')
        return b''.join(chunks)
    finally:os.close(fd)


def evidence(folder,coordinator_source,inventory_call_id):
    state=runtime.registry.read(folder/'registry');config=state['configuration']
    directory=folder/'native-dispatch';root_row=audit.inventory.decoded(broker.original(directory/'intents/root.json'))
    root_path=root_row['intent']['agent_path'];rows={'root':root_row}
    for job in state['workers']:rows[job]=audit.inventory.decoded(broker.original(directory/'intents'/(job+'.json')))
    locators={row['intent']['agent_path']:find_session(row['intent']['agent_path']) for row in rows.values()}
    raws={path:capture(locator,256*1024*1024) for path,locator in locators.items()}
    parent_raw=capture(coordinator_source,256*1024*1024)
    # The coordinator is still live. Closure requires its complete captured
    # prefix; a partial trailing delivery cannot be silently discarded.
    require(parent_raw.endswith(b'\n'),'Original coordinator capture must be complete; retain same live source and retry observation before closure')
    parent_prefix=parent_raw
    provision={'run_id':config['run_id'],'configuration_sha256':runtime.registry.sha(config),
               'jobs':{job:row['provision'] for job,row in rows.items()}}
    root_events=audit.inventory.core.parse(raws[root_path]);spawns={}
    for cid,event,args,receipt in audit.membership.original.operations(root_events):
        spawns[cid]={'agent_path':root_path+'/'+args['task_name'],
                     'request_token_sha256':hashlib.sha256(args['message'].encode()).hexdigest()}
    contracts={};ledgers={}
    for job,row in rows.items():
        path=row['intent']['agent_path'];control=audit.inventory.decoded(broker.original(folder/'broker'/job/'control.json'))
        contracts[path]={'job':job,'agent_path':path,'run_name':folder.name,'broker_script':str(Path(broker.__file__).resolve()),
            'capability_sha256':control['capability_sha256'],'request_sha256':row['intent']['public_request_sha256'],
            'reply_sha256':None,'spawns':spawns if job=='root' else {}}
        ledgers[path]=broker.ledger(folder,job)
    coordinator_id=audit.inventory.core.parse(parent_prefix)[0]['payload']['id']
    commitment={'parent_id':coordinator_id,'root_path':root_path,'member_paths':sorted(raws),
        'inventory_call_id':inventory_call_id,'parent_sha256':hashlib.sha256(parent_prefix).hexdigest(),
        'parent_bytes':len(parent_prefix),'no_more_delivery':True}
    proof=audit.audit(config,state,root_row['intent'],{job:row['intent'] for job,row in rows.items() if job!='root'},
        parent_prefix,raws[root_path],{path:raw for path,raw in raws.items() if path!=root_path},
        provision,folder/'registry',contracts,ledgers,{path:str(locator) for path,locator in locators.items()},inventory_call_id,commitment)
    return {'proof':proof,'raws':raws,'locators':locators,'coordinator_raw':parent_raw,'contracts':contracts,'ledgers':ledgers}


def close(folder,coordinator_source,inventory_call_id,private_acceptance):
    folder=Path(folder).resolve();require(folder.parent==ROOT/'runtime','Exact owned runtime namespace required')
    out=folder/'native-close';out.mkdir()  # No closure reruns or overwritten evidence.
    record={'started_at':time.time(),'original_started_at':runtime.load(folder)['started_at'],
            'native_qualified':False,'whole_final_cost_qualified':False,'comparison_eligible':False,'superiority_proven':False,
            'owned_cleanup_verified':False,'software_combined_pass':False,'first_error':None}
    atomic_json(out/'intent.json',{'coordinator_source':str(Path(coordinator_source).resolve()),'inventory_call_id':inventory_call_id,
        'private_acceptance':str(Path(private_acceptance).resolve()),'started_at':record['started_at']},exclusive=True)
    try:
        data=evidence(folder,coordinator_source,inventory_call_id)
        for path,raw in data['raws'].items():
            job='root' if path==data['proof']['membership']['root_path'] else path.rsplit('/',1)[-1]
            with (out/(job+'.jsonl')).open('xb') as stream:stream.write(raw)
        with (out/'coordinator.jsonl').open('xb') as stream:stream.write(data['coordinator_raw'])
        atomic_json(out/'audit.json',data['proof'],exclusive=True)
        atomic_json(out/'contracts.json',data['contracts'],exclusive=True);atomic_json(out/'ledgers.json',data['ledgers'],exclusive=True)
        require(all(capture(data['locators'][path],256*1024*1024)==raw for path,raw in data['raws'].items()),
                'Member source changed before stopped cleanup')
        cleaned=runtime.cleanup(folder)
        record['owned_cleanup_verified']=all(row['status']=='removed' for row in cleaned['jobs'].values())
        require(record['owned_cleanup_verified'],'Exact owned cleanup not complete')
        require(all(capture(data['locators'][path],256*1024*1024)==raw for path,raw in data['raws'].items()),
                'Member source changed after cleanup')
        atomic_json(folder/'native-observer/stop.json',{'reason':'coordinator_stop','root_path':data['proof']['membership']['root_path'],
            'parent_id':data['proof']['membership']['coordinator_native_id']},exclusive=True)
        record['source_fences_unchanged']=True;record['usage']=data['proof']['usage']
        events=[audit.inventory.decoded(p.read_bytes()) for p in sorted((folder/'events').glob('*.json'))]
        snapshots=[e for e in events if e.get('op')=='stopped_snapshot' and e.get('job')=='root']
        require(snapshots and snapshots[-1]['scope_error'] is None,'Final stopped source scope guard failed')
        acceptance=Path(private_acceptance).resolve()
        config=audit.inventory.decoded(broker.original(folder/'registry/configuration.json'))
        expected=ROOT/'improvement_cases/fresh-optional-cohort-v1'/config['case_id']/'private/acceptance_test.dart'
        require(acceptance==expected and acceptance.is_file() and not acceptance.is_symlink(),'Exact evaluator-owned private acceptance required')
        source=out/'combined-source';shutil.copytree(snapshots[-1]['export'],source)
        require(not (source/'test/author_acceptance_test.dart').exists(),'Private grader destination collision')
        shutil.copyfile(acceptance,source/'test/author_acceptance_test.dart')
        verified=verifier.verify(source,out/'combined-verifier',cleaned['deadline'],expected_tests=24)
        record['verification']=verified;record['software_combined_pass']=verified['pass']
        require(verified.get('removed') is True,'Fresh verifier cleanup incomplete')
        require(all(capture(data['locators'][path],256*1024*1024)==raw for path,raw in data['raws'].items()),
                'Member source changed through fresh grading')
    except BaseException as error:record['first_error']={'type':type(error).__name__,'message':str(error)}
    record['finished_at']=time.time();record['whole_observed_seconds']=record['finished_at']-record['original_started_at']
    atomic_json(out/'outcome.json',record,exclusive=True)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run');parser.add_argument('coordinator_source');parser.add_argument('inventory_call_id');parser.add_argument('private_acceptance')
    args=parser.parse_args();value=close(ROOT/'runtime'/args.run,args.coordinator_source,args.inventory_call_id,args.private_acceptance)
    print(json.dumps({'owned_cleanup_verified':value['owned_cleanup_verified'],'software_combined_pass':value['software_combined_pass'],'first_error':value['first_error']}))
