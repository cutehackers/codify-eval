"""Actor-free frontier adversarial controls. No model or Docker execution."""
import copy
import unittest
import contextlib
import json
from pathlib import Path
import tempfile
from unittest import mock

import improvement_baseline_question_quiescence_v1 as subject


class FrontierTests(unittest.TestCase):
    def fixture(self,case='B03'):
        row=next(r for r in subject.coordinator.inputs.sequence()
                 if r['case_id']==case and r['condition']=='A' and r['worker_cap']==0)
        prepared={'row':row,'original_started_at':100.0,'original_deadline':1300.0}
        state={'phase':'running','jobs':{'root':{'status':'running','capability_sha256':'original-cap'}},
               'started_at':100.0,'deadline':1300.0,'worker_cap':0}
        members={'workers':{},'active_leases':{}}
        control={'binding':{'run_id':row['run_id'],'case_id':case,'agent_path':row['actor_path'],
                            'parent_native_uuid':'original-parent','root_native_uuid':'original-child'},
                 'original_started_at':100.0,'original_deadline':1300.0,'worker_cap':0,
                 'root_capability_sha256':'original-cap'}
        return [row,prepared,state,members,control,[],'original-parent']

    def test_both_cases_running_and_previously_stopped(self):
        for case in ('B03','B04'):
            for status in ('running','stopped'):
                args=self.fixture(case);args[2]['jobs']['root']['status']=status
                result=subject.validate_frontier(*args)
                self.assertEqual(result,args[4]['binding'])
                result['run_id']='mutated-return'
                self.assertNotEqual(result,args[4]['binding'])

    def test_registration_model_namespace_and_cap_cannot_change(self):
        for key,value in [('case_id','B01'),('condition','C24'),('worker_cap',True),
                          ('worker_cap',2),('actor_path','/root/unregistered'),('run_id','replacement')]:
            with self.subTest(key=key,value=value):
                args=self.fixture();args[0][key]=value
                with self.assertRaises(ValueError):subject.validate_frontier(*args)

    def test_closed_or_paused_and_unsafe_job_statuses_denied(self):
        for phase in ('preparing','question_paused','failed','closed'):
            args=self.fixture();args[2]['phase']=phase
            with self.assertRaises(ValueError):subject.validate_frontier(*args)
        for status in ('removed','sealed_stopped','starting'):
            args=self.fixture();args[2]['jobs']['root']['status']=status
            with self.assertRaises(ValueError):subject.validate_frontier(*args)

    def test_pending_members_and_leases_denied(self):
        for where in ('job','worker','lease'):
            args=self.fixture()
            if where=='job':args[2]['jobs']['worker1']={'status':'running'}
            elif where=='worker':args[3]['workers']['worker1']={}
            else:args[3]['active_leases']['lib/x.dart']='worker1'
            with self.assertRaises(ValueError):subject.validate_frontier(*args)

    def test_prior_pause_or_reply_cannot_repeat(self):
        for operation in ('paused','authority','staged','resumed','reply_read_completed'):
            args=self.fixture();args[5].append({'operation':operation})
            with self.assertRaises(ValueError):subject.validate_frontier(*args)

    def test_clock_and_identity_drift_denied(self):
        for field in ('run_id','case_id','agent_path','parent_native_uuid'):
            args=self.fixture();args[4]['binding'][field]='replacement'
            with self.assertRaises(ValueError):subject.validate_frontier(*args)
        args=self.fixture();args[4]['binding']['root_native_uuid']='original-parent'
        with self.assertRaises(ValueError):subject.validate_frontier(*args)
        for container in (1,2,4):
            for field in (('original_started_at','original_deadline') if container!=2 else ('started_at','deadline')):
                args=self.fixture();args[container][field]+=1
                with self.assertRaises(ValueError):subject.validate_frontier(*args)

    def test_capability_and_boolean_caps_denied(self):
        args=self.fixture();args[4]['root_capability_sha256']='replacement'
        with self.assertRaises(ValueError):subject.validate_frontier(*args)
        for container in (2,4):
            args=self.fixture();args[container]['worker_cap']=False
            with self.assertRaises(ValueError):subject.validate_frontier(*args)

    def test_supplied_json_cannot_be_owner_authority(self):
        with self.assertRaises(ValueError):
            subject.quiesce_first({},'untrusted','untrusted',owner={},root_locator='/tmp/fake',frozen_sources={})


