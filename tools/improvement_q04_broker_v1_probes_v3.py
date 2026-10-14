"""Root-authored protocol fixtures only. No model/Docker/software outcome claim."""
import copy
import hashlib
import json
from pathlib import Path
import shlex
import unittest
from datetime import datetime,timezone,timedelta
import improvement_q04_broker_v1 as broker
import improvement_q04_native_v2 as native

ROOT=broker.ROOT
class Protocol(unittest.TestCase):
    def fixture(self,failed=False):
        cap='a'*48;name='q04-broker-v1-authored-probe';job='pricing';request='public request\n'
        registration={'run_name':name,'capability_hashes':{job:hashlib.sha256(cap.encode()).hexdigest()},
                      'actors':{job:{'path':'/root/example/pricing','source':'authored-native-only',
                                    'bootstrap_code':'text(await tools.exec_command({"cmd":"cat sole-request","max_output_tokens":6500}));',
                                    'request_sha256':hashlib.sha256(request.encode()).hexdigest()}}}
        data={'command':'cat lib/pricing.dart','seconds':20}
        action={'job':job,'op':'exec','data':data}
        expected={'status':'error','type':'ValueError','message':'authored failure'} if failed else {'status':'ok','result':{'exit_code':0,'stdout':'authored output','stderr':''}}
        encoded=json.dumps(expected)+'\n';split=10
        shell='python3 '+str(ROOT/'tools/improvement_q04_broker_v1.py')+' --run '+name+' --job '+job+' --cap '+cap+' --op exec --data '+shlex.quote(json.dumps(data))
        code='text(await tools.exec_command('+json.dumps({'cmd':shell,'yield_time_ms':1000})+'));'
        events=[]
        def event(kind,payload):
            when=datetime(2026,10,12,tzinfo=timezone.utc)+timedelta(seconds=len(events))
            events.append({'type':kind,'timestamp':when.isoformat(),'payload':payload})
        def call(cid,code):event('response_item',{'type':'custom_tool_call','name':'exec','namespace':'functions','call_id':cid,'input':code})
        def output(cid,value):event('response_item',{'type':'custom_tool_call_output','call_id':cid,'output':[{'type':'text','text':json.dumps(value)}]})
        event('session_meta',{'id':'authored-session','agent_path':registration['actors'][job]['path'],'parent_thread_id':'authored-parent'})
        event('turn_context',{'turn_id':'authored-turn','model':'gpt-6.1-sol','effort':'medium'})
        call('bootstrap',registration['actors'][job]['bootstrap_code']);output('bootstrap',{'exit_code':0,'output':request})
        call('broker',code);output('broker',{'session_id':5734,'output':encoded[:split]})
        call('poll','text(await tools.write_stdin({session_id:5734,chars:""}));');output('poll',{'exit_code':1 if failed else 0,'output':encoded[split:]})
        event('event_msg',{'type':'task_complete','turn_id':'authored-turn','completed_at':1791731600,'duration_ms':8000})
        entry={'job':job,'request':action,'status':'failed' if failed else 'completed'}
        entry.update(error={k:v for k,v in expected.items() if k!='status'}) if failed else entry.update(result=expected['result'])
        return events,registration,{'actions':[entry]},expected
    def audit(self,events,registration):
        raw=b''.join(json.dumps(e).encode()+b'\n' for e in events)
        return native.audit(raw,registration,'pricing',ROOT)
    def test_owned_async_success_join(self):
        events,reg,state,expected=self.fixture();proof=self.audit(events,reg)
        self.assertEqual(json.loads(proof['broker_receipts'][0]['stdout']),expected)
        broker.reconcile_requests(None,reg,state,'pricing',proof)
    def test_owned_async_failure_join(self):
        events,reg,state,expected=self.fixture(True);proof=self.audit(events,reg)
        broker.reconcile_requests(None,reg,state,'pricing',proof)
        self.assertEqual(proof['broker_receipts'][0]['exit_code'],1)
    def test_counterfeit_success_rejected(self):
        events,reg,state,_=self.fixture(True);proof=self.audit(events,reg)
        proof['broker_receipts'][0]['stdout']=json.dumps({'status':'ok','result':{'exit_code':0}})
        with self.assertRaises(ValueError):broker.reconcile_requests(None,reg,state,'pricing',proof)
    def test_result_mutation_rejected(self):
        events,reg,state,_=self.fixture();proof=self.audit(events,reg)
        state['actions'][0]['result']['stdout']='counterfeit'
        with self.assertRaises(ValueError):broker.reconcile_requests(None,reg,state,'pricing',proof)
    def test_outer_exit_mismatch_rejected(self):
        events,reg,state,_=self.fixture();proof=self.audit(events,reg);proof['broker_receipts'][0]['exit_code']=1
        with self.assertRaises(ValueError):broker.reconcile_requests(None,reg,state,'pricing',proof)
    def test_foreign_poll_rejected(self):
        events,reg,_,_=self.fixture();events[6]['payload']['input']=events[6]['payload']['input'].replace('5734','5735')
        with self.assertRaises(ValueError):self.audit(events,reg)
    def test_nonempty_poll_rejected(self):
        events,reg,_,_=self.fixture();events[6]['payload']['input']=events[6]['payload']['input'].replace('chars:""','chars:"change"')
        with self.assertRaises(ValueError):self.audit(events,reg)
    def test_pending_session_rejected(self):
        events,reg,_,_=self.fixture();events[7]['payload']['output'][0]['text']=json.dumps({'session_id':5734,'output':''})
        with self.assertRaises(ValueError):self.audit(events,reg)
    def test_wrong_capability_rejected(self):
        events,reg,_,_=self.fixture();events[4]['payload']['input']=events[4]['payload']['input'].replace('a'*48,'b'*48)
        with self.assertRaises(ValueError):self.audit(events,reg)
    def test_worker_integrate_rejected(self):
        events,reg,_,_=self.fixture();events[4]['payload']['input']=events[4]['payload']['input'].replace('--op exec','--op integrate')
        with self.assertRaises(ValueError):self.audit(events,reg)
    def test_mixed_poll_terminal_and_open_session_rejected(self):
        events,reg,_,_=self.fixture();obj=json.loads(events[7]['payload']['output'][0]['text']);obj['session_id']=5734
        events[7]['payload']['output'][0]['text']=json.dumps(obj)
        with self.assertRaises(ValueError):self.audit(events,reg)
    def test_mixed_bootstrap_terminal_and_open_session_rejected(self):
        events,reg,_,_=self.fixture();obj=json.loads(events[3]['payload']['output'][0]['text']);obj['session_id']=5734
        events[3]['payload']['output'][0]['text']=json.dumps(obj)
        with self.assertRaises(ValueError):self.audit(events,reg)
    def test_duplicate_native_result_key_rejected(self):
        events,reg,_,_=self.fixture();events[7]['payload']['output'][0]['text']='{"exit_code":1,"exit_code":0,"output":""}'
        with self.assertRaises(ValueError):self.audit(events,reg)
    def test_duplicate_broker_stdout_status_rejected(self):
        events,reg,state,_=self.fixture();proof=self.audit(events,reg)
        proof['broker_receipts'][0]['stdout']='{"status":"error","status":"ok","result":'+json.dumps(state['actions'][0]['result'])+'}'
        with self.assertRaises(ValueError):broker.reconcile_requests(None,reg,state,'pricing',proof)
    def test_null_session_terminal_allowed(self):
        events,reg,state,_=self.fixture();obj=json.loads(events[7]['payload']['output'][0]['text']);obj['session_id']=None
        events[7]['payload']['output'][0]['text']=json.dumps(obj)
        broker.reconcile_requests(None,reg,state,'pricing',self.audit(events,reg))
    def test_nonfinite_native_result_rejected(self):
        events,reg,_,_=self.fixture();events[7]['payload']['output'][0]['text']='{"exit_code":0,"output":"","wall_time_seconds":NaN}'
        with self.assertRaises(ValueError):self.audit(events,reg)
    def test_verifier_reports_actual_check_commands(self):
        receipt={'status':'completed','pass':True,'checks':[{'argv':['docker','exec','owned','/sdks/flutter/bin/flutter','test'],'exit_code':0}], 'identity':{'Config':{'Cmd':['sleep','infinity']}},'machine':{'pass':True},'removed':True,'source_unchanged':True}
        view=broker.verification_view(receipt)
        self.assertEqual(view['checks'][0]['argv'],receipt['checks'][0]['argv'])
        self.assertNotIn('executed_argv',view)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Protocol))
    names=['tools/improvement_q04_broker_v1.py','tools/improvement_q04_native_v2.py','tools/improvement_q04_broker_v1_probes_v3.py']
    value={'status':'pass' if result.wasSuccessful() else 'fail','tests':result.testsRun,'failures':[(str(t),s) for t,s in result.failures],'errors':[(str(t),s) for t,s in result.errors], 'scope':'Root-authored synthetic protocol unit checks only','actual_actor_allocated':False,'actual_docker_lifecycle_qualified':False,'launch_qualified':False,'superiority_proven':False,'source_hashes':{n:broker.sha(ROOT/n) for n in names}}
    with (ROOT/'results/improvement-v1/Q04-broker-v1-protocol-probes-v3.json').open('x') as f:json.dump(value,f,indent=2)
    raise SystemExit(0 if result.wasSuccessful() else 1)
