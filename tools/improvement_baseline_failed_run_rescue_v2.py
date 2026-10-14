"""Post-failure engineering grading and exact owned SDK cleanup for first row.

The original closure failure stays an evaluation error. This does not repair or
admit that comparison retrospectively. Original model execution is never retried.
The trusted calling ROOT obtains the final unfiltered native inventory first.
"""
import copy
from pathlib import Path
import time

import improvement_baseline_root_source_v4 as sources
import improvement_baseline_native_audit_v5 as audit
import improvement_baseline_grading_v3 as grading
import improvement_baseline_failure_close_v5 as cleanup
import improvement_baseline_normal_close_v9 as parent_guard

runtime=grading.runtime
coordinator=grading.coordinator
ROOT=grading.ROOT
require=runtime.require
encoded=runtime.encoded
_ctx=None


class Rescue:
    def __init__(self,owner,row,frozen_sources):
        require(row==next(r for r in grading.inputs.sequence() if r['case_id']=='B01'
            and r['condition']=='A' and r['worker_cap']==0),'Exact original failed row required')
        self.owner=owner;self.row=copy.deepcopy(row);self.graph=copy.deepcopy(frozen_sources)
        self.folder=ROOT/'runtime'/row['run_id'];self.path=row['actor_path']
        self.prepared_reference=runtime.question_reference(self.folder/'coordinator/prepared.json')
        self.binding_reference=runtime.question_reference(self.folder/'root-startup-binding/binding.json')
        self.failure_reference=runtime.question_reference(self.folder/'root-driver/runner-outcome.json')
        failure=runtime.strict.decoded(runtime.question_reference_bytes(self.failure_reference))
        require(failure['first_error']=={'type':'ValueError','message':'Normal close must use exact original sealed source/registry in same ROOT call'} and failure['status']=='closure_incomplete',
                'Exact original pre-grading closure failure required')
        private=runtime.strict.decoded(runtime.question_reference_bytes(
            runtime.question_reference(self.folder/'root-driver/private-create-result.json')))
        self.capability=private['root_capability']
        state,members=runtime.declared_runtime(self.folder,self.capability)
        require(set(state['jobs'])=={'root'} and not members['workers'],'Original root-only owned SDK required')
        original=runtime.strict.decoded(runtime.question_reference_bytes(self.binding_reference))['root_job']
        require(encoded(cleanup.immutable_job_fields({'jobs':{'root':original}}))
                ==encoded(cleanup.immutable_job_fields(state)),'Original bound container ownership changed')
        self.jobs=cleanup.immutable_job_fields(state);self.clock=(state['started_at'],state['deadline'])
        self.registry=copy.deepcopy(members)
        self.registry_pin=cleanup.registry_snapshot_fingerprint(cleanup.membership.reservation_prefix(self.folder/'registry'))
        import improvement_baseline_native_watch_v4 as watch
        self.locator=watch.find_session(self.path)
        origin=owner.root_origin(self.locator,self.path)
        self.parent,self.parent_pin=owner.parent();self.latest_parent=self.parent
        self.child,self.child_pin=sources.capture.native_capture(self.locator,origin['child_entity'])
        native_id=origin['native_join']['child_native_id']
        events=audit.inventory.core.parse(self.child)
        contexts=[e['payload'] for e in events if e['type']=='turn_context'];require(len(contexts)==1,'Original sole turn required')
        turn={'schema_version':1,'binding':{'agent_path':self.path,'actor_native_id':native_id,
                'parent_native_id':owner.value['parent_native_id']},'job':'root','expected_turns':1,
              'turn_ids':[audit.routes.lifecycle.turn_id(contexts[0])],'native_sha256':audit.inventory.core.digest(self.child),
              'worker_cap':0,'phase':'terminal'}
        parent_events=audit.inventory.core.parse(self.parent)
        cid=[e['payload']['call_id'] for e in parent_events if e['payload'].get('type')=='function_call'
             and audit.inventory.core.route(e['payload'],'collaboration','list_agents')][-1]
        commitment={'parent_id':owner.value['parent_native_id'],'root_path':self.path,'member_paths':[self.path],
            'inventory_call_id':cid,'parent_sha256':audit.inventory.core.digest(self.parent),
            'parent_bytes':len(self.parent),'no_more_delivery':True}
        paths=[self.folder/'configuration.json',self.folder/'native-dispatch/configuration.json',
               self.folder/'native-dispatch/intents/root.json',self.folder/'broker/root/control.json']
        self.controls={str(p):runtime.question_reference(p) for p in paths}
        dispatch=runtime.strict.decoded(runtime.question_reference_bytes(self.controls[str(paths[1])]))
        intent=runtime.strict.decoded(runtime.question_reference_bytes(self.controls[str(paths[2])]))
        broker=runtime.strict.decoded(runtime.question_reference_bytes(self.controls[str(paths[3])]))
        contract={'job':'root','agent_path':self.path,'run_name':row['run_id'],'broker_script':dispatch['broker_script'],
                  'capability_sha256':runtime.hashed(self.capability),'request_sha256':broker['request_sha256'],'spawns':{}}
        require(dispatch['root_path']==self.path and dispatch['coordinator_id']==owner.value['parent_native_id']
                and broker['capability_sha256']==contract['capability_sha256'],'Original dispatch/broker owner required')
        config=members['configuration'];provision={'run_id':config['run_id'],'configuration_sha256':cleanup.registry.sha(config),
            'jobs':{'root':intent['provision']}}
        self.proof=audit.audit(config,members,intent['intent'],{},self.parent,self.child,{},provision,
            self.folder/'registry',{self.path:contract},{self.path:audit.original_ledger(self.folder,'root')},
            {self.path:str(self.locator)},cid,commitment,turn_contracts={self.path:turn})
        self.fence()

    def fence(self):
        coordinator.source_fence(self.graph,[runtime.question_reference(Path(__file__).resolve())])
        for ref in [self.prepared_reference,self.binding_reference,self.failure_reference,*self.controls.values()]:
            runtime.question_verify_reference(ref)
        current,pin=self.owner.parent();require(pin==self.parent_pin,'Original parent inode changed')
        self.latest_parent=parent_guard.parent_extension_fence(self.parent,current,self.latest_parent)
        require(sources.capture.native_capture(self.locator,self.child_pin)[0]==self.child,
                'Original completed product source changed')
        state,members=runtime.declared_runtime(self.folder,self.capability)
        require(encoded(cleanup.immutable_job_fields(state))==encoded(self.jobs)
                and encoded((state['started_at'],state['deadline']))==encoded(self.clock)
                and encoded(members)==encoded(self.registry)
                and cleanup.registry_snapshot_fingerprint(cleanup.membership.reservation_prefix(self.folder/'registry'))
                    ==self.registry_pin,'Original SDK ownership/clock/registry changed')
        return state

    def verify(self,purpose,proof):
        state=self.fence();require(purpose=='grade_original_stopped_product','Only supplementary original stopped grading')
        ref=proof['stopped_snapshot_reference'];snap=runtime.strict.decoded(runtime.question_reference_bytes(ref))
        require(Path(ref['path']).parent==self.folder/'events' and snap.get('op')=='stopped_snapshot'
                and snap.get('job')=='root' and snap.get('scope_error') is None
                and snap.get('container_id')==state['jobs']['root']['container_id']
                and state['jobs']['root']['status']=='stopped','Original scoped stopped product required')
        contract,private=grading.selected_contract('B01',None)
        require(encoded(proof)==encoded({'row':self.row,'stopped_snapshot_reference':ref,
            'qualified_receipt_contract':contract,'private_grading_requested':private,
            'delivered_owner_selection':None,'original_deadline':self.clock[1]}),'Original frozen private grading contract required')
        require(runtime.inspect(self.folder,state,'root')['State']['Running'] is False,'Original SDK actually stopped required')
        self.fence()

    def execute(self):
        global _ctx
        require(_ctx is None,'Original post-failure rescue cannot restart');_ctx=self
        out=self.folder/'post-failure-rescue';out.mkdir()
        (out/'coordinator.jsonl').write_bytes(self.parent);(out/'product.jsonl').write_bytes(self.child)
        record={'original_row':self.row,'evaluation_status':'original_closure_failure',
                'original_failure_reference':self.failure_reference,'software_pass_supplementary':None,
                'usage':self.proof['usage'],'whole_comparison_qualified':False,'model_pilot_admitted':False,
                'model_retry_count':0,'owned_cleanup_verified':False,'first_error':None}
        runtime.atomic_json(out/'native-audit.json',self.proof,exclusive=True)
        runtime.atomic_json(out/'intent.json',record,exclusive=True)
        try:
            with runtime.lock(self.folder,'root'):
                self.fence();snap=runtime.snapshot(self.folder,'root',cleanup=True);self.fence()
            events=[p for p in (self.folder/'events').glob('*.json')
                    if runtime.strict.decoded(p.read_bytes()).get('export')==snap['export']]
            require(len(events)==1,'One original stopped product event required')
            graded=grading.grade(self.row,runtime.question_reference(events[0]),None,
                coordinator_verifier=verify,verifier_contract=coordinator.callback_contract(verify))
            self.fence();record['grading']=graded
            receipt=parent_guard.verified_grading_result(self.folder,self.row,None,graded)
            record['software_pass_supplementary']=receipt['software_pass']
            record['grader_cleanup_verified']=receipt['grader_owned_cleanup_verified']
        except Exception as error:record['first_error']={'type':type(error).__name__,'message':str(error)}
        self.fence();clean=cleanup.fenced_cleanup(self.folder,self.fence,original_jobs=self.jobs);self.fence()
        record['owned_cleanup_verified']=clean['owned_cleanup_verified'] and record.get('grader_cleanup_verified',False)
        record['product_owned_cleanup_verified']=clean['owned_cleanup_verified'];record['cleanup']=clean
        record['finished_at']=time.time()
        original=runtime.strict.decoded(runtime.question_reference_bytes(self.prepared_reference))
        record['whole_failed_attempt_observed_seconds']=record['finished_at']-original['preparation_started_at']
        runtime.atomic_json(out/'outcome.json',record,exclusive=True)
        return {'evaluation_status':record['evaluation_status'],'software_pass_supplementary':record['software_pass_supplementary'],
                'owned_cleanup_verified':record['owned_cleanup_verified'],'first_error':record['first_error'],
                'outcome_reference':runtime.question_reference(out/'outcome.json'),'model_pilot_admitted':False}


def verify(purpose,proof):
    require(_ctx is not None,'Original trusted ROOT rescue context required');return _ctx.verify(purpose,proof)