class WrapperControls(unittest.TestCase):
    """Mocked effect-path order only. These are not native/SDK qualification."""
    fixture = FrontierTests.fixture

    def exercise(self,mode='success'):
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            args=self.fixture();row,prepared,state,members,control,history,parent=args
            state['jobs']['root']['container_id']='owned-original-id'
            root=Path(tmp);folder=root/'runtime'/row['run_id'];folder.mkdir(parents=True)
            reference={'path':str(folder/'coordinator/prepared.json')}
            owner=object.__new__(subject.source.RootSource);owner.value={'parent_native_id':parent}
            owner.root_origin=mock.Mock(return_value={'native_join':{'child_native_id':'original-child'},
                                                      'child_entity':{'original':True}})
            owner.parent=mock.Mock(return_value=(b'parent\n',{}))
            effects=[];capture=[b'complete\n'];checks={'source':0,'prepared':0}
            if mode=='partial_before':capture[0]=b'complete\npartial-next-turn'
            def pin_check(kind):
                checks[kind]+=1
                if mode==kind+'_drift_after' and checks[kind]==(3 if kind=='source' else 2):
                    raise ValueError('post-effect pin drift')
            @contextlib.contextmanager
            def locking(label):
                effects.append('acquire-'+label)
                try:yield
                finally:effects.append('release-'+label)
            def snapshot(*unused,**kwargs):
                self.assertEqual(kwargs,{'restart':False,'cleanup':False})
                effects.append('snapshot');state['jobs']['root']['status']='stopped'
                if mode=='append_after':capture[0]+=b'next-turn\n'
                if mode in ('stop_failure','error_receipt_failure'):raise RuntimeError('original stop failed')
                if mode=='container_replaced':state['jobs']['root']['container_id']='replacement'
                return {'container_id':'owned-original-id','scope_error':None}
            def patch(obj,name,**kwargs):return stack.enter_context(mock.patch.object(obj,name,**kwargs))
            patch(subject.coordinator,'ROOT',new=root)
            patch(subject.coordinator,'source_fence',side_effect=lambda *a:pin_check('source'))
            patch(subject.runtime,'question_reference_bytes',return_value=json.dumps(prepared).encode())
            patch(subject.runtime,'question_verify_reference',side_effect=lambda *a:pin_check('prepared'))
            patch(subject.runtime,'question_reference',side_effect=lambda p:{'path':str(p)})
            patch(subject.runtime,'declared_runtime',side_effect=lambda *a:(copy.deepcopy(state),copy.deepcopy(members)))
            patch(subject.runtime,'question_coordinator_auth',side_effect=lambda *a:(copy.deepcopy(state),copy.deepcopy(control),[]))
            patch(subject.runtime,'question_operation_lock',side_effect=lambda *a:locking('question'))
            patch(subject.runtime,'lock',side_effect=lambda *a:locking('root'))
            patch(subject.runtime,'snapshot',side_effect=snapshot)
            original_atomic=subject.runtime.atomic_json
            def write_receipt(path,*a,**kw):
                if mode=='error_receipt_failure' and Path(path).name=='error.json':
                    raise OSError('cannot preserve error receipt')
                return original_atomic(path,*a,**kw)
            patch(subject.runtime,'atomic_json',side_effect=write_receipt)
            patch(subject.runtime,'inspect',return_value={'State':{'Running':False}})
            patch(subject.source.capture,'native_capture',side_effect=lambda *a:(capture[0],{}))
            patch(subject.coordinator.adapter,'turn_contract',return_value={'expected_turns':1})
            patch(subject.coordinator.adapter.lifecycle,'lifecycle',return_value=(None,[{'completed_at':'1970-01-01T00:01:40Z'}]))
            patch(subject.time,'time',return_value=101.0)
            if mode=='success':
                subject.quiesce_first(reference,'root','coord',owner=owner,root_locator='/original/native',frozen_sources={})
                self.assertTrue((folder/'question-root-quiescence/receipt.json').exists())
                with self.assertRaises(ValueError):
                    subject.quiesce_first(reference,'root','coord',owner=owner,root_locator='/original/native',frozen_sources={})
                self.assertEqual(effects.count('snapshot'),1)
                self.assertEqual(effects[:3],['acquire-question','acquire-root','snapshot'])
                self.assertEqual(effects[-2:],['release-root','release-question'])
            else:
                with self.assertRaises((ValueError,RuntimeError)) as raised:
                    subject.quiesce_first(reference,'root','coord',owner=owner,root_locator='/original/native',frozen_sources={})
                self.assertFalse((folder/'question-root-quiescence/receipt.json').exists())
                if mode=='partial_before':
                    self.assertNotIn('snapshot',effects)
                    self.assertFalse((folder/'question-root-quiescence').exists())
                elif mode=='error_receipt_failure':
                    self.assertIsInstance(raised.exception,RuntimeError)
                    self.assertEqual(str(raised.exception),'original stop failed')
                    self.assertIsInstance(raised.exception.__cause__,OSError)
                    self.assertTrue((folder/'question-root-quiescence/intent.json').exists())
                    self.assertEqual(effects.count('snapshot'),1)
                else:
                    error=json.loads((folder/'question-root-quiescence/error.json').read_text())
                    self.assertFalse(error['restart_permitted'])
                    self.assertTrue(error['original_owned_cleanup_required'])
                    self.assertEqual(effects.count('snapshot'),1)

    def test_original_lock_order_single_effect_and_repeat_denial(self):self.exercise()
    def test_incomplete_next_turn_cannot_be_ignored(self):self.exercise('partial_before')
    def test_append_during_effect_cannot_report_success(self):self.exercise('append_after')
    def test_post_effect_source_pin_drift_cannot_report_success(self):self.exercise('source_drift_after')
    def test_post_effect_prepared_drift_cannot_report_success(self):self.exercise('prepared_drift_after')
    def test_partial_stop_failure_preserves_cleanup_obligation(self):self.exercise('stop_failure')
    def test_error_writer_cannot_replace_primary_failure(self):self.exercise('error_receipt_failure')
    def test_replaced_container_cannot_report_success(self):self.exercise('container_replaced')


if __name__=='__main__':unittest.main()
