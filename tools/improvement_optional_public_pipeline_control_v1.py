"""Frozen actor-free public broker transport controls. Never software/comparison results."""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shlex
import stat
import subprocess
import uuid
import time

import improvement_optional_runtime_v8 as runtime
import improvement_optional_broker_v6 as broker
from improvement_software_artifacts_v3 import atomic_json
from improvement_q04_verifier_v5 import machine

ROOT=Path(__file__).resolve().parents[1]
FREEZE=ROOT/'results/improvement-v1/fresh-optional-public-pipeline-controls-freeze-v1.json'
REVIEW=ROOT/'results/improvement-v1/fresh-optional-runtime-prelaunch-review-v8.json'
DRIVER_REVIEW=ROOT/'results/improvement-v1/fresh-optional-public-pipeline-control-driver-review-v1.json'
BROKER_REVIEW=ROOT/'results/improvement-v1/fresh-optional-public-broker-review-v6.json'
SEQUENCE=('solo','one_worker','two_workers','lease_violation')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entity(path):
    mode=Path(path).lstat().st_mode
    runtime.require(stat.S_ISREG(mode),'Regular frozen source required')
    return {'kind':'file','mode':stat.S_IMODE(mode),'sha256':sha(path)}


def freeze():
    report=json.loads(REVIEW.read_bytes());runtime.require(report['verdict']=='pass' and not report['issues'],'Prelaunch review required')
    # Full typed import closure is supplied by independent review; not a hand
    # picked source list. Support the reviewed source entity schema explicitly.
    driver_report=json.loads(DRIVER_REVIEW.read_bytes())
    runtime.require(driver_report['verdict']=='pass' and not driver_report['issues'],'Driver review required')
    entities={}
    broker_report=json.loads(BROKER_REVIEW.read_bytes())
    runtime.require(broker_report['verdict']=='pass' and not broker_report['issues'],'Broker review required')
    for reviewed in (report['source_entities'],driver_report['source_entities'],broker_report['source_entities']):
        for name,row in reviewed.items():
            path=Path(name) if Path(name).is_absolute() else ROOT/name
            runtime.require(entity(path)==row,'Reviewed source kind/mode/content changed: '+name)
            runtime.require(name not in entities or entities[name]==row,'Conflicting independent review pins: '+name)
            entities[name]=row
    value={'sequence':list(SEQUENCE),'case_id':'O01','condition':'A','actor_count':0,'model_calls':0,
           'image_id':runtime.IMAGE,'trajectory_seconds':1200,'source_entities':entities,
           'driver_sha256':sha(__file__),'review_sha256':sha(REVIEW),
           'driver_review_entity':entity(DRIVER_REVIEW),'broker_review_entity':entity(BROKER_REVIEW),
           'driver_entity':entity(__file__),'review_entity':entity(REVIEW),
           'public_request_entity':entity(ROOT/'improvement_cases/fresh-optional-cohort-v1/O01/public/request.md'),
           'metadata_entity':entity(ROOT/'improvement_cases/fresh-optional-cohort-v1/O01/metadata.json'),
           'case_entities':runtime.source.inventory(ROOT/'improvement_cases/fresh-optional-cohort-v1/O01/repo'),
           'metadata_sha256':sha(ROOT/'improvement_cases/fresh-optional-cohort-v1/O01/metadata.json'),
           'runtime_qualified':False,'comparison_eligible':False,'superiority_proven':False,
           'deadline_limit_actual_qualification':False,'integration_runtime_qualification':False}
    atomic_json(FREEZE,value,exclusive=True);return value


