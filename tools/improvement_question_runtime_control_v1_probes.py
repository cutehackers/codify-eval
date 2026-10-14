"""Frozen control allocator schema/prospective isolation probes; no allocation."""
from copy import deepcopy
import unittest
from unittest.mock import patch
import improvement_question_runtime_control_v1 as control


class Probes(unittest.TestCase):
    def value(self):
        return {'allocation_mode':'runtime_qualification_control','adaptive_runtime_qualified':False,
                'comparison_eligible':False,'primary_confirmation_reuse_allowed':False,'superiority_proven':False,
                'model':'gpt-6.1-sol','effort':'medium','trajectory_seconds':1200,'actor_cap':1,
                'concurrency':1,'retries':0,'image_id':'fixed','conditions':['A'],'skill_hashes':{},
                'sequence':[{'case_id':case,'condition':'A','repeat':1,'run_id':f'{control.PHASE}-{case}-A-1'} for case in control.CASES]}

    def checked(self, value):
        with patch.object(control.legacy.prior,'check',return_value=value), patch.object(control.legacy,'read',return_value={'image_id':'fixed'}):
            return control.configure()

    def test_controls_remain_unqualified_and_noncomparative(self):
        value=self.checked(self.value())
        self.assertIs(value['adaptive_runtime_qualified'],False)
        self.assertEqual(value['conditions'],['A'])

    def test_false_qualification_and_candidate_or_gate_changes_rejected(self):
        for key,value in [('adaptive_runtime_qualified',True),('comparison_eligible',True),('conditions',['A','C16']),
                          ('trajectory_seconds',60),('model','deliberately-invalid-control'),('effort','high'),
                          ('allocation_mode','comparison'),('retries',1),('actor_cap',2),('superiority_proven',True)]:
            changed=deepcopy(self.value());changed[key]=value
            with self.subTest(key=key),self.assertRaises(AssertionError):self.checked(changed)

    def test_reordered_or_extra_allocations_rejected(self):
        changed=self.value();changed['sequence'].reverse()
        with self.assertRaises(AssertionError):self.checked(changed)
        changed=self.value();changed['sequence'].append(deepcopy(changed['sequence'][0]))
        with self.assertRaises(AssertionError):self.checked(changed)

    def test_missing_freeze_does_not_bootstrap_qualification(self):
        with patch.object(control.legacy.prior,'check',side_effect=FileNotFoundError('prospective freeze required')):
            with self.assertRaises(FileNotFoundError):control.configure()

if __name__=='__main__':unittest.main()
