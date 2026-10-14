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
import re
import time

import improvement_optional_runtime_v10 as runtime
import improvement_optional_broker_v10 as broker
import improvement_optional_native_dispatch_v4 as dispatch
import improvement_optional_native_watch_v4 as observer
import improvement_optional_native_audit_v4 as audit
import improvement_optional_native_close_v4 as closer
import improvement_q04_verifier_v5 as verifier
from improvement_software_artifacts_v3 import atomic_json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/improvement-v1'
CASE=ROOT/'improvement_cases/fresh-optional-cohort-v1/O01'
FREEZE=BASE/'fresh-optional-native-controls-freeze-v9.json'
REVIEWS=('fresh-optional-native-dispatch-and-broker-prelaunch-review-v4.json',
         'fresh-optional-runtime-prelaunch-review-v10.json',
         'fresh-optional-native-lifecycle-prelaunch-review-v4.json',
         'fresh-optional-inventory-retired-prelaunch-review-v4.json',
         'fresh-optional-native-delivery-graph-prelaunch-review-v1.json',
         'fresh-optional-native-composite-closure-prelaunch-review-v4.json',
         'fresh-optional-native-control-driver-prelaunch-review-v9.json')
SEQUENCE=('solo','one_worker','two_workers')
COUNTS=dict(zip(SEQUENCE,(0,1,2)))
require=runtime.require