def check():
    value=json.loads(FREEZE.read_bytes())
    runtime.require(entity(BROKER_REVIEW)==value['broker_review_entity'],'Frozen broker review changed')
    runtime.require(value['sequence']==list(SEQUENCE) and value['actor_count']==value['model_calls']==0,
                    'Control contract changed')
    runtime.require(entity(DRIVER_REVIEW)==value['driver_review_entity'],'Frozen driver review changed')
    runtime.require(value['driver_sha256']==sha(__file__) and value['review_sha256']==sha(REVIEW),'Frozen driver/review changed')
    runtime.require(entity(__file__)==value['driver_entity'] and entity(REVIEW)==value['review_entity'],'Frozen driver/review mode changed')
    for name,row in value['source_entities'].items():
        path=Path(name) if Path(name).is_absolute() else ROOT/name
        runtime.require(entity(path)==row,'Frozen source entity changed: '+name)
    case=ROOT/'improvement_cases/fresh-optional-cohort-v1/O01'
    runtime.require(runtime.source.inventory(case/'repo')==value['case_entities'] and sha(case/'metadata.json')==value['metadata_sha256'],'Frozen case changed')
    runtime.require(entity(case/'metadata.json')==value['metadata_entity'] and
                    entity(case/'public/request.md')==value['public_request_entity'],'Frozen metadata/public input changed')
    return value


def invoke(folder,job,cap,op,data):
    directory=Path(folder)/'broker-cli'/uuid.uuid4().hex;directory.mkdir(parents=True)
    argv=['python3',str(ROOT/'tools/improvement_optional_broker_v6.py'),'--run',Path(folder).name,'--job',job,'--cap',cap,'--op',op,'--data',json.dumps(data)]
    atomic_json(directory/'intent.json',{'argv':argv,'started_at':time.time()},exclusive=True)
    error=None
    try:
        value=subprocess.run(argv,capture_output=True,timeout=runtime.budget(runtime.load(folder))+30)
        stdout,stderr,code=value.stdout,value.stderr,value.returncode
    except subprocess.TimeoutExpired as failure:
        stdout,stderr,code=failure.stdout or b'',failure.stderr or b'',124
        error={'type':type(failure).__name__,'message':str(failure)}
    for name,raw in (('stdout',stdout),('stderr',stderr)):
        with (directory/name).open('xb') as stream:stream.write(raw)
    atomic_json(directory/'receipt.json',{'returncode':code,'stdout_bytes':len(stdout),'stderr_bytes':len(stderr),
        'stdout_sha256':hashlib.sha256(stdout).hexdigest(),'stderr_sha256':hashlib.sha256(stderr).hexdigest(),
        'finished_at':time.time(),'transport_error':error},exclusive=True)
    runtime.require(error is None and len(stdout)+len(stderr)<=broker.LIMIT+65536,'CLI transport incomplete or over bound; original output retained')
    body=broker.strict.decoded(stdout)
    runtime.require(code==0 and isinstance(body,dict) and body.get('status')=='ok','Public CLI failed: '+str(body))
    return body,code


def transport(folder,job,cap,text,seconds=120):
    body,code=invoke(folder,job,cap,'exec',{'command':text,'seconds':seconds})
    runtime.require(code==0 and body['status']=='ok','Public broker execution failed: '+str(body))
    return body['result']


def comment_command(paths,comment):
    payload='\n// '+comment+'\n'
    code='from pathlib import Path;'+ ';'.join('p=Path('+repr(path)+');p.write_text(p.read_text()+'+repr(payload)+')' for path in paths)
    return 'python3 -c '+shlex.quote(code)


