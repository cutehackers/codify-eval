"""Pure lifecycle/locking controls. Docker qualification is separate."""
import concurrent.futures
import copy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import improvement_optional_runtime_v1 as runtime


class RuntimeControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);(self.folder/'events').mkdir()
        started=time.time();self.caps={j:j+'-cap' for j in ('root','worker1','worker2')}
        self.state={'run_id':'run','configuration_sha256':'configuration','started_at':started,
                    'deadline':started+1200,'phase':'running','events':0,'first_error':None,
                    'jobs':{j:{'container':j,'container_id':j+'-id','commands':0,'status':'running',
                               'capability_sha256':runtime.hashed(self.caps[j])} for j in self.caps}}
        runtime.save(self.folder,self.state)

    def info(self,job='root'):
        return {'Id':job+'-id','Image':runtime.IMAGE,
                'Config':{'Labels':{'codify.optional.run':'run','codify.optional.configuration':'configuration','codify.optional.job':job}},
                'HostConfig':{'NetworkMode':'none'},'State':{'Running':True},
                'Mounts':[{'Destination':'/work/repo','Type':'bind','Source':str(self.folder/job/'repo'),'RW':True},
                          {'Destination':'/eval-input','Type':'bind','Source':str(self.folder/job/'input'),'RW':False}]}

    def command(self,job='root',**kwargs):
        return runtime.command(self.folder,job,self.caps[job],'exit 7',**kwargs)

    def test_exact_owned_mounts_for_root_and_worker(self):
        for job in ('root','worker1'):
            with patch.object(runtime,'call',return_value=type('Result',(),{'stdout':json.dumps([self.info(job)])})()):
                self.assertEqual(runtime.inspect(self.folder,self.state,job)['Id'],job+'-id')

    def test_wrong_identity_labels_image_network_and_mounts_denied(self):
        variants=[]
        for key,value in [('Id','foreign'),('Image','other')]:
            info=self.info();info[key]=value;variants.append(info)
        info=self.info();info['Config']['Labels']['codify.optional.run']='foreign';variants.append(info)
        info=self.info();info['HostConfig']['NetworkMode']='bridge';variants.append(info)
        info=self.info();info['Mounts'][0]['RW']=False;variants.append(info)
        info=self.info();info['Mounts'][1]['RW']=True;variants.append(info)
        info=self.info();info['Mounts'][0]['Source']='other';variants.append(info)
        for info in variants:
            with patch.object(runtime,'call',return_value=type('Result',(),{'stdout':json.dumps([info])})()):
                with self.assertRaises(ValueError):runtime.inspect(self.folder,self.state,'root')

    def test_wrong_capability_denied_before_docker(self):
        with patch.object(runtime,'inspect') as inspect,patch.object(runtime,'bounded_exec') as execute:
            with self.assertRaises(ValueError):runtime.command(self.folder,'worker1',self.caps['root'],'echo bad')
            inspect.assert_not_called();execute.assert_not_called()

    def test_closed_and_expired_commands_denied_before_docker(self):
        for mutation in ('phase','deadline'):
            state=copy.deepcopy(self.state)
            if mutation=='phase':state['phase']='closing'
            else:state['deadline']=time.time()-1
            runtime.save(self.folder,state)
            with patch.object(runtime,'bounded_exec') as execute:
                with self.assertRaises(ValueError):self.command()
                execute.assert_not_called()

    def test_inner_failure_retained_and_no_silent_twenty_command_cap(self):
        state=copy.deepcopy(self.state);state['jobs']['root']['commands']=20;runtime.save(self.folder,state)
        with patch.object(runtime,'inspect',return_value=self.info()),patch.object(runtime,'bounded_exec',return_value={'exit_code':7,'stdout':'','stderr':'','output_complete':True}):
            value=self.command()
        self.assertEqual(value['exit_code'],7);self.assertEqual(value['number'],21)
        self.assertFalse(value['native_qualified']);self.assertFalse(value['scope_checked'])

    def test_separate_job_commands_overlap_without_state_lock_held(self):
        barrier=threading.Barrier(2);starts=[]
        def execute(folder,job,number,args,seconds):
            starts.append(time.monotonic());barrier.wait(timeout=2)
            # A state lock can be acquired while both executions are live.
            with runtime.lock(folder):self.assertEqual(runtime.load(folder)['events'],2)
            time.sleep(0.05)
            return {'exit_code':0,'stdout':'','stderr':'','output_complete':True}
        with patch.object(runtime,'inspect',return_value=self.info()),patch.object(runtime,'bounded_exec',side_effect=execute):
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                results=[pool.submit(self.command,j) for j in ('worker1','worker2')]
                for result in results:self.assertEqual(result.result(timeout=3)['exit_code'],0)
        self.assertLess(abs(starts[1]-starts[0]),0.1)
        self.assertEqual(runtime.load(self.folder)['events'],4)

    def test_same_job_commands_serialize(self):
        counts=[0,0];guard=threading.Lock()
        def execute(*args):
            with guard:counts[0]+=1;counts[1]=max(counts[1],counts[0])
            time.sleep(0.03)
            with guard:counts[0]-=1
            return {'exit_code':0,'stdout':'','stderr':'','output_complete':True}
        with patch.object(runtime,'inspect',return_value=self.info()),patch.object(runtime,'bounded_exec',side_effect=execute):
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                results=[pool.submit(self.command) for _ in range(2)]
                for result in results:result.result(timeout=3)
        self.assertEqual(counts[1],1)
        self.assertEqual(runtime.load(self.folder)['jobs']['root']['commands'],2)

    def test_first_error_not_overwritten(self):
        runtime.failure(self.folder,RuntimeError('original'))
        runtime.failure(self.folder,ValueError('later'))
        self.assertEqual(runtime.load(self.folder)['first_error']['message'],'original')

    def test_invalid_seconds_and_unknown_job_denied(self):
        for seconds in (True,0,121):
            with self.assertRaises(ValueError):self.command(seconds=seconds)
        with self.assertRaises(ValueError):runtime.command(self.folder,'other','cap','echo')


if __name__=='__main__':unittest.main()
