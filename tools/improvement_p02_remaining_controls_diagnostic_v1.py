"""Observe six remaining controls. Never qualify fixtures from this diagnostic."""
import hashlib
import json
import shutil
import time
from pathlib import Path
from prepare import ROOT
from improvement_p02_verifier_v3 import verify
from improvement_p02_assertion_classifier_v1 import assertion_failure_names
from improvement_qualify_v3 import failed_tests
from improvement_software_artifacts_v3 import atomic_json, tree
from improvement_p02_controls_check_v4 import case_inventory


def main():
    review_path=ROOT/'results/improvement-v1/P02-controls-check-v4-prelaunch-review-v1.json'
    review=json.loads(review_path.read_text())
    assert review['verdict']=='pass' and not review['issues']
    for pins in (review['sourcepins'],review['evidencepins']):
        for name,digest in pins.items():
            assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    case=ROOT/'improvement_cases/pilot-expansion-v10/P02'
    coverage=json.loads((ROOT/'results/improvement-v1/pilot-P02-contract-coverage-review-v4.json').read_text())
    pins=coverage['fullcurrentv10inventory'];assert case_inventory(case)==pins
    controls=json.loads((case/'negative-manifest.json').read_text())['controls'][2:]
    assert len(controls)==6
    folder=ROOT/'runtime/protocol-probes/p02-v10-remaining-controls-diagnostic-v1';folder.mkdir()
    value={'status':'running','purpose':'diagnostic_observation_only','fixture_qualified':False,
           'historical_regrade':False,'candidate_runs':False,'superiority_proven':False,
           'source_inventory':pins,'executor_review_sha256':hashlib.sha256(review_path.read_bytes()).hexdigest(),
           'helper_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'stages':[],'started_at':time.time()}
    receipt=folder/'receipt.json';atomic_json(receipt,value,exclusive=True)
    deadline=time.time()+600
    try:
        for control in controls:
            assert case_inventory(case)==pins
            label=control['id'];assert label.replace('_','').isalnum()
            source=folder/(label+'-source');shutil.copytree(case/'repo',source)
            overlay=(case/control['overlay']).resolve();assert overlay.is_relative_to(case/'negative')
            artifacts={name:item for name,item in tree(overlay).items() if item['kind']=='file'}
            assert set(artifacts)=={'lib/event_processor.dart','lib/checkpoint_codec.dart'}
            assert {n:item['sha256'] for n,item in artifacts.items()}==control['files_sha256']
            for name in artifacts:shutil.copyfile(overlay/name,source/name)
            shutil.copytree(case/'oracle/test',source/'test',dirs_exist_ok=True)
            destination=folder/(label+'-execution');result=verify(source,destination,deadline,24,True)
            log=result['checks'][1]['stdout'] if len(result['checks'])>1 else ''
            names,incomplete=failed_tests(log);assertions,nonassert=assertion_failure_names(log)
            row={'id':label,'status':result['status'],'checks':[r['exit_code'] for r in result['checks']],
                 'machine':result.get('machine'),'failed_tests':sorted(names),'assertions':sorted(assertions),
                 'nonassertion_error':nonassert,'incomplete':incomplete,'removed':result.get('removed'),
                 'source_unchanged':result.get('source_unchanged'),'receipt_sha256':hashlib.sha256((destination/'receipt.json').read_bytes()).hexdigest(),
                 'lock_unchanged':hashlib.sha256((source/'pubspec.lock').read_bytes()).hexdigest()==hashlib.sha256((destination/'repo/pubspec.lock').read_bytes()).hexdigest(),
                 'qualified':False,'expected_declared_names':control['discriminating_test_names']}
            value['stages'].append(row);atomic_json(receipt,value)
            print(json.dumps({'id':label,'checks':row['checks'],'failed_count':len(names),'removed':row['removed']}),flush=True)
            assert row['status']=='completed' and row['removed'] and row['source_unchanged'], 'Incomplete diagnostic execution'
        value['status']='observed_pending_semantic_failure_mapping_review'
    except Exception as error:
        value.update(status='diagnostic_error',first_error={'type':type(error).__name__,'message':str(error)})
    finally:
        value['case_unchanged']=case_inventory(case)==pins;value['finished_at']=time.time();atomic_json(receipt,value)
    return value


if __name__=='__main__':main()
