"""Actual failed-run compatibility and negative automatic delivery controls."""
import copy
import json
from pathlib import Path
import unittest

import improvement_optional_lifecycle_v4 as life

ROOT=Path(__file__).resolve().parents[1]


def encoded(events):return b''.join(json.dumps(e,ensure_ascii=False).encode()+b'\n' for e in events)


class LifecycleControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out=ROOT/'runtime/native-optional-control-v7-one_worker/native-close'
        cls.raw=(out/'root.jsonl').read_bytes();cls.child=(out/'worker1.jsonl').read_bytes()
        cls.events=life.parse(cls.raw);header=cls.events[0]['payload']
        cls.binding={'agent_path':header['agent_path'],'actor_native_id':header['id'],'parent_native_id':header['parent_thread_id']}
        cls.path=header['agent_path']+'/worker1'
        cls.delivery=next(i for i,e in enumerate(cls.events) if e['payload'].get('type')=='agent_message' and e['payload'].get('author')==cls.path)

    def invoke(self,events=None,children=None):
        return life.lifecycle(self.raw if events is None else encoded(events),self.binding,1,{self.path:self.child} if children is None else children)

    def test_actual_original_full_events_indexes_and_final_text_preserved(self):
        events,turns=self.invoke()
        self.assertEqual(events,self.events);self.assertEqual(len(turns),1)
        self.assertEqual(turns[0]['worker_deliveries'][0]['event_index'],self.delivery)
        self.assertEqual(turns[0]['worker_deliveries'][0]['native_sha256'],life.core.digest(self.child))
        with self.assertRaisesRegex(ValueError,'Incoming routing changed'):life.core.lifecycle(self.raw,self.binding,1)

    def test_original_solo_lifecycle_unchanged(self):
        raw=(ROOT/'runtime/native-optional-control-v7-solo/native-close/root.jsonl').read_bytes();header=life.parse(raw)[0]['payload']
        binding={'agent_path':header['agent_path'],'actor_native_id':header['id'],'parent_native_id':header['parent_thread_id']}
        self.assertEqual(life.lifecycle(raw,binding,1),life.core.lifecycle(raw,binding,1))

    def test_missing_or_invalid_child_sources_denied(self):
        for supplied in ({},[],False,{self.path:self.child[:-1]}):
            with self.assertRaises(ValueError):self.invoke(children=supplied)

    def test_foreign_sender_recipient_or_changed_body_denied(self):
        for field,value in [('author','/root/foreign'),('recipient','/root/foreign'),('content',[{'type':'input_text','text':'forged final'}])]:
            events=copy.deepcopy(self.events);events[self.delivery]['payload'][field]=value
            with self.assertRaises(ValueError):self.invoke(events)

    def test_new_turn_or_numeric_boolean_alias_or_missing_metadata_denied(self):
        for value in (True,0,1,None):
            events=copy.deepcopy(self.events);events[self.delivery-1]['payload']['trigger_turn']=value
            with self.assertRaises(ValueError):self.invoke(events)
        events=copy.deepcopy(self.events);events[self.delivery-1]['type']='event_msg'
        with self.assertRaises(ValueError):self.invoke(events)

    def test_replayed_or_missing_final_delivery_denied(self):
        events=copy.deepcopy(self.events);events[self.delivery+1:self.delivery+1]=copy.deepcopy(events[self.delivery-1:self.delivery+1])
        with self.assertRaises(ValueError):self.invoke(events)
        events=copy.deepcopy(self.events);del events[self.delivery-1:self.delivery+1]
        with self.assertRaises(ValueError):self.invoke(events)

    def test_delivery_before_child_completion_or_after_parent_final_denied(self):
        events=copy.deepcopy(self.events)
        for i in (self.delivery-1,self.delivery):events[i]['timestamp']='2026-10-12T05:43:10.000Z'
        with self.assertRaises(ValueError):self.invoke(events)
        events=copy.deepcopy(self.events);pair=events[self.delivery-1:self.delivery+1];del events[self.delivery-1:self.delivery+1]
        final=next(i for i,e in enumerate(events) if e['payload'].get('phase')=='final_answer')
        events[final+1:final+1]=pair
        with self.assertRaises(ValueError):self.invoke(events)

    def test_child_wrong_uuid_or_parent_and_unapproved_turn_denied(self):
        for field,value in [('parent_thread_id','wrong-parent'),('id',self.binding['actor_native_id'])]:
            child=life.parse(self.child);child[0]['payload'][field]=value
            with self.assertRaises(ValueError):self.invoke(children={self.path:encoded(child)})
        events=copy.deepcopy(self.events);events[self.delivery]['payload']['internal_chat_message_metadata_passthrough']['turn_id']='new-turn'
        with self.assertRaises(ValueError):self.invoke(events)

    def test_additional_user_request_inside_parent_or_child_turn_denied(self):
        extra={'timestamp':self.events[self.delivery]['timestamp'],'type':'response_item',
               'payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'new unapproved task'}]}}
        parent=copy.deepcopy(self.events);parent.insert(self.delivery+1,extra)
        with self.assertRaisesRegex(ValueError,'Unapproved user request'):self.invoke(parent)
        child=life.parse(self.child);incoming=next(i for i,e in enumerate(child) if e['payload'].get('type')=='agent_message')
        extra=copy.deepcopy(extra);extra["timestamp"]=child[incoming]["timestamp"]
        child.insert(incoming+1,extra)
        with self.assertRaisesRegex(ValueError,'Unapproved user request'):self.invoke(children={self.path:encoded(child)})

    def test_delivery_identity_and_clock_metadata_are_typed(self):
        events=copy.deepcopy(self.events);events[self.delivery]['payload']['id']=False
        with self.assertRaises(ValueError):self.invoke(events)
        for value in (False,0,float('inf')):
            events=copy.deepcopy(self.events);events[self.delivery]['payload']['internal_chat_message_metadata_passthrough']['create_time']=value
            with self.assertRaises(ValueError):self.invoke(events)

    def test_alternate_native_user_event_denied_in_parent_and_child(self):
        for kind in ('event_msg','response_item'):
            shape={'type':'user_message','message':'extra task'}
            parent=copy.deepcopy(self.events);parent.insert(self.delivery+1,{'timestamp':parent[self.delivery]['timestamp'],'type':kind,'payload':shape})
            with self.assertRaisesRegex(ValueError,'Unapproved user request'):self.invoke(parent)
            child=life.parse(self.child);incoming=next(i for i,e in enumerate(child) if e['payload'].get('type')=='agent_message')
            child.insert(incoming+1,{'timestamp':child[incoming]['timestamp'],'type':kind,'payload':shape})
            with self.assertRaisesRegex(ValueError,'Unapproved user request'):self.invoke(children={self.path:encoded(child)})

    def test_conflicting_top_level_and_native_delivery_turn_identity_denied(self):
        for altered in ('metadata','top_level'):
            events=copy.deepcopy(self.events);p=events[self.delivery]['payload'];native=p['internal_chat_message_metadata_passthrough']['turn_id']
            p['turn_id']=native if altered=='metadata' else 'unapproved-turn'
            if altered=='metadata':p['internal_chat_message_metadata_passthrough']['turn_id']='unapproved-turn'
            with self.assertRaisesRegex(ValueError,'Conflicting native turn identity'):self.invoke(events)
        events=copy.deepcopy(self.events);p=events[self.delivery]['payload'];p['turn_id']=p['internal_chat_message_metadata_passthrough']['turn_id']
        self.invoke(events)
        del p['internal_chat_message_metadata_passthrough']['turn_id']
        with self.assertRaises(ValueError):self.invoke(events)

    def test_all_lifecycle_turn_identity_fields_are_typed_and_consistent(self):
        for key,value in [('turn_id',False),('turn_id','another-turn')]:
            events=copy.deepcopy(self.events);final=next(e for e in events if e['payload'].get('phase')=='final_answer');final['payload'][key]=value
            with self.assertRaises(ValueError):self.invoke(events)


if __name__=='__main__':unittest.main()
