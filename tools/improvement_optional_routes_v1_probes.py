"""Synthetic route/ledger/lifecycle controls only, not a model execution."""
import copy
import hashlib
import json
import shlex
import unittest

import improvement_optional_routes_v1 as audit


def event(second,payload,kind='response_item'):
    return {'timestamp':f'2026-10-12T00:00:{second:02d}Z','type':kind,'payload':payload}


def encode(es):return b''.join(json.dumps(e).encode()+b'\n' for e in es)


def contract(job='root'):
    path='/root/product'+('' if job=='root' else '/'+job)
    return {'job':job,'agent_path':path,'run_name':'probe','broker_script':'/repo/tools/improvement_optional_broker_v1.py',
            'capability_sha256':hashlib.sha256(('a'*48).encode()).hexdigest(),
            'request_sha256':hashlib.sha256(b'Public task').hexdigest(),
            'reply_sha256':hashlib.sha256(b'Public reply').hexdigest(),'spawns':{}}


def wrapper(c,op,data=None):
    parts=['python3',c['broker_script'],'--run',c['run_name'],'--job',c['job'],'--cap','a'*48,'--op',op,'--data',json.dumps(data or {})]
    return 'text(await tools.exec_command('+json.dumps({'cmd':shlex.join(parts)})+'));'


def call(t,cid,code):return event(t,{'type':'custom_tool_call','name':'exec','call_id':cid,'input':code})


def output(t,cid,body,exit_code=0,session=None):
    value={'output':body,'wall_time_seconds':0.1}
    if session is None:value['exit_code']=exit_code
    else:value['session_id']=session
    return event(t,{'type':'custom_tool_call_output','call_id':cid,'output':json.dumps(value)})


def turn(c,turn_id,start,ops):
    path=c['agent_path'];text='Done '+turn_id
    es=[event(start,{'type':'task_started','turn_id':turn_id},'event_msg'),
        event(start+1,{'turn_id':turn_id,'model':'gpt-6.1-sol','effort':'medium'},'turn_context'),
        event(start+2,{'type':'agent_message','author':path.rsplit('/',1)[0],'recipient':path,
              'turn_id':turn_id,'content':[{'type':'encrypted_content','encrypted_content':'gAAAAAtoken'}]})]
    es+=ops;t=start+9
    es+=[event(t,{'type':'message','role':'assistant','channel':'final','turn_id':turn_id,
                 'content':[{'type':'output_text','text':text}]}),
         event(t+1,{'type':'task_complete','turn_id':turn_id,'last_agent_message':text},'event_msg')]
    return es


