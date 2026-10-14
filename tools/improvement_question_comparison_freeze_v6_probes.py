"""Preregistered development matrix and exact policy negatives; no allocation."""
from copy import deepcopy
import unittest
from unittest.mock import patch
import improvement_question_comparison_freeze_v6 as freeze

class Probes(unittest.TestCase):
    def value(self):
        return {'model':'gpt-6.1-sol','effort':'medium','trajectory_seconds':1200,'actor_cap':1,'concurrency':1,'retries':0,'conditions':['A','C0','C16'],'cases':['Q05','Q06'],'repeats':3,'allocation_seed':610612,'sequence':freeze.sequence(),'allocation_mode':'development_comparison','adaptive_runtime_qualified':True,'primary_confirmation_reuse_allowed':False,'superiority_proven':False}

    def test_balanced_original_matrix_and_stable_order(self):
        rows=freeze.sequence();self.assertEqual(rows,freeze.sequence());self.assertEqual(len(rows),18);self.assertEqual(len({r['run_id'] for r in rows}),18)
        self.assertEqual({(r['case_id'],r['condition'],r['repeat']) for r in rows},{(case,condition,repeat) for case in freeze.CASES for condition in freeze.CONDITIONS for repeat in (1,2,3)})
        freeze.policy(self.value())

    def test_aliases_and_unapproved_caps_conditions_rejected(self):
        for key,value in [('actor_cap',True),('repeats',3.0),('trajectory_seconds',1200.0),('retries',False),('effort','high'),('conditions',['A','C16']),('superiority_proven',True),('adaptive_runtime_qualified',1)]:
            row=self.value();row[key]=value
            with self.subTest(key=key),self.assertRaises(AssertionError):freeze.policy(row)

    def test_no_reordering_duplicate_or_repeat_alias(self):
        for change in ('order','duplicate','repeat'):
            row=deepcopy(self.value())
            if change=='order':row['sequence'].reverse()
            elif change=='duplicate':row['sequence'][1]=row['sequence'][0]
            else:row['sequence'][0]['repeat']=1.0
            with self.subTest(change=change),self.assertRaises(AssertionError):freeze.policy(row)

    def test_complete_admission_set_and_hash_agreement(self):
        row=self.value()
        entity={'kind':'file','mode':420,'bytes':7,'sha256':'a'*64}
        row.update(status='frozen',stage='exposed development comparison',image_id='fixed',
            failure_retention='All18 original allocations retained; non-infrastructure failures never rerun or excluded',
            case_entities={case:{} for case in freeze.CASES},case_hashes={case:'case' for case in freeze.CASES},
            skill_entities={c:{} for c in ('C0','C16')},skill_hashes={c:'skill' for c in ('C0','C16')},
            source_entities={'admission.json':entity},source_hashes={'admission.json':'a'*64})
        with patch.object(freeze,'reviewed_sources',return_value={freeze.ROOT/'admission.json'}), \
             patch.object(freeze.formats,'entity',return_value=entity), \
             patch.object(freeze,'case_entities',return_value={}), \
             patch.object(freeze.source,'inventory',return_value={}), \
             patch.object(freeze.pilot.legacy,'read',return_value={'image_id':'fixed'}):
            freeze.checked(row)
            for kind in ('missing','digest','image','retention'):
                changed=deepcopy(row)
                if kind=='missing':changed['source_entities']={};changed['source_hashes']={}
                elif kind=='digest':changed['source_hashes']['admission.json']='b'*64
                elif kind=='image':changed['image_id']='other'
                else:changed['failure_retention']='drop failed runs'
                with self.subTest(kind=kind),self.assertRaises(AssertionError):freeze.checked(changed)

if __name__=='__main__':unittest.main()
