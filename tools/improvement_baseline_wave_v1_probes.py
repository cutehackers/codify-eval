"""Allocation order and evidence gating probes; no model or Docker work."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import improvement_baseline_wave_v1 as wave
OUT=wave.ROOT/'results/improvement-v1/baseline-wave-order-probes-v1.json'
class Order(unittest.TestCase):
    def frozen(self):return {'sequence':wave.SEQUENCE}
    def mark(self,root,row,review=None):
        p=root/'results'/row['run_id'];p.mkdir(parents=True);(p/'grade.json').write_text('{"status":"fail"}')
        if review is not None:
            p=root/row['outcome_review'];p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(review))
    def test_skip_first_allocation_denied_before_docker(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(wave,'ROOT',Path(tmp)),patch.object(wave,'configure',return_value=self.frozen()),patch.object(wave.subprocess,'check_output') as docker:
            with self.assertRaises(AssertionError):wave.launch(wave.SEQUENCE[1]['run_id'])
            docker.assert_not_called()
    def test_restarting_graded_original_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.mark(root,wave.SEQUENCE[0],{'run_id':wave.SEQUENCE[0]['run_id'],'verdict':'fail'})
            with patch.object(wave,'ROOT',root),patch.object(wave,'configure',return_value=self.frozen()),patch.object(wave.subprocess,'check_output') as docker:
                with self.assertRaises(AssertionError):wave.launch(wave.SEQUENCE[0]['run_id'])
                docker.assert_not_called()
    def test_previous_review_missing_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.mark(root,wave.SEQUENCE[0])
            with patch.object(wave,'ROOT',root),patch.object(wave,'configure',return_value=self.frozen()),patch.object(wave.subprocess,'check_output') as docker:
                with self.assertRaises(ValueError):wave.launch(wave.SEQUENCE[1]['run_id'])
                docker.assert_not_called()
    def test_wrong_run_review_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.mark(root,wave.SEQUENCE[0],{'run_id':'other-run'})
            with patch.object(wave,'ROOT',root),patch.object(wave,'configure',return_value=self.frozen()),patch.object(wave.subprocess,'check_output') as docker:
                with self.assertRaises(AssertionError):wave.launch(wave.SEQUENCE[1]['run_id'])
                docker.assert_not_called()
if __name__=='__main__':
    assert not OUT.exists()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Order))
    paths=[Path(__file__),wave.ROOT/'tools/improvement_baseline_wave_v1.py']
    with OUT.open('x') as f:json.dump({'status':'pass' if result.wasSuccessful() else 'fail','tests':result.testsRun,'errors':[(str(t),s) for t,s in result.errors],'failures':[(str(t),s) for t,s in result.failures],'actual_allocation_qualified':False,'superiority_proven':False,'source_hashes':{str(p.relative_to(wave.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}},f,indent=2)
    raise SystemExit(0 if result.wasSuccessful() else 1)
