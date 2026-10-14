"""Synthetic native origin controls, not actual model runtime qualification."""
import copy
import json
import unittest
import improvement_optional_membership_v1 as m


def e(second, payload, kind='response_item'):
    return {'timestamp':f'2026-10-12T00:00:{second:02d}Z','type':kind,'payload':payload}


def raw(events):return b''.join(json.dumps(x).encode()+b'\n' for x in events)


def child(path, parent, identity, second, token):
    return [e(second,{'id':identity,'agent_path':path,'parent_thread_id':parent,
               'source':{'subagent':{'thread_spawn':{'parent_thread_id':parent,'agent_path':path}}}},'session_meta'),
            e(second+2,{'model':'gpt-6.1-sol','effort':'medium','turn_id':'turn-'+identity},'turn_context'),
            e(second+3,{'type':'agent_message','author':path.rsplit('/',1)[0],'recipient':path,
               'content':[{'type':'encrypted_content','encrypted_content':token}],
               'internal_chat_message_metadata_passthrough':{'turn_id':'turn-'+identity}})]


def spawn(task, cid, token, second):
    return e(second,{'type':'function_call','namespace':'collaboration','name':'spawn_agent',
         'call_id':cid,'arguments':json.dumps({'task_name':task,'message':token,'fork_turns':'none',
                    'model':'gpt-6.1-sol','reasoning_effort':'medium'})})


def receipt(path,cid,second):return e(second,{'type':'function_call_output','call_id':cid,'output':json.dumps({'task_name':path})})


