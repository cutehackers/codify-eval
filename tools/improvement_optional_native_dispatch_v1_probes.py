"""Prospective dispatch filesystem controls. No native or Docker execution."""
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import improvement_optional_native_dispatch_v1 as dispatch
import improvement_optional_routes_v3 as routes


class DispatchControls(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();self.folder=self.root/'runtime/probe';self.folder.mkdir(parents=True)
        self.root_patch=patch.object(dispatch,'ROOT',self.root);self.root_patch.start();self.addCleanup(self.root_patch.stop)
        self.role_patch=patch.object(dispatch.original_broker.runtime,'role',return_value={});self.role_patch.start();self.addCleanup(self.role_patch.stop)
        tree={'.':{'kind':'directory','mode':493},**{f'{n}.dart':{'kind':'file','mode':420,'sha256':'a'*64} for n in range(3)}}
        self.state=dispatch.registry.create(self.folder/'registry','probe','O01','A',time.time()-1,tree,[f'{n}.dart' for n in range(3)])
        self.cap='a'*48;self.control('root')

    def control(self,job):
        directory=self.folder/'broker'/job;directory.mkdir(parents=True)
        dispatch.atomic_json(directory/'control.json',{'job':job,'configuration_sha256':self.state['configuration_sha256'],
            'request_sha256':hashlib.sha256(b'public task').hexdigest(),'capability_sha256':hashlib.sha256(self.cap.encode()).hexdigest()},exclusive=True)

    def create(self):return dispatch.create(self.folder,'/root/product','coordinator',self.cap)

    def test_root_intent_precedes_allocation_and_matches_provision(self):
        row=self.create();self.assertEqual(row['intent']['job'],'root');self.assertEqual(row['intent']['agent_path'],'/root/product')
        self.assertEqual(row['provision']['intent_sha256'],dispatch.registry.sha(row['intent']))
        self.assertTrue((self.folder/'native-dispatch/intents/root.json').exists());self.assertFalse(row['native_qualified'])

    def test_exact_literal_bootstrap_read_command_for_each_role(self):
        for job in ('root','worker1','worker2'):
            text=dispatch.bootstrap('probe',job,self.cap)
            wrapper=text.split('exactly:\n',1)[1].split('\nRead its entire',1)[0]
            command=routes.literal_command(wrapper)
            self.assertEqual(command,dispatch.command('probe',job,self.cap,'read'))
            self.assertNotIn('gpt-6-sol',text)

    def test_reserved_workers_have_original_snapshot_goal_scope_intent(self):
        self.create()
        for i in range(2):
            self.state=dispatch.registry.reserve_worker(self.folder/'registry','public goal',[f'{i}.dart'],self.state['configuration']['initial_tree'])
            job=f'worker{i+1}';self.control(job);row=dispatch.prepare(self.folder,job,self.cap)
            self.assertEqual(row['intent']['agent_path'],'/root/product/'+job)
            self.assertEqual(row['intent']['reservation_worker_sha256'],dispatch.registry.sha({key:self.state['workers'][job][key] for key in ('slot','goal','scope','mode','snapshot','snapshot_sha256')}))
            self.assertIn('Never spawn',row['native_bootstrap'])

    def test_no_replacement_or_unreserved_worker(self):
        self.create()
        with self.assertRaises(FileExistsError):dispatch.prepare(self.folder,'root',self.cap)
        with self.assertRaises(ValueError):dispatch.prepare(self.folder,'worker1',self.cap)

    def test_original_config_schema_and_false_qualifications_required(self):
        self.create();p=self.folder/'native-dispatch/configuration.json';value=json.loads(p.read_bytes())
        for field,changed in [('configuration_sha256','wrong'),('native_qualified',True),('unknown',1),('root_path','/root/../other')]:
            data=dict(value,**{field:changed});p.write_text(json.dumps(data))
            with self.assertRaises(ValueError):dispatch.prepare(self.folder,'root',self.cap)
        p.write_text(json.dumps(value))

    def test_expired_original_clock_is_not_reset(self):
        self.create()
        with patch.object(dispatch.time,'time',return_value=self.state['configuration']['deadline']):
            with self.assertRaises(ValueError):dispatch.prepare(self.folder,'root',self.cap)

    def test_wrong_capability_or_closed_runtime_cannot_prepare(self):
        self.create()
        with self.assertRaises(ValueError):dispatch.prepare(self.folder,'root','b'*48)
        with patch.object(dispatch.original_broker.runtime,'role',side_effect=ValueError('closed')):
            with self.assertRaises(ValueError):dispatch.prepare(self.folder,'root',self.cap)

    def test_nonliteral_namespace_and_role_denied(self):
        for run,job,cap in [('probe;echo bad','root',self.cap),('probe','worker3',self.cap),('probe','root','x'*48)]:
            with self.assertRaises(ValueError):dispatch.command(run,job,cap,'read')


if __name__=='__main__':unittest.main()