class Controls(unittest.TestCase):
    def fixture(self,job='root',two_turns=False):
        c=contract(job);path=c['agent_path'];parent='parent' if job=='root' else 'root-id'
        binding={'agent_path':path,'actor_native_id':'native-'+job,'parent_native_id':parent}
        read={'status':'ok','result':{'text':'Public task'}};execution={'status':'ok','result':{'exit_code':7,'stdout':'','stderr':'failure'}}
        ops=[call(5,'read',wrapper(c,'read')),output(6,'read',json.dumps(read)),
             call(7,'exec',wrapper(c,'exec',{'command':'exit 7','seconds':30})),output(8,'exec',json.dumps(execution))]
        es=[event(0,{'id':binding['actor_native_id'],'agent_path':path,'parent_thread_id':parent,
                    'source':{'subagent':{'thread_spawn':{'parent_thread_id':parent,'agent_path':path}}}},'session_meta')]
        es+=turn(c,'turn1',2,ops)
        ledger=[{'action_id':0,'request':{'job':job,'op':'read','data':{}},'status':'completed','result':read['result']},
                {'action_id':1,'request':{'job':job,'op':'exec','data':{'command':'exit 7','seconds':30}},'status':'completed','result':execution['result']}]
        if two_turns:
            reply={'status':'ok','result':{'text':'Public reply'}}
            es+=turn(c,'turn2',20,[call(23,'reply',wrapper(c,'read_reply')),output(24,'reply',json.dumps(reply))])
            ledger.append({'action_id':2,'request':{'job':job,'op':'read_reply','data':{}},'status':'completed','result':reply['result']})
        return es,binding,c,ledger

    def check(self,es,binding,c,ledger):
        raw=encode(es);ids=[e['payload']['turn_id'] for e in es if e['type']=='turn_context']
        return audit.audit_member(raw,binding,c,json.dumps(ledger).encode(),{'turn_ids':ids,'native_sha256':hashlib.sha256(raw).hexdigest(),'approved':True})

    def test_solo_worker_and_two_turn_root(self):
        for job,two in [('root',False),('worker1',False),('worker2',False),('root',True)]:
            d=self.check(*self.fixture(job,two));self.assertFalse(d['native_qualified']);self.assertFalse(d['cleanup_authorized'])

    def test_wrong_cap_job_script_op(self):
        for change in ['cap','job','script','op']:
            a=list(self.fixture('worker1'));code=a[0][6]['payload']['input']
            if change=='cap':code=code.replace('a'*48,'b'*48)
            elif change=='job':code=code.replace('--job worker1','--job root')
            elif change=='script':code=code.replace('optional_broker_v1','other')
            else:code=code.replace('--op exec','--op integrate')
            a[0][6]['payload']['input']=code
            with self.assertRaises(ValueError):self.check(*a)

    def test_repeated_or_wrong_first_read(self):
        for first in [True,False]:
            a=list(self.fixture());a[0][4 if first else 6]['payload']['input']=wrapper(a[2],'exec' if first else 'read')
            with self.assertRaises(ValueError):self.check(*a)

    def test_bootstrap_incomplete_or_inner_failure(self):
        for body in [{'status':'ok','result':{'text':'partial'}},{'status':'error','message':'failed'}]:
            a=list(self.fixture());a[0][5]=output(6,'read',json.dumps(body))
            with self.assertRaises(ValueError):self.check(*a)

    def test_work_before_bootstrap_receipt(self):
        a=list(self.fixture());es=a[0];es[5],es[6]=es[6],es[5];es[5]['timestamp']='2026-10-12T00:00:05Z';es[6]['timestamp']='2026-10-12T00:00:06Z'
        with self.assertRaises(ValueError):self.check(*a)

    def test_host_expansion_or_extra_tool(self):
        for suffix in ['; await tools.web__run({});','; await tools.exec_command({"cmd":"id"});']:
            a=list(self.fixture());a[0][6]['payload']['input']+=suffix
            with self.assertRaises(ValueError):self.check(*a)
        c=contract();code=wrapper(c,'exec',{'command':'echo $(id) `id` $HOME'})
        self.assertEqual(audit.wrapper(code,c)['data']['command'],'echo $(id) `id` $HOME')
        obj=json.loads(code[len('text(await tools.exec_command('):-3]);obj['cmd']+='; id'
        with self.assertRaises(ValueError):audit.wrapper('text(await tools.exec_command('+json.dumps(obj)+'));',c)

    def test_duplicate_execution_option(self):
        code=wrapper(contract(),'read').replace('}));',', yield_time_ms:1, yield_time_ms:2}));')
        with self.assertRaises(ValueError):audit.wrapper(code,contract())

    def test_missing_duplicate_wrong_receipt(self):
        for mode in ['missing','duplicate','wrong_type']:
            a=list(self.fixture())
            if mode=='missing':a[0].pop(7)
            elif mode=='duplicate':a[0].insert(8,copy.deepcopy(a[0][7]))
            else:a[0][7]['payload']['type']='function_call_output'
            with self.assertRaises(ValueError):self.check(*a)

    def test_ledger_omission_extra_mismatch_pending(self):
        for mode in ['missing','extra','result','request','pending']:
            a=list(self.fixture())
            if mode=='missing':a[3].pop()
            elif mode=='extra':a[3].append(dict(copy.deepcopy(a[3][-1]),action_id=2))
            elif mode=='result':a[3][-1]['result']['exit_code']=0
            elif mode=='request':a[3][-1]['request']['data']['seconds']=1
            else:a[3][-1]['status']='started'
            with self.assertRaises(ValueError):self.check(*a)

    def test_actual_failed_action_outer_code_one(self):
        a=list(self.fixture());error={'type':'ValueError','message':'recorded failure'}
        a[3][-1].pop('result');a[3][-1].update(status='failed',error=error)
        a[0][7]=output(8,'exec',json.dumps({'status':'error',**error}),exit_code=1)
        self.check(*a)
        a[0][7]=output(8,'exec',json.dumps({'status':'error',**error}),exit_code=0)
        with self.assertRaises(ValueError):self.check(*a)

    def asynchronous(self):
        a=list(self.fixture());body=json.loads(json.loads(a[0][7]['payload']['output'])['output']);text=json.dumps(body)
        a[0][7]=output(8,'exec',text[:12],session=7)
        a[0][8:8]=[call(9,'poll','text(await tools.write_stdin({session_id:7, chars:""}));'),output(10,'poll',text[12:])]
        a[0][-2]['timestamp']='2026-10-12T00:00:11Z';a[0][-1]['timestamp']='2026-10-12T00:00:12Z'
        return a

    def test_owned_async_chunks_close(self):self.check(*self.asynchronous())

    def test_foreign_input_open_or_reused_session(self):
        for mode in ['foreign','stdin','open','duplicate_key']:
            a=self.asynchronous()
            if mode=='foreign':a[0][8]['payload']['input']=a[0][8]['payload']['input'].replace('session_id:7','session_id:8')
            elif mode=='stdin':a[0][8]['payload']['input']=a[0][8]['payload']['input'].replace('chars:""','chars:"x"')
            elif mode=='open':a[0][9]=output(10,'poll','',session=7)
            else:a[0][8]['payload']['input']=a[0][8]['payload']['input'].replace('session_id:7','session_id:8,session_id:7')
            with self.assertRaises(ValueError):self.check(*a)

    def test_worker_coordination_denied(self):
        a=list(self.fixture('worker1'));a[0][6]['payload']={'type':'function_call','namespace':'collaboration','name':'list_agents','call_id':'exec','arguments':'{}'}
        with self.assertRaises(ValueError):self.check(*a)

    def test_second_turn_requires_pinned_first_reply(self):
        for mode in ['op','text','repeat']:
            a=list(self.fixture(two_turns=True))
            if mode=='op':a[0][13]['payload']['input']=wrapper(a[2],'exec')
            elif mode=='text':a[0][14]=output(24,'reply',json.dumps({'status':'ok','result':{'text':'wrong'}}))
            else:a[2]['reply_sha256']=None
            with self.assertRaises(ValueError):self.check(*a)

    def test_extra_unapproved_model_or_turn(self):
        a=list(self.fixture());a[0][2]['payload']['model']='gpt-6-sol'
        with self.assertRaises(ValueError):self.check(*a)
        a=list(self.fixture('worker1',True))
        with self.assertRaises(ValueError):self.check(*a)

    def test_root_optional_spawn_matches_membership(self):
        a=list(self.fixture());c=a[2];token='gAAAAAworker';c['spawns']={'spawn':{'agent_path':'/root/product/worker1','request_token_sha256':hashlib.sha256(token.encode()).hexdigest()}}
        args={'task_name':'worker1','message':token,'model':'gpt-6.1-sol','reasoning_effort':'medium','fork_turns':'none'}
        a[0][8:8]=[event(9,{'type':'function_call','namespace':'collaboration','name':'spawn_agent','call_id':'spawn','arguments':json.dumps(args)}),
                      event(10,{'type':'function_call_output','call_id':'spawn','output':'{"task_name":"/root/product/worker1"}'})]
        a[0][-2]['timestamp']='2026-10-12T00:00:11Z';a[0][-1]['timestamp']='2026-10-12T00:00:12Z'
        self.check(*a)
        c['spawns']={}
        with self.assertRaises(ValueError):self.check(*a)


if __name__=='__main__':unittest.main()