class Controls(unittest.TestCase):
    def fixture(self,n=2):
        started=m.core.instant('2026-10-12T00:00:00Z').timestamp()
        config={'run_id':'probe','model':'gpt-6.1-sol','effort':'medium','started_at':started,
                'deadline':started+1200,'worker_cap':2,'retries':0}
        workers={}
        for i in range(n):
            slot=f'worker{i+1}'
            workers[slot]={'slot':slot,'goal':'public work','scope':[f'lib/{i}.dart'],'mode':'write',
                          'snapshot':{},'snapshot_sha256':'b'*64,'status':'reserved','errors':[]}
        state={'configuration':config,'configuration_sha256':m.digest(config),'workers':workers,'head_sha256':'c'*64}
        root_path='/root/product'
        def intent(job,at):
            return {'job':job,'agent_path':root_path if job=='root' else root_path+'/'+job,
                    'at':f'2026-10-12T00:00:{at:02d}Z','public_request_sha256':'d'*64,
                    'configuration_sha256':m.digest(config),
                    'reservation_worker_sha256':None if job=='root' else m.worker_digest(workers[job])}
        ri=intent('root',0);wi={slot:intent(slot,5) for slot in workers}
        parent=[e(0,{'id':'coordinator'},'session_meta'),spawn('product','rootcall','gAAAAAroot',1),receipt(root_path,'rootcall',3)]
        root=child(root_path,'coordinator','root-id',2,'gAAAAAroot');members={}
        for i,slot in enumerate(workers):
            t=6+i*6;path=root_path+'/'+slot;token='gAAAAA'+slot
            root.extend([spawn(slot,slot,token,t),receipt(path,slot,t+2)])
            members[path]=raw(child(path,'root-id','id-'+slot,t+1,token))
        jobs={}
        for job,v in {'root':ri,**wi}.items():
            jobs[job]={'job':job,'agent_path':v['agent_path'],'intent_sha256':m.digest(v),
                       'public_request_sha256':v['public_request_sha256'],'status':'prepared'}
        return [config,state,ri,wi,raw(parent),raw(root),members,
                {'run_id':'probe','configuration_sha256':m.digest(config),'jobs':jobs}]

    def edit_root(self,a,change):
        events=m.core.parse(a[5]);change(events);a[5]=raw(events)

    def test_valid_zero_one_two(self):
        for n in range(3):
            with self.subTest(n=n):
                d=m.reconcile_membership(*self.fixture(n));self.assertEqual(len(d['members']),n+1)
                self.assertTrue(d['provided_allocation_joins_complete']);self.assertFalse(d['native_qualified'])

    def test_third_or_replacement(self):
        for task in ['worker1','worker3']:
            a=self.fixture();self.edit_root(a,lambda es:es.extend([spawn(task,'extra','gAAAAAextra',20)]))
            with self.assertRaises(ValueError):m.reconcile_membership(*a)

    def test_unregistered_spawn_or_source(self):
        a=self.fixture(0);self.edit_root(a,lambda es:es.extend([spawn('worker1','extra','gAAAAAextra',6)]))
        with self.assertRaises(ValueError):m.reconcile_membership(*a)
        a=self.fixture(0);a[6]['/root/product/worker1']=raw(child('/root/product/worker1','root-id','other',7,'gAAAAAother'))
        with self.assertRaises(ValueError):m.reconcile_membership(*a)

    def test_missing_receipt_stays_pending_and_retains_source(self):
        a=self.fixture(1);self.edit_root(a,lambda es:es.pop())
        d=m.reconcile_membership(*a);self.assertEqual(d['pending_allocation_slots'],['worker1'])
        self.assertEqual(len(d['observed_unbound_sources']),1);self.assertFalse(d['provided_allocation_joins_complete'])

    def test_unknown_receipt_not_absence(self):
        for output in ['{}','{"error":"unknown"}','not-json']:
            a=self.fixture(1);self.edit_root(a,lambda es:es[-1]['payload'].update(output=output))
            d=m.reconcile_membership(*a);self.assertEqual(d['attempts'][0]['allocation_status'],'dispatch_outcome_unknown')

    def test_missing_native_source_stays_pending(self):
        a=self.fixture(1);a[6]={};d=m.reconcile_membership(*a)
        self.assertEqual(d['attempts'][0]['allocation_status'],'allocated_native_source_missing')

    def test_reserved_without_dispatch_keeps_slot(self):
        a=self.fixture(1);self.edit_root(a,lambda es:es.__delitem__(slice(3,None)));a[6]={};a[3]={}
        d=m.reconcile_membership(*a);self.assertEqual(d['pending_allocation_slots'],['worker1'])
        self.assertEqual(len(d['attempts']),1)

    def test_allocation_error_not_filtered(self):
        a=self.fixture(1);a[1]['workers']['worker1']['status']='allocation_unknown_pending_reconciliation'
        a[1]['workers']['worker1']['errors']=[{'type':'RuntimeError','message':'ambiguous'}]
        d=m.reconcile_membership(*a);self.assertEqual(len(d['members']),2)
        self.assertEqual(d['attempts'][0]['registry_errors'][0]['message'],'ambiguous')

    def test_nested_worker_allocation(self):
        a=self.fixture(1);path='/root/product/worker1';es=m.core.parse(a[6][path]);es.append(spawn('nested','nested','gAAAAAnested',20));a[6][path]=raw(es)
        with self.assertRaises(ValueError):m.reconcile_membership(*a)

    def test_worker_uuid_or_parent_conflict(self):
        for field,value in [('id','root-id'),('parent_thread_id','foreign')]:
            a=self.fixture(1);p='/root/product/worker1';es=m.core.parse(a[6][p]);es[0]['payload'][field]=value;a[6][p]=raw(es)
            with self.assertRaises(ValueError):m.reconcile_membership(*a)

    def test_spawn_model_context_extra_args(self):
        for key,value in [('model','gpt-6-sol'),('reasoning_effort','high'),('fork_turns','all'),('other',True)]:
            a=self.fixture(1)
            def change(es):
                args=json.loads(es[3]['payload']['arguments']);args[key]=value;es[3]['payload']['arguments']=json.dumps(args)
            self.edit_root(a,change)
            with self.assertRaises(ValueError):m.reconcile_membership(*a)

    def test_later_actual_model_not_hidden_by_initial_binding(self):
        a=self.fixture(1);p='/root/product/worker1';es=m.core.parse(a[6][p]);es.append(e(20,{'model':'gpt-6-sol','effort':'medium'},'turn_context'));a[6][p]=raw(es)
        with self.assertRaises(ValueError):m.reconcile_membership(*a)

    def test_initial_token_mismatch(self):
        a=self.fixture(1);p='/root/product/worker1';es=m.core.parse(a[6][p]);es[-1]['payload']['content'][0]['encrypted_content']='gAAAAAwrong';a[6][p]=raw(es)
        with self.assertRaises(ValueError):m.reconcile_membership(*a)

    def test_scope_goal_snapshot_or_configuration_drift(self):
        for key,value in [('goal','changed'),('scope',[]),('snapshot_sha256','e'*64)]:
            a=self.fixture(1);a[1]['workers']['worker1'][key]=value
            with self.assertRaises(ValueError):m.reconcile_membership(*a)
        a=self.fixture(1);a[3]['worker1']['configuration_sha256']='f'*64
        with self.assertRaises(ValueError):m.reconcile_membership(*a)

    def test_intent_after_spawn(self):
        a=self.fixture(1);a[3]['worker1']['at']='2026-10-12T00:00:07Z';a[7]['jobs']['worker1']['intent_sha256']=m.digest(a[3]['worker1'])
        with self.assertRaises(ValueError):m.reconcile_membership(*a)

    def test_unprepared_provision(self):
        a=self.fixture(1);a[7]['jobs']['worker1']['status']='failed'
        with self.assertRaises(ValueError):m.reconcile_membership(*a)

    def test_duplicate_json_or_nonfinite(self):
        a=self.fixture(0);a[5]=a[5].replace(b'"id": "root-id"',b'"id": "root-id", "id": "other"')
        with self.assertRaises(ValueError):m.reconcile_membership(*a)
        a=self.fixture(0);a[5]=a[5].replace(b'"id": "root-id"',b'"id": "root-id", "bad": 1e999')
        with self.assertRaises(ValueError):m.reconcile_membership(*a)


if __name__=='__main__':unittest.main()
