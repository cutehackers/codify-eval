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

import improvement_optional_runtime_v3 as runtime


class RuntimeControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name).resolve();(self.folder/'events').mkdir()
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
            with patch.object(runtime,'engine_inspect',return_value=type('Result',(),{'stdout':json.dumps([self.info(job)])})()):
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
            with patch.object(runtime,'engine_inspect',return_value=type('Result',(),{'stdout':json.dumps([info])})()):
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

    def test_pending_create_cannot_be_marked_removed_then_orphaned(self):
        state=copy.deepcopy(self.state);state['phase']='preparing';state['jobs']={}
        runtime.save(self.folder,state);(self.folder/'root/repo').mkdir(parents=True)
        entered=threading.Event();release=threading.Event();created=[False]
        class Result:
            def __init__(self,returncode=0,stdout='',stderr=''):
                self.returncode=returncode;self.stdout=stdout;self.stderr=stderr
        def call(state,args,cleanup=False,**kwargs):
            if args[0]=='create':
                entered.set();self.assertTrue(release.wait(2));created[0]=True;return Result()
            if args[0]=='inspect':
                if not created[0]:return Result(1,stderr='No such object: owned')
                info=self.info();info['State']['Running']=False;return Result(stdout=json.dumps([info]))
            if args[0]=='rm':created[0]=False;return Result()
            raise AssertionError(args)
        def provision():
            try:runtime.provision(self.folder,'root','public task')
            except ValueError:return 'start refused after closing'
            raise AssertionError('Closing runtime unexpectedly started')
        with patch.object(runtime,'engine_inspect',side_effect=lambda folder,state,job,target,cleanup=False,check=True:call(state,['inspect',target],cleanup)),patch.object(runtime,'call',side_effect=call),patch.object(runtime,'snapshot',return_value={}),patch.object(runtime,'archive_tmp'):
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                provision_future=pool.submit(provision);self.assertTrue(entered.wait(2))
                cleanup_future=pool.submit(runtime.cleanup,self.folder)
                expires=time.monotonic()+2
                while runtime.load(self.folder)['phase']!='closing' and time.monotonic()<expires:time.sleep(0.005)
                self.assertEqual(runtime.load(self.folder)['phase'],'closing')
                self.assertFalse(cleanup_future.done())
                release.set();self.assertEqual(provision_future.result(3),'start refused after closing')
                cleaned=cleanup_future.result(3)
        self.assertFalse(created[0]);self.assertEqual(cleaned['jobs']['root']['status'],'removed')
        self.assertEqual(cleaned['phase'],'closed_docker_only')

    def test_first_error_not_overwritten(self):
        runtime.failure(self.folder,RuntimeError('original'))
        runtime.failure(self.folder,ValueError('later'))
        self.assertEqual(runtime.load(self.folder)['first_error']['message'],'original')

    def test_invalid_seconds_and_unknown_job_denied(self):
        for seconds in (True,0,121):
            with self.assertRaises(ValueError):self.command(seconds=seconds)
        with self.assertRaises(ValueError):runtime.command(self.folder,'other','cap','echo')

    def capture(self, data, code=0, stderr=b'', complete=True):
        import hashlib
        def execute(folder, job, number, args, seconds):
            raw={};directory=Path(folder)/'commands';directory.mkdir()
            for name,value in [('stdout',data),('stderr',stderr)]:
                p=directory/(job+'-00000.'+name);p.write_bytes(value)
                raw[name]={'path':str(p),'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()}
            return {'exit_code':code,'stdout':data.decode(errors='replace'),'stderr':stderr.decode(errors='replace'),
                    'output_complete':complete,'raw_output':raw}
        return patch.object(runtime,'bounded_exec',side_effect=execute)

    def test_full_engine_info_original_bytes_preserved(self):
        data=(json.dumps([self.info()],indent=2)+'\n').encode()
        with self.capture(data):self.assertEqual(runtime.inspect(self.folder,self.state,'root')['Id'],'root-id')
        receipts=list((self.folder/'engine-inspections').glob('*/receipt.json'));self.assertEqual(len(receipts),1)
        receipt=json.loads(receipts[0].read_bytes());stdout=Path(receipt['result']['raw_output']['stdout']['path'])
        self.assertEqual(stdout.read_bytes(),data);self.assertEqual(runtime.load(self.folder)['events'],1)

    def test_rejected_identity_original_receipt_retained(self):
        info=self.info();info['Id']='foreign';data=json.dumps([info]).encode()
        with self.capture(data):
            with self.assertRaises(ValueError):runtime.inspect(self.folder,self.state,'root')
        self.assertEqual(len(list((self.folder/'engine-inspections').glob('*/receipt.json'))),1)

    def test_absence_raw_stdout_stderr_retained(self):
        with self.capture(b'[]\n',1,b'Error: No such object: root-id\n'):
            value=runtime.engine_inspect(self.folder,self.state,'root','root-id',cleanup=True,check=False)
        self.assertEqual(value.returncode,1);self.assertEqual(value.stdout,'[]\n');self.assertIn('No such object:',value.stderr)

    def test_incomplete_invalid_utf8_and_duplicate_json_fail_after_preservation(self):
        for data,complete in [(b'[partial',False),(b'\xff',True),(b'[{"Id":"one","Id":"two"}]',True)]:
            with self.capture(data,complete=complete):
                with self.assertRaises(ValueError):runtime.inspect(self.folder,self.state,'root')
        self.assertEqual(len(list((self.folder/'engine-inspections').glob('*/receipt.json'))),3)

    def test_foreign_target_denied_before_allocation(self):
        with patch.object(runtime,'bounded_exec') as execute:
            with self.assertRaises(ValueError):runtime.engine_inspect(self.folder,self.state,'root','foreign')
            execute.assert_not_called()
        self.assertFalse((self.folder/'engine-inspections').exists())

    def test_inspect_original_deadline_overrun_cannot_pass(self):
        deadline=self.state['deadline'];data=json.dumps([self.info()]).encode()
        with self.capture(data),patch.object(runtime.time,'time',side_effect=[deadline-1,deadline-1,deadline-1,deadline+1,deadline+1]):
            with self.assertRaises(ValueError):runtime.inspect(self.folder,self.state,'root')
        self.assertEqual(len(list((self.folder/'engine-inspections').glob('*/receipt.json'))),1)


if __name__=='__main__':unittest.main()
