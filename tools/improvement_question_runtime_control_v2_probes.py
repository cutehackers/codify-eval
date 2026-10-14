"""Frozen control allocator schema/prospective isolation probes; no allocation."""
from copy import deepcopy
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
import improvement_question_runtime_control_v2 as control


class Probes(unittest.TestCase):
    def value(self):
        return {'source_entities':{'source.py':{'kind':'file','mode':420,'sha256':'fixed'}}, 'source_hashes':{'source.py':'fixed'},
                'case_entities':{'Q05':{},'Q06':{}}, 'allocation_mode':'runtime_qualification_control','adaptive_runtime_qualified':False,
                'comparison_eligible':False,'primary_confirmation_reuse_allowed':False,'superiority_proven':False,
                'model':'gpt-6.1-sol','effort':'medium','trajectory_seconds':1200,'actor_cap':1,
                'concurrency':1,'retries':0,'image_id':'fixed','conditions':['A'],'skill_hashes':{},
                'sequence':[{'case_id':case,'condition':'A','repeat':1,'run_id':f'{control.PHASE}-{case}-A-1'} for case in control.CASES]}

    def checked(self, value):
        with patch.object(control.legacy.prior,'check',return_value=value), patch.object(control.legacy,'read',return_value={'image_id':'fixed'}), patch.object(control,'entity',return_value={'kind':'file','mode':420,'sha256':'fixed'}), patch.object(control,'case_entities',return_value={}):
            return control.configure()

    def test_controls_remain_unqualified_and_noncomparative(self):
        value=self.checked(self.value())
        self.assertIs(value['adaptive_runtime_qualified'],False)
        self.assertEqual(value['conditions'],['A'])

    def test_false_qualification_and_candidate_or_gate_changes_rejected(self):
        for key,value in [('adaptive_runtime_qualified',True),('comparison_eligible',True),('conditions',['A','C16']),
                          ('trajectory_seconds',60),('model','deliberately-invalid-control'),('effort','high'),
                          ('allocation_mode','comparison'),('retries',1),('actor_cap',2),('actor_cap',True),('concurrency',True),('trajectory_seconds',1200.0),('retries',False),('superiority_proven',True)]:
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

    def test_mode_only_and_kind_changes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source';path.write_text('same bytes')
            before=control.entity(path);path.chmod(0o600)
            self.assertNotEqual(control.entity(path),before)
            link=Path(directory)/'link';link.symlink_to(path)
            with self.assertRaises(AssertionError):control.entity(link)

    def test_nonempty_review_pin_coverage_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.py';source.write_text('same')
            review=root/'review.json';names=set()
            with patch.object(control,'ROOT',root):
                review.write_text(json.dumps({'verdict':'PASS','issues':[]}))
                with self.assertRaises(AssertionError):control.check_review(review,names,required=[source])
                review.write_text(json.dumps({'verdict':'PASS','issues':[],'source_hashes':{'source.py':control.legacy.sha(source)}}))
                control.check_review(review,names,required=[source])
                with self.assertRaises(AssertionError):control.check_review(review,names,required=[root/'missing.py'])

    def test_case_directory_entity_mode_changes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'lib').mkdir();(root/'lib/source.dart').write_text('same')
            with patch.object(control.pilot,'case_directory',return_value=root):
                before=control.case_entities('Q05');(root/'lib').chmod(0o700)
                self.assertNotEqual(control.case_entities('Q05'),before)
                (root/'link').symlink_to(root/'lib/source.dart')
                with self.assertRaises(AssertionError):control.case_entities('Q05')

if __name__=='__main__':unittest.main()