def execute(scenario):
    check();runtime.require(scenario in SEQUENCE,'Unknown preregistered scenario')
    for prior in SEQUENCE[:SEQUENCE.index(scenario)]:
        previous=ROOT/'results/improvement-v1'/('fresh-optional-public-pipeline-control-v1-'+prior+'.json')
        result=json.loads(previous.read_bytes());runtime.require(result['dimension_pass'] and result['owned_cleanup_verified'],'Prior control not closed')
    case=ROOT/'improvement_cases/fresh-optional-cohort-v1/O01';metadata=json.loads((case/'metadata.json').read_bytes())
    folder=ROOT/'runtime'/('control-probe-optional-public-pipeline-v1-'+scenario)
    output=ROOT/'results/improvement-v1'/('fresh-optional-public-pipeline-control-v1-'+scenario+'.json')
    runtime.require(not folder.exists() and not output.exists(),'No retry/replacement control namespace')
    result={'scenario':scenario,'started_at':time.time(),'actor_count':0,'model_calls':0,
            'checks':[],'first_error':None,'dimension_pass':False,'owned_cleanup_verified':False,
            'software_pass':None,'runtime_qualified':False,'comparison_eligible':False,'superiority_proven':False,
            'integration_runtime_qualification':False,'deadline_limit_actual_qualification':False}
    atomic_json(output,result,exclusive=True)
    try:
        allocated=runtime.create(folder,case/'repo','O01','A',(case/'public/request.md').read_text(),metadata['editable_paths'])
        cap=allocated['root_capability'];result['run_id']=allocated['run_id']
        broker.register(folder,'root',cap)
        public_read,read_code=invoke(folder,'root',cap,'read',{})
        runtime.require(read_code==0 and public_read['result']['text']==(case/'public/request.md').read_text(),'Complete exact public request required')
        result['checks'].append({'check':'actual_public_read_once','result':public_read})
        before=runtime.load(folder)
        try:invoke(folder,'root','f'*48,'exec',{'command':'exit 99'})
        except ValueError:pass
        else:raise AssertionError('Wrong capability accepted')
        runtime.require(runtime.load(folder)==before,'Rejected capability changed dispatch state')
        result['checks'].append({'check':'wrong_capability_before_dispatch','pass':True})
        failure=transport(folder,'root',cap,'exit 7')
        runtime.require(failure['exit_code']==7 and failure['output_complete'],'Controlled failure not preserved')
        result['checks'].append({'check':'inner_exit7_no_retry','result':failure})
        count={'solo':0,'one_worker':1,'two_workers':2,'lease_violation':1}[scenario]
        workers=[]
        for index in range(count):
            body,code=invoke(folder,'root',cap,'worker',{'goal':'Actor-free ownership/parallelism control','scope':(metadata['editable_paths'][:2] if count==1 else [metadata['editable_paths'][index]])})
            runtime.require(code==0,'Public broker worker provisioning failed')
            w=body['result'];workers.append(w)
            body,code=invoke(folder,w['job'],w['capability'],'read',{})
            runtime.require(code==0 and body['result']['text']=='Actor-free ownership/parallelism control','Worker original public read required')
        runtime.require(len(runtime.load(folder)['jobs'])==count+1,'Optional Docker membership mismatch')
        if count==2:
            text='python3 -c '+shlex.quote('import time;print(time.time(),flush=True);time.sleep(2);print(time.time(),flush=True)')
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                futures=[pool.submit(transport,folder,w['job'],w['capability'],text) for w in workers]
                values=[future.result() for future in futures]
            runtime.require(all(v['exit_code']==0 and v['output_complete'] for v in values),'Parallel commands failed')
            spans=[list(map(float,v['stdout'].split())) for v in values]
            overlap=min(span[1] for span in spans)-max(span[0] for span in spans)
            runtime.require(overlap>=1,'Real Docker command interiors did not overlap')
            result['checks'].append({'check':'actual_concurrent_worker_processes','overlap_seconds':overlap,'results':values})
        if scenario=='solo':
            timeout=transport(folder,'root',cap,'sleep 10',seconds=1)
            runtime.require(timeout['exit_code']==124 and timeout['output_complete'] and
                            not timeout.get('transport_error'),'Actual inner command timeout missing or transport incomplete')
            public=transport(folder,'root',cap,'/sdks/flutter/bin/flutter test --no-pub --machine')
            analyzed=transport(folder,'root',cap,'/sdks/flutter/bin/flutter analyze --no-pub')
            protocol=machine(public['stdout'],metadata['public_test_count'])
            runtime.require(public['output_complete'] and protocol['well_formed'] and
                            analyzed['output_complete'] and analyzed['exit_code'] not in (124,137,143),'Public process observation incomplete')
            result['checks'].append({'check':'actual_timeout_and_closed_public_tests','timeout':timeout,
                                    'public':public,'machine':protocol,'analyze':analyzed,
                                    'note':'Unimplemented starting fixture results retained; no software pass qualification'})
        if scenario!='lease_violation':
            root_path=metadata['editable_paths'][2]
            text=comment_command([root_path],'root independent control')
            transport(folder,'root',cap,text)
            choices=[]
            for index,w in enumerate(workers):
                scope=metadata['editable_paths'][:2] if count==1 else [metadata['editable_paths'][index]]
                transport(folder,w['job'],w['capability'],comment_command(scope,'worker contribution control'))
                sealed,_=invoke(folder,w['job'],w['capability'],'seal',{})
                viewed,_=invoke(folder,'root',cap,'view',{'slot':w['job']})
                chosen,_=invoke(folder,'root',cap,'decide',{'slot':w['job'],'view':viewed['result']['view'],
                    'decision':'reject' if count==2 and index==1 else 'accept','reason':'Actor-free original contribution decision'})
                choices.append({'slot':w['job'],'sealed':sealed,'viewed':viewed,'chosen':chosen})
            installed,_=invoke(folder,'root',cap,'integrate',{})
            runtime.require(runtime.registry.read(folder/'registry')['active_leases']=={},'Final leases not released')
            for index,path in enumerate(metadata['editable_paths'][:2]):
                accepted=count==1 or count==2 and index==0
                raw=(folder/'root/repo'/path).read_text()
                runtime.require(('// worker contribution control' in raw)==accepted,'Accepted/rejected source bytes not preserved')
            runtime.require('// root independent control' in (folder/'root/repo'/root_path).read_text(),'Unleased root edit lost')
            result['checks'].append({'check':'actual_cli_contribution_pipeline','choices':choices,'integration':installed})
            verified,_=invoke(folder,'root',cap,'verify',{})
            checks=verified['result'];protocol=machine(checks['public']['stdout'],metadata['public_test_count'])
            runtime.require(checks['public']['output_complete'] and protocol['well_formed']
                and checks['analyze']['output_complete'] and checks['analyze']['exit_code']==0,
                'Fixed public verification after comment-only integration incomplete')
            result['checks'].append({'check':'actual_cli_fixed_public_verification','result':verified,'machine':protocol,
                'note':'Original unimplemented fixture behavior retained; not coding superiority'})
        if scenario=='lease_violation':
            path=metadata['editable_paths'][0]
            text='python3 -c '+shlex.quote('from pathlib import Path;p=Path('+repr(path)+');p.write_text(p.read_text()+"\\n// forbidden root lease edit\\n")')
            changed=transport(folder,'root',cap,text);runtime.require(changed['exit_code']==0,'Lease negative command not executed')
            with runtime.lock(folder,'root'):
                try:runtime.snapshot(folder,'root')
                except ValueError as error:
                    runtime.require('leased' in str(error),'Unexpected lease rejection');result['checks'].append({'check':'actual_lease_violation_rejected','error':str(error)})
                else:raise AssertionError('Root leased-file change accepted')
        else:
            for job in runtime.load(folder)['jobs']:
                with runtime.lock(folder,job):runtime.snapshot(folder,job)
        result['dimension_pass']=True
    except BaseException as error:
        result['first_error']={'type':type(error).__name__,'message':str(error)}
        if (folder/'state.json').exists():runtime.failure(folder,error)
    finally:
        if (folder/'state.json').exists():
            try:
                result['closed_state']=runtime.cleanup(folder);result['owned_cleanup_verified']=True
            except BaseException as error:
                result['cleanup_error']={'type':type(error).__name__,'message':str(error)}
        if (folder/'broker').exists():
            try:
                result['broker_ledgers']={job:broker.ledger(folder,job) for job in runtime.load(folder)['jobs'] if (folder/'broker'/job/'control.json').exists()}
                runtime.require(all(a['status']=='completed' for rows in result['broker_ledgers'].values() for a in rows),'Unclosed broker action')
            except BaseException as error:
                result['broker_ledger_error']={'type':type(error).__name__,'message':str(error)}
                result['dimension_pass']=False
        result['finished_at']=time.time()
        result['dimension_pass']=result['dimension_pass'] and result['owned_cleanup_verified']
        if (folder/'state.json').exists():
            state=runtime.load(folder);result['original_started_at']=state['started_at'];result['original_deadline']=state['deadline']
            result['allocation_through_cleanup_seconds']=result['finished_at']-state['started_at']
            result['time_limit_exceeded']=result['finished_at']>state['deadline']
            result['dimension_pass']=result['dimension_pass'] and not result['time_limit_exceeded']
        atomic_json(output,result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('freeze',)+SEQUENCE);args=parser.parse_args()
    print(json.dumps(freeze() if args.action=='freeze' else execute(args.action)))
