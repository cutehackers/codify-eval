"""ROOT-owned original prebirth observer process lifecycle.

No actor allocation, reply, cleanup or comparison admission. The caller's ROOT
identity is an external trust requirement. A pinned manifest transfers control
references to a fresh ROOT-owned Python process, never to a product actor.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import improvement_baseline_startup_driver_v3 as driver

runtime=driver.runtime
coordinator=driver.coordinator
require=driver.require
encoded=driver.encoded
ROOT=driver.ROOT


def process_fence(entities):
    coordinator.source_fence(entities,[runtime.question_reference(Path(__file__).resolve())])


def private_result(reference,folder):
    path=runtime.question_verify_reference(reference)
    require(path==folder/'root-driver/private-create-result.json'
            and reference['entity']['mode']==0o600,'Original ROOT-only private result required')
    value=runtime.strict.decoded(runtime.question_reference_bytes(reference))
    require(type(value) is dict and set(value)=={'folder','run_id','root_capability'}
            and value['folder']==str(folder),'Exact private original SDK result required')
    return value


class ObserverProcess:
    def __init__(self,binding_reference,private_result_reference,owner,*,frozen_driver_sources,frozen_process_sources):
        process_fence(frozen_process_sources);driver.driver_fence(frozen_driver_sources)
        owner.parent()
        binding=runtime.strict.decoded(runtime.question_reference_bytes(binding_reference))
        coordinator.inputs.row_valid(binding['row'])
        self.folder=ROOT/'runtime'/binding['row']['run_id']
        require(binding_reference['path']==str(self.folder/'root-startup-binding/binding.json'),
                'Original observer binding namespace required')
        result=private_result(private_result_reference,self.folder)
        require(result['run_id']==binding['runtime_run_id']
                and runtime.hashed(result['root_capability'])==binding['capability_sha256'],
                'Original private capability/runtime identity required')
        self.value=copy.deepcopy({'schema_version':1,'binding_reference':binding_reference,
            'private_result_reference':private_result_reference,'anchor_reference':owner.anchor_reference,
            'trusted_root_native_id':owner.value['parent_native_id'],'driver_sources':frozen_driver_sources,
            'process_sources':frozen_process_sources,'row':binding['row'],'actual_native_authenticated':False,
            'model_pilot_admitted':False})
        self.owner=owner;self.proc=None;self.directory=self.folder/'root-driver/observer-process'
        self.manifest_reference=None;self.stdout=None;self.stderr=None
        self.commitment=encoded(self.value);self.completion_reference=None
        self.launch_preparation_attempted=False

    def fence(self):
        require(encoded(self.value)==self.commitment,'Original observer process inputs changed')
        process_fence(self.value['process_sources']);driver.driver_fence(self.value['driver_sources'])
        self.owner.parent()
        runtime.question_verify_reference(self.value['binding_reference'])
        private_result(self.value['private_result_reference'],self.folder)
        if self.manifest_reference is not None:runtime.question_verify_reference(self.manifest_reference)

    def start(self):
        self.fence();require(self.proc is None,'Original observer cannot restart')
        require(not (self.folder/'native-observer').exists(),'Observer must precede all readiness/sample files')
        self.directory.mkdir()
        path=self.directory/'manifest.json';runtime.atomic_json(path,self.value,exclusive=True)
        self.manifest_reference=runtime.question_reference(path)
        self.stdout=(self.directory/'stdout.log').open('xb');self.stderr=(self.directory/'stderr.log').open('xb')
        try:
            self.proc=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--child',
                str(path),self.manifest_reference['entity']['sha256']],cwd=ROOT,
                stdin=subprocess.DEVNULL,stdout=self.stdout,stderr=self.stderr,
                env={**os.environ,'PYTHONPATH':str(ROOT/'tools'),'PYTHONDONTWRITEBYTECODE':'1'})
        except BaseException:
            self.stdout.close();self.stderr.close();raise
        runtime.atomic_json(self.directory/'launch.json',{'pid':self.proc.pid,
            'manifest_reference':self.manifest_reference,'observer_restarts':0,'actor_control':False,
            'model_pilot_admitted':False},exclusive=True)
        return self.proc.pid

    def await_ready(self,seconds=30):
        require(type(seconds) in (int,float) and 0<seconds<=30,'Bounded original readiness wait required')
        require(self.proc is not None,'Original observer process not started')
        end=time.monotonic()+seconds
        while True:
            code=self.proc.poll()
            require(code is None,'Original observer terminated before confirmed readiness')
            out=self.folder/'native-observer'
            require(not (out/'failure.json').exists() and not (out/'terminal.json').exists(),
                    'Original observer failed or terminated before readiness')
            ready=out/'ready.json';samples=out/'samples.jsonl'
            if ready.exists() and samples.exists():
                # Samples append while the observer is live. Read one original
                # inode snapshot rather than applying an immutable-file reader.
                raw,entity=driver.controller.watch.native_capture(samples)
                newline=raw.find(b'\n')
                if newline>=0:
                    first=runtime.strict.decoded(raw[:newline])
                    value=runtime.strict.decoded(runtime.question_reference_bytes(runtime.question_reference(ready)))
                    binding=runtime.strict.decoded(runtime.question_reference_bytes(self.value['binding_reference']))
                    clock={'worker_cap':self.value['row']['worker_cap'],
                           'started_at':binding['original_started_at'],'deadline':binding['original_deadline']}
                    driver.controller.watch.authority_snapshot(first['authority'],self.value['row']['actor_path'],
                        self.value['trusted_root_native_id'],clock)
                    require(type(first['sample_number']) is int and first['sample_number']==0
                        and first['reserved_jobs']==['root'] and first['members']==[]
                        and first['authority']['root_native_id'] is None
                        and first['authority']['turn_ids']==[] and first['authority']['expected_turns']==1
                        and first['authority']['phase']=='awaiting_semantic_review'
                        and first['root_native_id'] is None and first['pending_native_jobs']==['root']
                        and first['failure_diagnostics']==[] and first['deadline_reached'] is False,
                        'One successful original prebirth observer sample required')
                    require(value['root_path']==self.value['row']['actor_path']
                        and value['parent_id']==self.value['trusted_root_native_id']
                        and value['root_native_id'] is None and type(value['observer_restarts']) is int
                        and value['observer_restarts']==0 and value['actor_control'] is False
                        and encoded(value['original_started_at'])==encoded(clock['started_at'])
                        and encoded(value['deadline'])==encoded(clock['deadline'])
                        and encoded(value['authority_callback_reference'])==encoded(runtime.question_reference(Path(driver.controller.__file__).resolve()))
                        and value['native_qualified'] is False
                        and clock['started_at']<=value['started_at']<=first['started_at']
                        <=first['completed_at']<=time.time()<clock['deadline']
                        and first['completed_at']-value['started_at']<=30,
                        'Original prebirth observer readiness required')
                    self.fence()
                    current,_=driver.controller.watch.native_capture(samples,entity)
                    require(current.startswith(raw),'Original observer samples rewritten or truncated')
                    complete=current[:current.rfind(b'\n')+1]
                    latest=runtime.strict.decoded(complete.splitlines()[-1])
                    now=time.time()
                    require(type(latest['sample_number']) is int and latest['sample_number']>=0
                            and type(latest['completed_at']) in (int,float)
                            and 0<=now-latest['completed_at']<=30,
                            'Original observer latest completed sample is stale or future-dated')
                    driver.controller.watch.authority_snapshot(latest['authority'],self.value['row']['actor_path'],
                        self.value['trusted_root_native_id'],clock)
                    require(latest['root_native_id'] is None and latest['members']==[]
                            and latest['reserved_jobs']==['root'] and latest['pending_native_jobs']==['root']
                            and latest['failure_diagnostics']==[] and latest['deadline_reached'] is False,
                            'Original observer must remain live and prebirth through readiness')
                    require(self.proc.poll() is None and not (out/'terminal.json').exists()
                            and not (out/'failure.json').exists(),
                            'Observer ceased during readiness validation')
                    return runtime.question_reference(ready)
            require(time.monotonic()<end,'Original readiness wait expired; retain handle, do not restart')
            time.sleep(.1)

    def prepare_launch(self,prepared_reference):
        """One original launch intent while this original observer remains live.

        Actual native API dispatch stays with ROOT. Failure after intent creation
        preserves the intent and denies another attempt; this never retries a
        model allocation or asserts comparison admission.
        """
        require(not self.launch_preparation_attempted,'Original launch preparation cannot be retried')
        prepared_reference=copy.deepcopy(prepared_reference)
        self.fence()
        require(prepared_reference['path']==str(self.folder/'coordinator/prepared.json'),
                'Same original prepared runtime required for observer launch')
        prepared=runtime.strict.decoded(runtime.question_reference_bytes(prepared_reference))
        binding=runtime.strict.decoded(runtime.question_reference_bytes(self.value['binding_reference']))
        require(encoded(prepared['row'])==encoded(self.value['row'])
                and encoded(prepared['configuration_reference'])==encoded(binding['configuration_reference'])
                and encoded(prepared['original_started_at'])==encoded(binding['original_started_at'])
                and encoded(prepared['original_deadline'])==encoded(binding['original_deadline']),
                'Original observer preparation/configuration/clock required')
        ready=self.await_ready(30)
        result=private_result(self.value['private_result_reference'],self.folder)
        self.launch_preparation_attempted=True
        launched=driver.prepare_launch(prepared_reference,ready,result['root_capability'],self.owner,
                                      frozen_driver_sources=self.value['driver_sources'])
        # The coordinator's callbacks and SDK fences take time. Recheck current
        # observer cadence after those callbacks, before returning any arguments.
        current_ready=self.await_ready(1)
        require(encoded(current_ready)==encoded(ready),'Original prebirth readiness reference changed during launch')
        return launched

    def request_stop(self):
        require(self.proc is not None,'Original observer not started')
        self.fence()
        if self.proc.poll() is not None:return self.proc.returncode
        path=self.folder/'native-observer/stop.json'
        require(path.parent.is_dir(),'Original observer has not reached owned readiness directory')
        runtime.atomic_json(path,{'reason':'coordinator_stop','root_path':self.value['row']['actor_path'],
            'parent_id':self.value['trusted_root_native_id']},exclusive=True)
        return None

    def wait(self,seconds=30):
        require(self.proc is not None,'Original observer not started')
        require(type(seconds) in (int,float) and 0<seconds<=30,'Bounded original process wait required')
        if self.completion_reference is not None:
            value=runtime.strict.decoded(runtime.question_reference_bytes(self.completion_reference))
            if value['terminal_reference'] is not None:runtime.question_verify_reference(value['terminal_reference'])
            return value
        try:code=self.proc.wait(timeout=seconds)
        except subprocess.TimeoutExpired:return {'completed':False,'pid':self.proc.pid,'restart_permitted':False}
        finally:
            if self.proc.poll() is not None:self.stdout.close();self.stderr.close()
        terminal=self.folder/'native-observer/terminal.json'
        value={'completed':True,'pid':self.proc.pid,'exit_code':code,
            'terminal_reference':runtime.question_reference(terminal) if terminal.exists() else None,
            'actor_control':False,'cleanup_authorized':False,'model_pilot_admitted':False}
        path=self.directory/'completion.json';runtime.atomic_json(path,value,exclusive=True)
        self.completion_reference=runtime.question_reference(path)
        return value


def child_main(path,expected_sha256):
    path=Path(path);reference=runtime.question_reference(path)
    require(reference['entity']['sha256']==expected_sha256,'Original process manifest changed before child start')
    value=runtime.strict.decoded(runtime.question_reference_bytes(reference))
    require(type(value) is dict and set(value)=={'schema_version','binding_reference','private_result_reference',
        'anchor_reference','trusted_root_native_id','driver_sources','process_sources','row',
        'actual_native_authenticated','model_pilot_admitted'} and type(value['schema_version']) is int
        and value['schema_version']==1 and value['actual_native_authenticated'] is False
        and value['model_pilot_admitted'] is False,'Exact original ROOT observer manifest required')
    coordinator.inputs.row_valid(value['row']);folder=ROOT/'runtime'/value['row']['run_id']
    require(path==folder/'root-driver/observer-process/manifest.json','Exact original process namespace required')
    process_fence(value['process_sources']);driver.driver_fence(value['driver_sources'])
    owner=driver.controller.source.RootSource(value['anchor_reference'],trusted_root_native_id=value['trusted_root_native_id'])
    result=private_result(value['private_result_reference'],folder)
    driver.supervise_original(value['binding_reference'],result['root_capability'],owner,
                              frozen_driver_sources=value['driver_sources'])
    process_fence(value['process_sources']);runtime.question_verify_reference(reference)
    terminal=runtime.strict.decoded((folder/'native-observer/terminal.json').read_bytes())
    require(terminal['reason'] in ('coordinator_stop','original_deadline','native_error_diagnostic'),
            'Original observer failed; terminal evidence preserved')


if __name__=='__main__':
    require(len(sys.argv)==4 and sys.argv[1]=='--child','ROOT-owned child entry only')
    child_main(sys.argv[2],sys.argv[3])
