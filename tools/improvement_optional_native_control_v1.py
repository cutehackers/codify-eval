"""Prospective native0/1/2 control preparation, not actor allocation or grading.

The original O01 case is exposed infrastructure material, not untouched final
confirmation. All native allocation, observed lifecycle closure and accounting
are performed and recorded by the original coordinator on this shared clock.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat

import improvement_optional_runtime_v8 as runtime
import improvement_optional_broker_v10 as broker
import improvement_optional_native_dispatch_v4 as dispatch
import improvement_optional_native_watch_v3 as observer
from improvement_software_artifacts_v3 import atomic_json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/improvement-v1'
CASE=ROOT/'improvement_cases/fresh-optional-cohort-v1/O01'
FREEZE=BASE/'fresh-optional-native-controls-freeze-v1.json'
REVIEWS=('fresh-optional-native-watch-prelaunch-review-v3.json',
         'fresh-optional-native-dispatch-and-broker-prelaunch-review-v4.json',
         'fresh-optional-native-control-driver-prelaunch-review-v1.json')
SEQUENCE=('solo','one_worker','two_workers')
COUNTS=dict(zip(SEQUENCE,(0,1,2)))
require=runtime.require


def entity(path):
    path=Path(path);value=path.lstat();require(stat.S_ISREG(value.st_mode),'Original regular source required')
    return {'kind':'file','mode':stat.S_IMODE(value.st_mode),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def freeze():
    sources={};reviews={}
    for name in REVIEWS:
        path=BASE/name;value=json.loads(path.read_bytes())
        require(value['verdict']=='pass' and not value['issues'],'Current independent prelaunch PASS required: '+name)
        reviews[name]=entity(path)
        for key,row in value['source_entities'].items():
            source=Path(key) if Path(key).is_absolute() else ROOT/key
            require(entity(source)==row,'Reviewed source changed: '+key)
            require(key not in sources or sources[key]==row,'Conflicting reviewed source pins')
            sources[key]=row
    value={'sequence':list(SEQUENCE),'worker_counts':COUNTS,'case_id':'O01','condition':'A',
        'model':'gpt-6.1-sol','effort':'medium','image_id':runtime.IMAGE,'trajectory_seconds':1200,
        'reviews':reviews,'source_entities':sources,'driver_entity':entity(__file__),
        'public_entity':entity(CASE/'public/request.md'),'metadata_entity':entity(CASE/'metadata.json'),
        'case_inventory':runtime.source.inventory(CASE/'repo'),
        'native_qualified':False,'comparison_eligible':False,'superiority_proven':False,
        'limits':['Exposed infrastructure case and forced worker counts. Never comparative optional-delegation benefit or untouched confirmation.',
                  'Freeze and preparation do not allocate native actors, prove closure, cleanup or whole final costs.']}
    atomic_json(FREEZE,value,exclusive=True);return value


def checked_freeze():
    value=json.loads(FREEZE.read_bytes())
    require(value['sequence']==list(SEQUENCE) and value['worker_counts']==COUNTS
            and value['model']=='gpt-6.1-sol' and value['effort']=='medium'
            and value['trajectory_seconds']==1200 and value['image_id']==runtime.IMAGE,'Frozen control policy changed')
    require(entity(__file__)==value['driver_entity'],'Frozen driver changed')
    for name,row in value['reviews'].items():require(entity(BASE/name)==row,'Frozen review changed: '+name)
    for name,row in value['source_entities'].items():
        path=Path(name) if Path(name).is_absolute() else ROOT/name
        require(entity(path)==row,'Frozen source changed: '+name)
    require(entity(CASE/'public/request.md')==value['public_entity']
            and entity(CASE/'metadata.json')==value['metadata_entity']
            and runtime.source.inventory(CASE/'repo')==value['case_inventory'],'Frozen case changed')
    return value


def public_task(scenario):
    require(scenario in SEQUENCE,'Unregistered native control')
    count=COUNTS[scenario]
    protocol=('INFRASTRUCTURE CONTROL\nImplement the public task below. This is a native execution control, not a comparison. '
        f'Allocate exactly {count} cumulative worker slots through the public broker. '
        'If there are workers, assign each a distinct single editable file with a clear implementation goal that includes '
        'the relevant public requirements. Keep the remaining editable files with root. Do not allocate review-only or dummy '
        'workers for this control. Read the public API and files before assigning scopes. Wait for each genuine worker final, '
        'view every sealed contribution and explicitly accept or reject it with a reason. Integrate once even when there are '
        'zero workers. Root may then correct implementation, verify and finish. Do not ask a follow-up question: the public '
        'task already states the business decisions. Never use hidden cases or another run.\n\nPUBLIC TASK\n')
    return protocol+(CASE/'public/request.md').read_text()


def prepare(scenario,coordinator_id):
    checked_freeze();require(scenario in SEQUENCE,'Unregistered native control')
    for prior in SEQUENCE[:SEQUENCE.index(scenario)]:
        closed=json.loads((BASE/('fresh-optional-native-control-outcome-v1-'+prior+'.json')).read_bytes())
        require(closed['native_control_dimension_pass'] and closed['owned_cleanup_verified'],'Prior native control not closed')
    folder=ROOT/'runtime'/('native-optional-control-v1-'+scenario)
    actor_path='/root/native_optional_control_v1_'+scenario
    output=BASE/('fresh-optional-native-control-preparation-v1-'+scenario+'.json')
    require(not folder.exists() and not output.exists(),'No retries or reused native namespace')
    metadata=json.loads((CASE/'metadata.json').read_bytes())
    root_cap=None
    try:
        prepared=runtime.create(folder,CASE/'repo','O01','A',public_task(scenario),metadata['editable_paths'])
        root_cap=prepared['root_capability'];broker.register(folder,'root',root_cap)
        dispatch_row=dispatch.create(folder,actor_path,coordinator_id,root_cap)
        value={'scenario':scenario,'folder':str(folder),'actor_path':actor_path,'coordinator_id':coordinator_id,
            'root_dispatch':dispatch_row,'observer_argv':['python3',str(Path(observer.__file__).resolve()),folder.name,actor_path,coordinator_id],
            'original_started_at':runtime.load(folder)['started_at'],'deadline':runtime.load(folder)['deadline'],
            'model_actors_allocated':0,'model':'gpt-6.1-sol','effort':'medium',
            'native_qualified':False,'comparison_eligible':False,'superiority_proven':False}
        atomic_json(output,value,exclusive=True);return value
    except BaseException as error:
        failure={'status':'preparation_failed','first_error':{'type':type(error).__name__,'message':str(error)},
            'model_actors_allocated':0,'native_qualified':False,'comparison_eligible':False,'superiority_proven':False}
        if folder.exists():
            try:runtime.failure(folder,error)
            except BaseException as preservation_error:failure['preservation_error']={'type':type(preservation_error).__name__,'message':str(preservation_error)}
            # This preparation function has no native allocation calls. Its
            # own actor-free containers may be preserved and removed here.
            try:failure['owned_cleanup']=runtime.cleanup(folder)
            except BaseException as cleanup_error:failure['cleanup_error']={'type':type(cleanup_error).__name__,'message':str(cleanup_error)}
        atomic_json(output,failure,exclusive=True)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=('freeze','prepare'))
    parser.add_argument('--scenario',choices=SEQUENCE);parser.add_argument('--coordinator-id')
    args=parser.parse_args()
    if args.operation=='freeze':print(json.dumps(freeze()))
    else:
        require(args.scenario is not None and args.coordinator_id is not None,'Exact scenario and coordinator required')
        print(json.dumps(prepare(args.scenario,args.coordinator_id)))
