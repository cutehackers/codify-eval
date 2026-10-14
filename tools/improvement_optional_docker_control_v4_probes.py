"""Controller classification controls, all runtime operations mocked."""
import contextlib
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import improvement_optional_docker_control_v4 as control


class ClassificationControls(unittest.TestCase):
    def exercise(self,timeout_complete,late):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();case=root/'improvement_cases/fresh-optional-cohort-v1/O01'
            (case/'repo').mkdir(parents=True);(case/'public').mkdir()
            (root/'runtime').mkdir();(root/'results/improvement-v1').mkdir(parents=True)
            (case/'public/request.md').write_text('Pure fake controller fixture; no actors.')
            (case/'metadata.json').write_text(json.dumps({'editable_paths':['lib/a.dart','lib/b.dart','lib/c.dart'],'public_test_count':12}))
            clock=[100.0];state={'started_at':100.0,'deadline':1300.0,'jobs':{'root':{'status':'running'}}}
            def create(folder,*args):
                folder.mkdir();(folder/'state.json').write_text(json.dumps(state))
                return {'root_capability':'cap','run_id':'synthetic'}
            def command(folder,job,cap,text,**kwargs):
                if cap=='invalid-cap':raise ValueError('Denied before dispatch')
                if text=='exit 7':return {'exit_code':7,'output_complete':True}
                if text=='sleep 10':
                    result={'exit_code':124,'output_complete':timeout_complete}
                    if not timeout_complete:result['transport_error']={'type':'TimeoutError'}
                    return result
                return {'exit_code':0,'output_complete':True,'stdout':'mock closed protocol'}
            def cleanup(folder):
                clock[0]=1301.0 if late else 200.0
                return {'jobs':{'root':{'status':'removed'}}}
            with contextlib.ExitStack() as stack:
                for target,key,value in [(control,'ROOT',root),(control,'check',lambda:{}),
                         (control.runtime,'create',create),(control.runtime,'command',command),
                         (control.runtime,'snapshot',lambda *a,**k:{}),
                         (control.runtime,'cleanup',cleanup),(control.runtime,'failure',lambda *a:None),
                         (control,'machine',lambda *a:{'well_formed':True}),
                         (control.time,'time',lambda:clock[0])]:
                    stack.enter_context(patch.object(target,key,value))
                result=control.execute('solo')
            return result

    def test_later_review_cannot_mask_changed_runtime_review_pin(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);leaf=root/'leaf.py';leaf.write_text('changed current source')
            current=control.entity(leaf);prior={**current,'sha256':'0'*64}
            runtime_review=root/'runtime-review.json';driver_review=root/'driver-review.json'
            runtime_review.write_text(json.dumps({'verdict':'pass','issues':[],'source_entities':{'leaf.py':prior}}))
            driver_review.write_text(json.dumps({'verdict':'pass','issues':[],'source_entities':{'leaf.py':current}}))
            freeze=root/'freeze.json'
            with patch.object(control,'ROOT',root),patch.object(control,'REVIEW',runtime_review),patch.object(control,'DRIVER_REVIEW',driver_review),patch.object(control,'FREEZE',freeze):
                with self.assertRaisesRegex(ValueError,'Reviewed source'):control.freeze()
            self.assertFalse(freeze.exists())

    def test_transport_timeout_not_accepted_as_inner_command_timeout(self):
        result=self.exercise(False,False)
        self.assertFalse(result['dimension_pass']);self.assertIsNotNone(result['first_error'])
        self.assertTrue(result['owned_cleanup_verified'])

    def test_cleanup_after_original_deadline_denies_dimension_pass(self):
        result=self.exercise(True,True)
        self.assertFalse(result['dimension_pass']);self.assertTrue(result['time_limit_exceeded'])
        self.assertTrue(result['owned_cleanup_verified'])

    def test_complete_inner_timeout_and_within_budget_cleanup_only(self):
        result=self.exercise(True,False)
        self.assertTrue(result['dimension_pass']);self.assertFalse(result['time_limit_exceeded'])
        self.assertFalse(result['runtime_qualified']);self.assertFalse(result['comparison_eligible'])


if __name__=='__main__':unittest.main()
