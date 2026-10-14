"""ROOT-owned first native row controller. Native APIs stay with the calling ROOT.

Persistent process retains its original observer handle and startup context.
No actor is started by this file. The caller dispatches the returned frozen
bootstrap once, obtains the final unfiltered native inventory, then requests
finish. Product actors never receive this plan, anchor, or grading sources.
"""
import hashlib
import json
from pathlib import Path
import sys

import improvement_baseline_startup_driver_v5 as driver
import improvement_baseline_observer_process_v6 as observer
import improvement_baseline_root_terminal_controller_v5 as terminal
import improvement_baseline_startup_cleanup_v3 as startup_cleanup

runtime=driver.runtime
coordinator=driver.coordinator
ROOT=driver.ROOT
require=runtime.require
encoded=runtime.encoded
TRUSTED_ROOT_NATIVE_ID='01a122a7-1f52-7810-8588-f0a7a8732fa1'
PLAN_KEYS={'schema_version','row','anchor_reference','source_entities','driver_sources',
           'process_sources','terminal_sources','cleanup_sources','boundary_review_reference'}


class Run:
    def __init__(self,plan_reference):
        self.plan_reference=plan_reference
        self.plan=runtime.strict.decoded(runtime.question_reference_bytes(plan_reference))
        require(type(self.plan) is dict and set(self.plan)==PLAN_KEYS
                and type(self.plan['schema_version']) is int and self.plan['schema_version']==1,
                'Exact original ROOT run plan required')
        row=self.plan['row'];coordinator.inputs.row_valid(row)
        require(row['case_id']=='B01' and row['condition']=='A' and type(row['worker_cap']) is int
                and row['worker_cap']==0,'First actual startup qualification is B01/A/cap0 only')
        self.row=row;self.folder=ROOT/'runtime'/row['run_id']
        self.owner=driver.controller.source.RootSource(self.plan['anchor_reference'],
            trusted_root_native_id=TRUSTED_ROOT_NATIVE_ID)
        self.prepared=None;self.watcher=None;self.started=False;self.finished=False;self.launch_returned=False
        self.fence()
        review=runtime.strict.decoded(runtime.question_reference_bytes(self.plan['boundary_review_reference']))
        require(self.plan['boundary_review_reference']['path']==str(ROOT/'results/improvement-v1/baseline-root-terminal-controller-v5-independent-static-review-v1.json'),
                'Original independently persisted boundary review required')
        require(review['verdict']=='pass' and review.get('issues')==[], 'Qualified underlying boundary review required')
        required=coordinator.source_closure([runtime.question_reference(Path(terminal.__file__).resolve()),
            runtime.question_reference(Path(observer.__file__).resolve())])
        require(type(review.get('source_entities')) is dict and bool(review['source_entities'])
                and encoded(review['source_entities'])==encoded(required),
                'Exact nonempty independently reviewed terminal/observer source coverage required')
        for name,entity in review['source_entities'].items():
            require(encoded(self.plan['source_entities'].get(name))==encoded(entity),
                    'Current runner source differs from independently reviewed boundary')

    def fence(self):
        runtime.question_verify_reference(self.plan_reference)
        refs={'source_entities':Path(__file__).resolve(),'driver_sources':Path(driver.__file__).resolve(),
              'process_sources':Path(observer.__file__).resolve(),'terminal_sources':Path(terminal.__file__).resolve(),
              'cleanup_sources':Path(startup_cleanup.__file__).resolve()}
        for key,path in refs.items():
            coordinator.source_fence(self.plan[key],[runtime.question_reference(path)])
        runtime.question_verify_reference(self.plan['boundary_review_reference'])
        self.owner.parent()

    def start(self):
        require(not self.started and not self.finished,'Original SDK startup cannot restart')
        self.started=True;self.fence()
        self.prepared=driver.prepare_startup(self.row,self.owner,None,None,
            frozen_driver_sources=self.plan['driver_sources'])
        private=runtime.question_reference(self.folder/'root-driver/private-create-result.json')
        self.watcher=observer.ObserverProcess(self.prepared['binding_reference'],private,self.owner,
            frozen_driver_sources=self.plan['driver_sources'],frozen_process_sources=self.plan['process_sources'])
        self.watcher.start()
        return self.prepare_launch()

    def prepare_launch(self):
        require(self.started and not self.finished and not self.launch_returned and self.watcher is not None,
                'Original preparation handle required; launch cannot repeat')
        self.fence()
        try:launch=self.watcher.prepare_launch(self.prepared['prepared_reference'])
        except ValueError as error:
            if str(error)=='Original readiness wait expired; retain handle, do not restart' and not self.watcher.launch_preparation_attempted:
                return {'phase':'observer_readiness_pending','observer_pid':self.watcher.proc.pid,
                        'restart_permitted':False}
            raise
        self.launch_returned=True
        self.fence()
        return {'phase':'dispatch_original_actor_once','row':self.row,
                'arguments':launch['arguments'],'launch_intent_reference':launch['intent_reference'],
                'actual_model_dispatched_by_runner':False,'model_pilot_admitted':False}

    def status(self):
        require(self.watcher is not None,'Original observer does not exist')
        self.fence();self.watcher.fence()
        path=self.folder/'native-observer/samples.jsonl'
        raw,_=observer.driver.controller.watch.native_capture(path)
        complete=driver.controller.source.complete_prefix(raw)
        sample=runtime.strict.decoded(complete.splitlines()[-1])
        return {'phase':'observing_original_actor','observer_pid':self.watcher.proc.pid,
                'observer_exit_code':self.watcher.proc.poll(),
                'sample_number':sample['sample_number'],'completed_at':sample['completed_at'],
                'root_native_id':sample['root_native_id'],
                'normal_completions_observed':sample['all_registered_normal_completions_observed'],
                'pending_jobs':sample['pending_native_jobs'],
                'failure_diagnostics_observed':bool(sample['failure_diagnostics'])}

    def stop_observer(self,*,normal_required):
        require(self.watcher is not None and self.watcher.proc is not None,'Original observer handle required')
        if self.watcher.proc.poll() is None:self.watcher.request_stop()
        completion=self.watcher.wait(30)
        require(completion['completed'] is True, 'Original observer stop remains incomplete')
        if normal_required:
            require(completion['exit_code']==0, 'Original normal observer stop unsuccessful')
            record=runtime.strict.decoded(runtime.question_reference_bytes(completion['terminal_reference']))
            require(record['reason']=='coordinator_stop','Original observer ended without coordinator stop')
            require(record['normal_completions_observed'] is True,
                    'Original observer has not established genuine model terminal completion')
        return completion

    def finish(self):
        require(self.started and not self.finished and self.prepared is not None,'One original normal close required')
        self.fence();status=self.status()
        require(status['normal_completions_observed'] is True and status['observer_exit_code'] is None
                and not status['failure_diagnostics_observed'], 'Live original normal terminal sample required')
        completion=self.stop_observer(normal_required=True)
        self.finished=True
        locator=driver.controller.watch.find_session(self.row['actor_path'])
        context=terminal.TerminalController(driver.controller._context,
            self.prepared['prepared_reference'],locator,self.plan['terminal_sources'])
        terminal.configure(context)
        inputs=context.seal()
        # Same ROOT functions.exec call: no intermediate native delivery,
        # inventory or new control call between seal and normal.close.
        result=terminal.normal.close(self.row,self.prepared['prepared_reference'],inputs,
            self.owner.source,{self.row['actor_path']:str(locator)},None,
            root_capability=self.prepared['root_capability'],validated_authority=terminal.terminal_authority,
            authority_contract=coordinator.callback_contract(terminal.terminal_authority),
            coordinator_verifier=terminal.verify,verifier_contract=coordinator.callback_contract(terminal.verify))
        self.fence()
        result['original_observer_completion']=completion
        path=self.folder/'root-driver/runner-outcome.json'
        runtime.atomic_json(path,result,exclusive=True)
        return {'phase':result['status'],'software_pass':result['software_pass'],
                'owned_cleanup_verified':result['owned_cleanup_verified'],
                'whole_observed_seconds':result['whole_observed_seconds'],
                'all_member_usage_observed':result.get('all_member_usage_observed',False),
                'outcome_reference':runtime.question_reference(path),'model_pilot_admitted':False}

    def abort_actor_free(self):
        require(not self.finished,'Original closure cannot restart')
        self.fence()
        # This is denied by original parent-source inspection after *any* exact
        # native dispatch, even with no ACK. Never use it for actor failures.
        startup_cleanup.no_product_spawn(self.owner,self.row['actor_path'])
        if self.watcher is not None and self.watcher.proc is not None:
            self.stop_observer(normal_required=False)
        state=runtime.load(self.folder)
        directory=ROOT/'results/improvement-v1/root-runner-startup-preservation-v2'/self.row['run_id']
        directory.mkdir(parents=True,exist_ok=False)
        snapshot=directory/'state.json';runtime.atomic_json(snapshot,state,exclusive=True)
        result=startup_cleanup.close(self.folder,self.row['actor_path'],self.owner,
            runtime.question_reference(snapshot),runtime.question_reference(self.folder/'configuration.json'),
            frozen_sources=self.plan['cleanup_sources'],observer=self.watcher)
        self.finished=True
        return {'phase':'actor_free_startup_cleanup','result':result}


