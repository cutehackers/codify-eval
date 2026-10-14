"""ROOT post-terminal observations and excluded-cache cleanup for frozen v5 rows.

No actor, grading, admission, retry or broad Docker cleanup is performed here.
The caller must already have observed its original runner process exit normally.
"""
import json
import datetime
from pathlib import Path
import shutil
import subprocess
import sys

import improvement_baseline_root_runner_v7 as runner

r=runner.runtime
ROOT=runner.ROOT


def record_clock(run_id):
    row=next((row for row in runner.coordinator.inputs.sequence() if row['run_id']==run_id),None)
    r.require(row is not None and row['case_id'] in ('B01','B02') and row['worker_cap']==0,
              'Exact frozen solo run required')
    source=Path('/Users/junhyounglee/.codex/sessions/2026/10/10/rollout-2026-10-10T06-52-20-01a122a7-1f52-7810-8588-f0a7a8732fa1.jsonl')
    needle=('improvement_baseline_root_runner_v7.py '+str(ROOT/'results/improvement-v1/baseline-development-v5-nonquestion-solo-plans-v1'/(run_id+'.json'))+' --execute-plan-sha256').encode()
    found=[]
    with source.open('rb') as stream:
        for raw in stream:
            if needle not in raw:continue
            event=json.loads(raw);payload=event.get('payload',{})
            if event['type']=='response_item' and payload.get('type') in ('function_call','custom_tool_call'):
                found.append({'timestamp':event['timestamp'],'call_id':payload.get('call_id'),
                              'tool_name':payload.get('name'),'tool_namespace':payload.get('namespace')})
    r.require(len(found)==1,'Exactly one original ROOT execution dispatch required')
    at=datetime.datetime.fromisoformat(found[0]['timestamp'].replace('Z','+00:00')).timestamp()
    prepared=r.strict.decoded((ROOT/'runtime'/run_id/'coordinator/prepared.json').read_bytes())
    out={'schema_version':1,'run_id':run_id,'native_root_execution_start_observation':found[0],
         'source_path':str(source),'native_tool_dispatch_epoch':at,
         'driver_preparation_started_at':prepared['preparation_started_at'],
         'initial_root_constructor_and_dispatch_seconds':prepared['preparation_started_at']-at,
         'secondary_metric_only':True,'frozen_primary_metric_unchanged':True,
         'note':'Driver whole_observed_seconds starts after Run construction. Preserve native dispatch for full pipeline accounting; freeze the complete boundary before final confirmatory models.'}
    r.atomic_json(ROOT/'results/improvement-v1'/(run_id+'-root-execution-clock-observation-v1.json'),out,exclusive=True)
    return {'run_id':run_id,'initial_root_constructor_and_dispatch_seconds':out['initial_root_constructor_and_dispatch_seconds']}


