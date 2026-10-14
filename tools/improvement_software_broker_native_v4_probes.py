"""Synthetic route tests, not real model/software qualification."""
import copy
import hashlib
import json
import shlex
import unittest
from pathlib import Path

from improvement_software_broker_native_v4 import audit, wrapper, runtime_completed

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/improvement-v1/software-broker-native-v4-probes.json'


def events_bytes(values):
    return b''.join(json.dumps(e).encode() + b'\n' for e in values)


def event(kind, payload, second):
    return {'type': kind, 'payload': payload, 'timestamp': '2026-10-11T08:00:' + str(second).zfill(2) + '.000Z'}


def registration():
    cap = 'a'*48
    return {'run_name': 'software-broker-v4-probe', 'capability_hashes': {j:hashlib.sha256(cap.encode()).hexdigest() for j in ('root','label','quantity')},
            'actors': {j:{'path':'/root/product' if j=='root' else '/root/product/'+j,'source':'synthetic-'+j,'request_sha256':hashlib.sha256(b'{}').hexdigest(),'bootstrap_code':'text(await tools.exec_command({"cmd":"cat /only/request-'+j+'"}));'} for j in ('root','label','quantity')}}


def code(job='label', op='exec', data=None):
    command = 'python3 ' + str(ROOT/'tools/improvement_software_broker_v4.py') + ' --run software-broker-v4-probe --job '+job+' --cap '+ 'a'*48 +' --op '+op+' --data '+shlex.quote(json.dumps(data or {'command':'python3 -m unittest tests.test_label -v','seconds':30}))
    return 'text(await tools.exec_command('+json.dumps({'cmd':command})+'));'


def trajectory():
    r=registration()
    values=[event('session_meta',{'id':'child-id','agent_path':r['actors']['label']['path'],'parent_thread_id':'parent-id'},0),
            event('event_msg',{'type':'task_started','turn_id':'turn-1'},1),
            event('turn_context',{'turn_id':'turn-1','model':'gpt-6.1-sol','effort':'medium'},2)]
    for i,c in enumerate((r['actors']['label']['bootstrap_code'],code())):
        values.append(event('response_item',{'type':'custom_tool_call','name':'exec','namespace':'functions','call_id':str(i),'input':c},3+2*i))
        values.append(event('response_item',{'type':'custom_tool_call_output','call_id':str(i),'output':json.dumps({'exit_code':0,'output':'{}','wall_time_seconds':0})},4+2*i))
    values += [event('event_msg',{'type':'token_count','info':{'total_token_usage':{'input_tokens':100,'cached_input_tokens':50,'output_tokens':10,'total_tokens':110}}},8),
               event('event_msg',{'type':'task_complete','turn_id':'turn-1','started_at':1,'completed_at':9,'duration_ms':8000},9)]
    return r,values


