"""Development repeat admission before owned effects; no native or Docker runs."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import improvement_question_failure_close_v4 as closer
import improvement_question_deadline_close_v2 as deadline

class Probes(unittest.TestCase):
    def admission(self,repeat):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);run=f'{closer.PHASE}-Q05-C16-{repeat}';folder=root/'runtime'/run;folder.mkdir(parents=True);out=root/'results'/run;out.mkdir(parents=True)
            meta={'run_id':run,'case_id':'Q05','condition':'C16','repeat':repeat,'phase':closer.PHASE,'model':'gpt-6.1-sol','effort':'medium','image_id':closer.IMAGE,'container':'codify-'+run.lower(),'started_at':100}
            (folder/'run.json').write_text(json.dumps(meta));(out/'launch-intent.json').write_text(json.dumps({'run_id':run,'started_at':100}))
            with patch.object(closer,'ROOT',root),patch.object(closer.legacy,'owned_identity',return_value={}) as owner:
                if type(repeat) is int and 1<=repeat<=3:
                    self.assertEqual(closer.allocated_paths(run)[2],meta);owner.assert_called_once()
                else:
                    with self.assertRaises(AssertionError):closer.allocated_paths(run)
                    owner.assert_not_called()

    def test_all_registered_repeats_admitted(self):
        for repeat in (1,2,3):self.admission(repeat)

    def test_aliases_and_unregistered_repeats_rejected(self):
        for repeat in (True,1.0,0,4):self.admission(repeat)

    def test_deadline_reuses_exact_new_failure_owner_module(self):
        self.assertIs(deadline.normal,closer)
        self.assertEqual(deadline.PHASE,closer.PHASE)

if __name__=='__main__':unittest.main()