def emit(value):
    sys.stdout.write(json.dumps(value,sort_keys=True,allow_nan=False)+'\n');sys.stdout.flush()


def serve(plan_reference):
    run=Run(plan_reference)
    try:
        emit(run.start())
        for line in sys.stdin:
            command=runtime.strict.decoded(line)
            require(type(command) is dict and set(command)=={'op'},'Exact ROOT control operation required')
            op=command['op']
            if op=='prepare_launch':emit(run.prepare_launch())
            elif op=='status':emit(run.status())
            elif op=='finish':emit(run.finish());return
            elif op=='abort_actor_free':emit(run.abort_actor_free());return
            else:raise ValueError('Unqualified ROOT control operation')
        raise ValueError('Original ROOT control input ended before qualified closure')
    except BaseException as error:
        directory=run.folder/'root-driver'
        if directory.is_dir():
            try:runtime.atomic_json(directory/'runner-error.json',{'error_type':type(error).__name__,
                'error_message':str(error),'original_actor_retry_permitted':False,
                'cleanup_required':True,'model_pilot_admitted':False},exclusive=True)
            except BaseException as preservation_error:
                try:emit({'phase':'error_preservation_unavailable','original_error_type':type(error).__name__,
                          'preservation_error_type':type(preservation_error).__name__})
                except BaseException:pass
        try:emit({'phase':'runner_error','error_type':type(error).__name__,
                  'error_message':str(error),'cleanup_required':True,'restart_permitted':False})
        except BaseException:pass
        raise


if __name__=='__main__':
    require(len(sys.argv)==4 and sys.argv[2]=='--execute-plan-sha256','Exact frozen ROOT plan execution required')
    reference=runtime.question_reference(Path(sys.argv[1]))
    require(reference['entity']['sha256']==sys.argv[3],'Original execution plan hash changed')
    serve(reference)