class Routes(unittest.TestCase):
    def test_literal_wrapper(self):
        self.assertEqual(wrapper(code(),ROOT,registration(),'label')['op'],'exec')
    def test_extra_tool(self):
        with self.assertRaises(ValueError):wrapper(code()+' await tools.web__run({});',ROOT,registration(),'label')
    def test_wrong_job(self):
        with self.assertRaises(ValueError):wrapper(code('quantity'),ROOT,registration(),'label')
    def test_root_operation_from_worker(self):
        with self.assertRaises(ValueError):wrapper(code('label','integrate'),ROOT,registration(),'label')
    def test_wrong_capability(self):
        with self.assertRaises(ValueError):wrapper(code().replace('a'*48,'b'*48),ROOT,registration(),'label')
    def test_closed_worker(self):
        r,v=trajectory();proof=audit(events_bytes(v),r,'label',ROOT)
        self.assertEqual(proof['native_calls'],2);self.assertEqual(proof['usage']['usage']['total_tokens'],110)
    def test_missing_native_output(self):
        r,v=trajectory();v=[e for e in v if not(e.get('payload',{}).get('type')=='custom_tool_call_output' and e['payload']['call_id']=='1')]
        with self.assertRaises(ValueError):audit(events_bytes(v),r,'label',ROOT)
    def test_duplicate_call(self):
        r,v=trajectory();v.insert(7,copy.deepcopy(v[5]))
        with self.assertRaises(ValueError):audit(events_bytes(v),r,'label',ROOT)
    def test_worker_message_route(self):
        r,v=trajectory();v[5]['payload'].update(type='function_call',name='send_message',namespace='collaboration',arguments='{}')
        with self.assertRaises(ValueError):audit(events_bytes(v),r,'label',ROOT)
    def test_repeated_bootstrap(self):
        r,v=trajectory();v[5]['payload']['input']=r['actors']['label']['bootstrap_code']
        with self.assertRaises(ValueError):audit(events_bytes(v),r,'label',ROOT)
    def test_incomplete_session(self):
        r,v=trajectory();v.pop()
        with self.assertRaises(ValueError):audit(events_bytes(v),r,'label',ROOT)
    def test_backward_receipt(self):
        r,v=trajectory();v[6]['timestamp']=v[0]['timestamp']
        with self.assertRaises(ValueError):audit(events_bytes(v),r,'label',ROOT)
    def test_unknown_namespace(self):
        r,v=trajectory();v[5]['payload']['namespace']='other'
        with self.assertRaises(ValueError):audit(events_bytes(v),r,'label',ROOT)
    def test_double_quoted_payload_expansion(self):
        prefix='python3 '+str(ROOT/'tools/improvement_software_broker_v4.py')+' --run software-broker-v4-probe --job label --cap '+'a'*48+' --op exec --data '
        data=json.dumps({'command':'$(id)','seconds':30})
        cmd=prefix+'"'+data.replace('"','\\"')+'"'
        bad='text(await tools.exec_command('+json.dumps({'cmd':cmd})+'));'
        with self.assertRaises(ValueError):wrapper(bad,ROOT,registration(),'label')
    def test_failed_bootstrap(self):
        r,v=trajectory();v[4]['payload']['output']=json.dumps({'exit_code':1,'output':'{}'})
        with self.assertRaises(ValueError):audit(events_bytes(v),r,'label',ROOT)
    def test_wrong_bootstrap_contents(self):
        r,v=trajectory();v[4]['payload']['output']=json.dumps({'exit_code':0,'output':'other task'})
        with self.assertRaises(ValueError):audit(events_bytes(v),r,'label',ROOT)
    def test_missing_poll_state(self):
        r,v=trajectory();v[6]['payload']['output']=json.dumps({'session_id':1,'output':''})
        poll='text(await tools.write_stdin({"session_id":1,"chars":"","yield_time_ms":1000}));'
        additions=[event('response_item',{'type':'custom_tool_call','name':'exec','namespace':'functions','call_id':'poll1','input':poll},7),
                   event('response_item',{'type':'custom_tool_call_output','call_id':'poll1','output':json.dumps({'output':'ambiguous','session_id':True})},8),
                   event('response_item',{'type':'custom_tool_call','name':'exec','namespace':'functions','call_id':'poll2','input':poll},9),
                   event('response_item',{'type':'custom_tool_call_output','call_id':'poll2','output':json.dumps({'exit_code':0,'output':'done'})},10)]
        v=v[:7]+additions+v[7:];v[-1]['timestamp']='2026-10-11T08:00:12.000Z'
        with self.assertRaises(ValueError):audit(events_bytes(v),r,'label',ROOT)
    def test_completion_before_tool_receipt(self):
        r,v=trajectory();v[-1]['timestamp']=v[0]['timestamp']
        with self.assertRaises(ValueError):audit(events_bytes(v),r,'label',ROOT)
    def test_runtime_duplicate_receipt(self):
        paths={'root':'/root/product','label':'/root/product/label','quantity':'/root/product/quantity'}
        v=[event('session_meta',{'id':'parent'},0),event('response_item',{'type':'function_call','name':'list_agents','namespace':'collaboration','call_id':'status','arguments':json.dumps({'path_prefix':paths['root']})},10),
           event('response_item',{'type':'function_call_output','call_id':'status','output':json.dumps({'agents':[{'agent_name':p,'agent_status':{'completed':'done'}} for p in paths.values()]})},11)]
        v.append(copy.deepcopy(v[-1]));v[-1]['timestamp']='2026-10-11T08:00:12.000Z'
        with self.assertRaises(ValueError):runtime_completed(events_bytes(v),paths,0)
    def test_pending_later_status_call(self):
        paths={'root':'/root/product','label':'/root/product/label','quantity':'/root/product/quantity'}
        v=[event('session_meta',{'id':'parent'},0),event('response_item',{'type':'function_call','name':'list_agents','namespace':'collaboration','call_id':'status','arguments':json.dumps({'path_prefix':paths['root']})},10),
           event('response_item',{'type':'function_call_output','call_id':'status','output':json.dumps({'agents':[{'agent_name':p,'agent_status':{'completed':'done'}} for p in paths.values()]})},11)]
        call=copy.deepcopy(v[1]);call['payload']['call_id']='unclosed';call['timestamp']='2026-10-11T08:00:12.000Z';v.append(call)
        with self.assertRaises(ValueError):runtime_completed(events_bytes(v),paths,0)
    def test_runtime_completed_actual_receipt_shape(self):
        paths={'root':'/root/product','label':'/root/product/label','quantity':'/root/product/quantity'}
        v=[event('session_meta',{'id':'parent'},0),event('response_item',{'type':'function_call','name':'list_agents','namespace':'collaboration','call_id':'status','arguments':json.dumps({'path_prefix':paths['root']})},10),
           event('response_item',{'type':'function_call_output','call_id':'status','output':json.dumps({'agents':[{'agent_name':p,'agent_status':{'completed':'done'}} for p in paths.values()]})},11)]
        self.assertEqual(runtime_completed(events_bytes(v),paths,0)['call_id'],'status')
        v[2]['payload']['output']=json.dumps({'agents':[{'agent_name':p,'agent_status':'running'} for p in paths.values()]})
        with self.assertRaises(ValueError):runtime_completed(events_bytes(v),paths,0)


if __name__=='__main__':
    assert not OUT.exists()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Routes)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'status':'pass' if result.wasSuccessful() else 'fail','synthetic_tests':result.testsRun,
            'failures':[(str(t),s) for t,s in result.failures],'errors':[(str(t),s) for t,s in result.errors],
            'actual_actor_or_software_qualified':False,'superiority_proven':False,
            'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),ROOT/'tools/improvement_software_broker_native_v4.py')}}
    with OUT.open('x') as f:json.dump(report,f,indent=2)
    raise SystemExit(0 if result.wasSuccessful() else 1)