def summarize(run_id, outcome_sha256):
    base=ROOT/'results/improvement-v1'
    manifest_path=base/'baseline-development-v5-nonquestion-solo-cohort-v1.json'
    manifest_ref=r.question_reference(manifest_path)
    r.require(manifest_ref['entity']['sha256']=='fd89c4c2ebe97f34fe3b02bb90c2a96106ab3b4bcaa201a2e2719d7de3e68f82',
              'Original frozen v5 cohort required')
    manifest=r.strict.decoded(r.question_reference_bytes(manifest_ref))
    matches=[row for row in manifest['order'] if row['run_id']==run_id]
    r.require(len(matches)==1,'Exact frozen nonquestion solo row required')
    row=matches[0]
    for name,entity in manifest['common_source_entities'].items():
        r.require(r.encoded(r.question_file_entity(ROOT/name))==r.encoded(entity),'Frozen source changed')
    folder=ROOT/'runtime'/run_id
    outcome_ref=r.question_reference(folder/'root-driver/runner-outcome.json')
    r.require(outcome_ref['entity']['sha256']==outcome_sha256,'Exact original completed outcome required')
    outcome=r.strict.decoded(r.question_reference_bytes(outcome_ref))
    r.require(outcome['row']==row and outcome['status']=='closed' and outcome['first_error'] is None
              and outcome['all_member_usage_observed'] is True and outcome['owned_cleanup_verified'] is True
              and outcome['cleanup_errors']==[] and outcome['grader_cleanup_errors']==[],
              'Complete original closure and exact owned cleanup required')
    observer=outcome['original_observer_completion']
    r.require(observer['completed'] is True and type(observer['exit_code']) is int
              and observer['exit_code']==0,'Original observer normal completion required')
    terminal=r.strict.decoded(r.question_reference_bytes(observer['terminal_reference']))
    r.require(terminal['reason']=='coordinator_stop' and terminal['normal_completions_observed'] is True,
              'Original observer stopped after native completion required')
    grading=runner.terminal.normal.grading
    contract,private=grading.selected_contract(row['case_id'],None)
    r.require(private is True,'Original private nonquestion grading required')
    receipt_ref=r.question_reference(folder/'grading/verifier/receipt.json')
    receipt=r.strict.decoded(r.question_reference_bytes(receipt_ref))
    classification=grading.classifier.classify(receipt,contract['expected_nonloading_tests'],commands=contract['inner_argv'])
    r.require(classification==outcome['grading']['classification']
              and classification['software_pass']==outcome['software_pass'], 'Actual grader classification differs')
    usage=outcome['usage']
    r.require(usage['distinct_uuid_count']==1 and len(usage['members'])==1
              and usage['unknown_usage_paths']==[] and usage['malformed_counter_info_paths']==[],
              'Exactly one original model with complete usage required')
    member=usage['members'][0]
    raw,_=runner.driver.controller.source.capture.native_capture(Path(member['source']))
    r.require(len(raw)==member['source_bytes']
              and runner.terminal.normal.audit.inventory.core.digest(raw)==member['source_sha256'],
              'Original native source changed')
    state=r.load(folder)
    identities=[state['jobs']['root']['container_id'],receipt['container_id']]
    absent=[]
    for identity in identities:
        result=subprocess.run(['docker','inspect',identity],capture_output=True,text=True)
        r.require(result.returncode!=0 and 'No such object' in result.stderr,'Owned container removal not confirmed')
        absent.append({'container_id':identity,'exit_code':result.returncode,'absence_verified':True})
    summary={'schema_version':1,'row':row,'status':'closed','software_pass':outcome['software_pass'],
             'private_expected_tests':contract['expected_nonloading_tests'],'classification':classification,
             'raw_product_tokens':usage['observed_prefix_totals']['total_tokens'],'usage':usage,
             'whole_observed_seconds':outcome['whole_observed_seconds'],'currency_observed':False,
             'all_member_usage_observed':True,'owned_cleanup_verified':True,'owned_absence':absent,
             'outcome_reference':outcome_ref,'grader_receipt_reference':receipt_ref,
             'full24_comparison_admitted':False,'superiority_proven':False}
    clock_path=base/(run_id+'-root-execution-clock-observation-v1.json')
    if clock_path.exists():
        clock=r.strict.decoded(clock_path.read_bytes())
        summary['secondary_native_dispatch_to_cleanup_seconds']=outcome['finished_at']-clock['native_tool_dispatch_epoch']
        summary['secondary_clock_reference']=r.question_reference(clock_path)
    r.atomic_json(base/(run_id+'-actual-completed-run-summary-v1.json'),summary,exclusive=True)
    cache={'schema_version':1,'run_id':run_id,'source_invariant_verified':True,'excluded_cache_removed':[]}
    for tree in [folder/'root/repo',folder/'grading/source']:
        before=r.source.inventory(tree,None)['source_entities']
        for name in ('.dart_tool','build'):
            path=tree/name
            if not path.exists():continue
            r.require(not path.is_symlink() and path.resolve()==path and path.is_dir(),'Exact generated cache directory required')
            count=sum(p.stat().st_size for p in path.rglob('*') if p.is_file() and not p.is_symlink())
            shutil.rmtree(path)
            cache['excluded_cache_removed'].append({'path':str(path),'bytes':count})
        r.require(r.encoded(r.source.inventory(tree,None)['source_entities'])==r.encoded(before),
                  'Protected source changed during generated cache cleanup')
    cache['bytes_removed']=sum(row['bytes'] for row in cache['excluded_cache_removed'])
    r.atomic_json(base/(run_id+'-actual-excluded-cache-cleanup-v1.json'),cache,exclusive=True)
    return {'run_id':run_id,'software_pass':summary['software_pass'],'expected_tests':summary['private_expected_tests'],
            'raw_tokens':summary['raw_product_tokens'],'whole_observed_seconds':summary['whole_observed_seconds'],
            'owned_IDs_absent':len(absent),'excluded_cache_bytes_removed':cache['bytes_removed']}


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[2]=='--record-root-clock':
        print(json.dumps(record_clock(sys.argv[1]),sort_keys=True),flush=True)
        sys.exit(0)
    r.require(len(sys.argv)==4 and sys.argv[2]=='--outcome-sha256','Exact completed row and outcome hash required')
    print(json.dumps(summarize(sys.argv[1],sys.argv[3]),sort_keys=True),flush=True)
