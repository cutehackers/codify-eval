"""Report-field qualification using original v6 evidence, not actor reruns."""
import copy,hashlib,json,unittest
from pathlib import Path
from unittest.mock import patch
import improvement_software_broker_v7 as b
ROOT=b.ROOT
FOLDER=ROOT/'runtime/protocol-probes/software-broker-v6-actual-1'
OUT=ROOT/'results/improvement-v1/software-broker-v7-report-probes.json'
class Reports(unittest.TestCase):
    def setUp(self):self.state=b.load(FOLDER)
    def test_actual_label_origin_scope(self):
        v=b.sealed_view(FOLDER,self.state,'label')
        self.assertEqual(v['changed_paths'],['pkg/label.py']);self.assertTrue(v['protected_entities_unchanged'])
        self.assertEqual(len(v['base_tree_sha256']),64)
    def test_actual_quantity_origin_scope(self):
        v=b.sealed_view(FOLDER,self.state,'quantity')
        self.assertEqual(v['changed_paths'],['pkg/quantity.py']);self.assertTrue(v['worker_native_id'])
    def test_protected_mutation_rejected(self):
        tree=b.artifacts.tree(FOLDER/'label/repo');tree['pkg/api.py']['sha256']='0'*64
        with patch.object(b.artifacts,'tree',return_value=tree):
            with self.assertRaises(ValueError):b.sealed_view(FOLDER,self.state,'label')
    def test_allowed_payload_mutation_rejected(self):
        tree=b.artifacts.tree(FOLDER/'label/repo');tree['pkg/label.py']['sha256']='0'*64
        with patch.object(b.artifacts,'tree',return_value=tree):
            with self.assertRaises(ValueError):b.sealed_view(FOLDER,self.state,'label')
    def test_seal_manifest_mutation_rejected(self):
        with patch.object(b,'sha',return_value='0'*64):
            with self.assertRaises(ValueError):b.sealed_view(FOLDER,self.state,'label')
    def test_actual_verifier_argv(self):
        result=next(a['result'] for a in self.state['actions'] if a['request']['op']=='verify')
        v=b.verification_view(result)
        self.assertEqual(v['executed_argv'],['/usr/bin/python3','-I','-B','-m','unittest','discover','-s','tests','-t','.','-v'])
        self.assertIn('PYTHONDONTWRITEBYTECODE=1',v['verifier_environment'])
        self.assertEqual(v['exit_code'],0)
if __name__=='__main__':
    assert not OUT.exists()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Reports))
    paths=[Path(__file__),ROOT/'tools/improvement_software_broker_v7.py',ROOT/'tools/improvement_software_broker_native_v7.py',FOLDER/'broker-state.json',FOLDER/'configuration.json']
    with OUT.open('x') as f:json.dump({'status':'pass' if result.wasSuccessful() else 'fail','tests':result.testsRun,'errors':[(str(t),s) for t,s in result.errors],'failures':[(str(t),s) for t,s in result.failures],'actual_v7_actor_qualified':False,'original_v6_report_promoted':False,'superiority_proven':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}},f,indent=2)
    raise SystemExit(0 if result.wasSuccessful() else 1)
