"""Actual approved two-turn regressions and counterfeit input negatives; no actors."""
import json
from pathlib import Path
import unittest
from copy import deepcopy
import improvement_question_lifecycle_v1 as lifecycle

ROOT=Path(__file__).resolve().parents[1]

class Probes(unittest.TestCase):
    def source(self,case):
        folder=ROOT/'results'/f'control-probe-natural-question-runtime-v2-{case}-A-1'
        b=json.loads((folder/'actor-binding.json').read_bytes())
        binding={'actor_native_id':b['native_session_id'],'agent_path':b['agent_path'],'parent_native_id':b['parent_thread_id']}
        raw=(folder/'terminal-native.jsonl').read_bytes()
        return raw,binding

    def altered(self,events):
        return b''.join((json.dumps(e)+'\n').encode() for e in events)

    def test_two_original_approved_dialogues_remain_valid(self):
        for case in ('Q05','Q06'):
            with self.subTest(case=case):
                raw,binding=self.source(case)
                events,turns=lifecycle.lifecycle(raw,binding,2)
                self.assertEqual(len(turns),2)
                self.assertEqual(events,lifecycle.parse(raw))

    def test_unapproved_user_frames_after_second_delivery_rejected(self):
        for case in ('Q05','Q06'):
            raw,binding=self.source(case);events,turns=lifecycle.lifecycle(raw,binding,2)
            at=turns[1]['incoming_index']+1
            for payload in ({'type':'user_message','message':'unapproved'}, {'type':'message','role':'user','content':[{'type':'input_text','text':'unapproved'}]}):
                with self.subTest(case=case,payload=payload['type']):
                    changed=deepcopy(events);changed.insert(at,{'timestamp':changed[at-1]['timestamp'],'type':'event_msg' if payload['type']=='user_message' else 'response_item','payload':payload})
                    with self.assertRaisesRegex(ValueError,'Unapproved user input'):
                        lifecycle.lifecycle(self.altered(changed),binding,2)

    def test_conflicting_native_turn_aliases_rejected(self):
        for case in ('Q05','Q06'):
            raw,binding=self.source(case);events,turns=lifecycle.lifecycle(raw,binding,2)
            for t in turns:
                with self.subTest(case=case,turn=t['turn_id']):
                    changed=deepcopy(events);p=changed[t['incoming_index']]['payload'];p['turn_id']=t['turn_id'];p['internal_chat_message_metadata_passthrough']['turn_id']='unapproved-conflict'
                    with self.assertRaisesRegex(ValueError,'Conflicting native turn identity'):
                        lifecycle.lifecycle(self.altered(changed),binding,2)

    def test_empty_or_nonstring_aliases_rejected(self):
        for value in ('',True,1,None):
            with self.subTest(value=value),self.assertRaises(ValueError):
                lifecycle.turn_id({'turn_id':'approved','internal_chat_message_metadata_passthrough':{'turn_id':value}})

    def test_only_typed_one_or_two_turns_allowed(self):
        raw,binding=self.source('Q05')
        for count in (True,2.0,3):
            with self.subTest(count=count),self.assertRaisesRegex(ValueError,'Unsupported turn count'):
                lifecycle.lifecycle(raw,binding,count)

if __name__=='__main__':unittest.main()