def entity(path):
    path=Path(path);value=path.lstat();require(stat.S_ISREG(value.st_mode),'Original regular source required')
    return {'kind':'file','mode':stat.S_IMODE(value.st_mode),'bytes':value.st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def reviewed_entity(path,row):
    require(isinstance(row,dict) and set(row) in ({'kind','mode','sha256'},{'kind','mode','bytes','sha256'}) and
            row['kind']=='file' and type(row['mode']) is int and
            isinstance(row['sha256'],str) and re.fullmatch('[0-9a-f]{64}',row['sha256']) and
            ('bytes' not in row or type(row['bytes']) is int and row['bytes']>=0), 'Exact typed review file pin required')
    actual=entity(path)
    require(runtime.encoded(row)==runtime.encoded({key:actual[key] for key in row}), 'Reviewed file entity changed: '+str(path))
    # Old and new reports independently verify identical files; normalize both
    # after validation while retaining every byte-count pin supplied by either.
    return actual


def freeze():
    sources={};reviews={}
    for name in REVIEWS:
        path=BASE/name;value=json.loads(path.read_bytes())
        require(value['verdict']=='pass' and not value['issues'],'Current independent prelaunch PASS required: '+name)
        require(isinstance(value['source_entities'],dict) and bool(value['source_entities']),'Nonempty independent source closure required')
        reviews[name]=entity(path)
        for key,row in value['source_entities'].items():
            source=Path(key) if Path(key).is_absolute() else ROOT/key
            row=reviewed_entity(source,row)
            require(key not in sources or sources[key]==row,'Conflicting reviewed source pins')
            sources[key]=row
    value={'sequence':list(SEQUENCE),'worker_counts':COUNTS,'case_id':'O01','condition':'A',
        'model':'gpt-6.1-sol','effort':'medium','image_id':runtime.IMAGE,'trajectory_seconds':1200,
        'reviews':reviews,'source_entities':sources,'driver_entity':entity(__file__),
        'private_acceptance_entity':entity(CASE/'private/acceptance_test.dart'),
        'public_entity':entity(CASE/'public/request.md'),'metadata_entity':entity(CASE/'metadata.json'),
        'case_inventory':runtime.source.inventory(CASE/'repo'),
        'native_qualified':False,'comparison_eligible':False,'superiority_proven':False,
        'limits':['Exposed infrastructure case and forced worker counts. Never comparative optional-delegation benefit or untouched confirmation.',
                  'Freeze and preparation do not allocate native actors, prove closure, cleanup or whole final costs.']}
    atomic_json(FREEZE,value,exclusive=True);return value


def checked_freeze():
    value=json.loads(FREEZE.read_bytes())
    require(value['sequence']==list(SEQUENCE) and runtime.encoded(value['worker_counts'])==runtime.encoded(COUNTS)
            and value['model']=='gpt-6.1-sol' and value['effort']=='medium'
            and type(value['trajectory_seconds']) is int and value['trajectory_seconds']==1200
            and value['image_id']==runtime.IMAGE and value['case_id']=='O01' and value['condition']=='A'
            and value['native_qualified'] is False and value['comparison_eligible'] is False and value['superiority_proven'] is False,'Frozen control policy changed')
    require(set(value['reviews'])==set(REVIEWS),'All exact required reviews must remain frozen')
    expected_sources={}
    for name in REVIEWS:
        review=json.loads((BASE/name).read_bytes())
        require(review['verdict']=='pass' and not review['issues'] and bool(review['source_entities']),'Required reviewed closure missing')
        for key,row in review['source_entities'].items():
            source=Path(key) if Path(key).is_absolute() else ROOT/key
            row=reviewed_entity(source,row)
            require(key not in expected_sources or expected_sources[key]==row,'Conflicting reviewed closure')
            expected_sources[key]=row
    require(runtime.encoded(value['source_entities'])==runtime.encoded(expected_sources),'Frozen dependency closure differs from original reviews')
    essential={Path(module.__file__).resolve() for module in (runtime,broker,dispatch,observer,audit,closer,verifier)}|{Path(__file__).resolve()}
    registered={Path(key).resolve() if Path(key).is_absolute() else (ROOT/key).resolve() for key in expected_sources}
    require(essential<=registered,'Essential driver and dynamic script dependencies missing')
    require(runtime.encoded(entity(__file__))==runtime.encoded(value['driver_entity']),'Frozen driver changed')
    for name,row in value['reviews'].items():require(runtime.encoded(entity(BASE/name))==runtime.encoded(row),'Frozen review changed: '+name)
    for name,row in value['source_entities'].items():
        path=Path(name) if Path(name).is_absolute() else ROOT/name
        require(runtime.encoded(entity(path))==runtime.encoded(row),'Frozen source changed: '+name)
    require(runtime.encoded(entity(CASE/'private/acceptance_test.dart'))==runtime.encoded(value['private_acceptance_entity'])
            and runtime.encoded(entity(CASE/'public/request.md'))==runtime.encoded(value['public_entity'])
            and runtime.encoded(entity(CASE/'metadata.json'))==runtime.encoded(value['metadata_entity'])
            and runtime.encoded(runtime.source.inventory(CASE/'repo'))==runtime.encoded(value['case_inventory']),'Frozen case changed')
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
    require(isinstance(coordinator_id,str) and re.fullmatch('[A-Za-z0-9_-]{1,100}',coordinator_id),'Valid original coordinator identity required before allocation')
    checked_freeze();require(scenario in SEQUENCE,'Unregistered native control')
    for prior in SEQUENCE[:SEQUENCE.index(scenario)]:
        closed=json.loads((BASE/('fresh-optional-native-control-outcome-v9-'+prior+'.json')).read_bytes())
        require(closed['native_control_dimension_pass'] is True and closed['owned_cleanup_verified'] is True,'Prior native control not closed')
    folder=ROOT/'runtime'/('native-optional-control-v9-'+scenario)
    actor_path='/root/native_optional_control_v9_'+scenario
    output=BASE/('fresh-optional-native-control-preparation-v9-'+scenario+'.json')
    require(not folder.exists() and not output.exists(),'No retries or reused native namespace')
    metadata=json.loads((CASE/'metadata.json').read_bytes())
    # Exclusive attempt ownership precedes SDK effects and canonical output.
    # Losing this admission must never enter another invocation's cleanup/report path.
    attempt=BASE/('fresh-optional-native-control-allocation-intent-v9-'+scenario+'.json')
    atomic_json(attempt,{'scenario':scenario,'folder':str(folder),'output':str(output),
        'actor_path':actor_path,'coordinator_id':coordinator_id,'started_at':time.time(),
        'driver_sha256':entity(__file__)['sha256'],'model_actors_allocated':0},exclusive=True)
    root_cap=None;ownership=[]
    def own(created):
        require(Path(created).resolve()==folder,'Ownership callback path changed')
        ownership.append(folder)
    try:
        prepared=runtime.create(folder,CASE/'repo','O01','A',public_task(scenario),metadata['editable_paths'],record_ownership=own)
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
        failure['runtime_ownership_observed']=bool(ownership)
        if ownership:
            try:runtime.failure(folder,error)
            except BaseException as preservation_error:failure['preservation_error']={'type':type(preservation_error).__name__,'message':str(preservation_error)}
            # This preparation function has no native allocation calls. Its
            # own actor-free containers may be preserved and removed here.
            try:failure['owned_cleanup']=runtime.cleanup(folder)
            except BaseException as cleanup_error:failure['cleanup_error']={'type':type(cleanup_error).__name__,'message':str(cleanup_error)}
        try:atomic_json(output,failure,exclusive=True)
        except BaseException as report_error:
            print(json.dumps({'original_preparation_failure':failure,'report_error':{'type':type(report_error).__name__,'message':str(report_error)}}))
        raise


def close_control(scenario,coordinator_source,inventory_call_id):
    # Verification of the prospectively frozen caller, closure, grader and
    # private fixture precedes any stopped cleanup or grading effect.
    checked_freeze();require(scenario in SEQUENCE,'Unregistered native control')
    folder=ROOT/'runtime'/('native-optional-control-v9-'+scenario)
    prepared=json.loads((BASE/('fresh-optional-native-control-preparation-v9-'+scenario+'.json')).read_bytes())
    require(prepared['scenario']==scenario and prepared['folder']==str(folder) and
            prepared['actor_path']=='/root/native_optional_control_v9_'+scenario and
            prepared['model']=='gpt-6.1-sol' and prepared['effort']=='medium',
            'Original preparation does not own requested closure')
    config=runtime.load(folder)
    original_config=json.loads(broker.original(folder/'configuration.json'))
    require(hashlib.sha256(runtime.encoded(original_config)).hexdigest()==config['configuration_sha256'],
            'Original runtime configuration changed')
    require(config['started_at']==prepared['original_started_at'] and config['deadline']==prepared['deadline'] and
            original_config['case']=='O01' and original_config['condition']=='A',
            'Closure original clock or case changed')
    return closer.close(folder,coordinator_source,inventory_call_id,CASE/'private/acceptance_test.dart')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=('freeze','prepare','close'))
    parser.add_argument('--scenario',choices=SEQUENCE);parser.add_argument('--coordinator-id')
    parser.add_argument('--coordinator-source');parser.add_argument('--inventory-call-id')
    args=parser.parse_args()
    if args.operation=='freeze':print(json.dumps(freeze()))
    elif args.operation=='prepare':
        require(args.scenario is not None and args.coordinator_id is not None,'Exact scenario and coordinator required')
        print(json.dumps(prepare(args.scenario,args.coordinator_id)))

    else:
        require(args.scenario is not None and args.coordinator_source is not None and args.inventory_call_id is not None,'Exact current original closure inputs required')
        print(json.dumps(close_control(args.scenario,args.coordinator_source,args.inventory_call_id)))
