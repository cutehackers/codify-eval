"""Decisive filesystem probes, not native/Docker/model qualification."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import subprocess
import sys

import improvement_software_artifacts_v2 as core


class IsolationIntegration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.base_repo = self.home / 'base'
        (self.base_repo / 'pkg').mkdir(parents=True)
        (self.base_repo / 'pkg/label.py').write_text('label = None\n')
        (self.base_repo / 'pkg/quantity.py').write_text('quantity = None\n')
        (self.base_repo / 'public.txt').write_text('protected\n')
        self.base = core.freeze_base(self.base_repo, {'label': 'pkg/label.py', 'quantity': 'pkg/quantity.py'})
        self.root = self.home / 'root'
        shutil.copytree(self.base_repo, self.root)
        self.workers = {}
        for job, path in self.base['scopes'].items():
            worker = self.home / job
            shutil.copytree(self.base_repo, worker)
            (worker / path).write_text(job + ' = "contribution"\n')
            self.workers[job] = worker
        self.journal = self.home / 'journal'

    def tearDown(self):
        self.temp.cleanup()

    def decisions(self):
        result = {}
        for job, worker in self.workers.items():
            row = core.seal_worker(self.base, worker, job, self.home / 'artifacts' / (job + '.json'))
            result[job] = {**row, 'decision': 'accept', 'reason': 'Public module contract reviewed'}
        return result

    def test_two_isolated_contributions_protected_root_and_permissions(self):
        decisions = self.decisions()
        self.assertEqual(core.tree(self.root), self.base['files'])
        self.assertEqual((self.workers['label'] / 'pkg/quantity.py').read_bytes(), (self.base_repo / 'pkg/quantity.py').read_bytes())
        result = core.integrate(self.root, self.base, decisions, self.journal)
        intent = json.loads(result.read_bytes())
        self.assertEqual(core.tree(self.root), intent['expected_after'])
        self.assertEqual((self.root / 'public.txt').read_text(), 'protected\n')
        self.assertFalse(intent['native_binding_qualified'])
        self.assertFalse(intent['root_verification_qualified'])

    def test_protected_worker_mutation_rejected(self):
        (self.workers['label'] / 'public.txt').write_text('bad')
        with self.assertRaises(AssertionError):
            self.decisions()
        self.assertEqual(core.tree(self.root), self.base['files'])

    def test_empty_directory_addition_rejected(self):
        (self.workers['label'] / 'unowned').mkdir()
        with self.assertRaises(AssertionError):
            self.decisions()

    def test_symlink_worker_artifact_rejected(self):
        target = self.workers['label'] / 'pkg/label.py'
        target.unlink()
        target.symlink_to(self.base_repo / 'pkg/label.py')
        with self.assertRaises(AssertionError):
            self.decisions()

    def test_permission_mutation_rejected(self):
        (self.workers['label'] / 'pkg/label.py').chmod(0o777)
        with self.assertRaises(AssertionError):
            self.decisions()

    def test_payload_tampering_rejected_before_copy(self):
        decisions = self.decisions()
        path = Path(decisions['label']['artifact'])
        path.write_bytes(path.read_bytes() + b' ')
        with self.assertRaises(AssertionError):
            core.integrate(self.root, self.base, decisions, self.journal)
        self.assertEqual(core.tree(self.root), self.base['files'])

    def test_root_drift_rejected_before_copy(self):
        decisions = self.decisions()
        (self.root / 'public.txt').write_text('unexpected')
        before = core.tree(self.root)
        with self.assertRaises(AssertionError):
            core.integrate(self.root, self.base, decisions, self.journal)
        self.assertEqual(core.tree(self.root), before)

    def test_overlap_rejected_before_copy(self):
        decisions = self.decisions()
        base = copy.deepcopy(self.base)
        base['scopes']['quantity'] = 'pkg/label.py'
        with self.assertRaises(AssertionError):
            core.integrate(self.root, base, decisions, self.journal)
        self.assertEqual(core.tree(self.root), self.base['files'])

    def test_rejected_decision_cannot_integrate(self):
        decisions = self.decisions()
        decisions['quantity']['decision'] = 'reject'
        with self.assertRaises(AssertionError):
            core.integrate(self.root, self.base, decisions, self.journal)
        self.assertEqual(core.tree(self.root), self.base['files'])

    def test_interrupted_copy_retains_error_and_recovers_exact_bytes(self):
        decisions = self.decisions()
        def fail(index, name):
            raise OSError('injected after first rename')
        with self.assertRaises(OSError):
            core.integrate(self.root, self.base, decisions, self.journal, fail)
        transaction, = self.journal.glob('*.json')
        original = json.loads(transaction.read_bytes())
        self.assertEqual(original['state'], 'partial_integration')
        self.assertEqual((self.root / 'pkg/label.py').read_text(), 'label = "contribution"\n')
        self.assertEqual((self.root / 'pkg/quantity.py').read_text(), 'quantity = None\n')
        core.recover(self.root, transaction)
        recovered = json.loads(transaction.read_bytes())
        self.assertEqual(recovered['first_error'], original['first_error'])
        self.assertEqual(core.tree(self.root), recovered['expected_after'])
        self.assertFalse(recovered['superiority_proven'])

    def test_interrupted_intent_not_mistaken_for_completion(self):
        decisions = self.decisions()
        def fail(index, name):
            raise OSError('simulate process interruption')
        with self.assertRaises(OSError):
            core.integrate(self.root, self.base, decisions, self.journal, fail)
        transaction, = self.journal.glob('*.json')
        intent = json.loads(transaction.read_bytes())
        intent['state'] = 'intent'
        intent.pop('first_error')
        core.atomic_json(transaction, intent)
        core.recover(self.root, transaction)
        recovered = json.loads(transaction.read_bytes())
        self.assertTrue(recovered['interrupted_intent_observed'])
        self.assertEqual(core.tree(self.root), recovered['expected_after'])

    def test_unexpected_partial_root_bytes_block_recovery(self):
        decisions = self.decisions()
        def fail(index, name):
            raise OSError('partial')
        with self.assertRaises(OSError):
            core.integrate(self.root, self.base, decisions, self.journal, fail)
        transaction, = self.journal.glob('*.json')
        (self.root / 'pkg/quantity.py').write_text('unowned drift')
        before = core.tree(self.root)
        with self.assertRaises(AssertionError):
            core.recover(self.root, transaction)
        self.assertEqual(core.tree(self.root), before)

    def test_real_process_exit_before_rename_recovers_registered_stage(self):
        decisions = self.decisions()
        request = self.home / 'crash-input.json'
        request.write_text(json.dumps({'repo': str(self.root), 'base': self.base, 'decisions': decisions, 'journal': str(self.journal)}))
        code = "import json,os,sys;sys.path.insert(0,sys.argv[2]);import improvement_software_artifacts_v2 as c;d=json.load(open(sys.argv[1]));c.integrate(d['repo'],d['base'],d['decisions'],d['journal'],after_stage=lambda *args:os._exit(23))"
        proc = subprocess.run([sys.executable, '-B', '-c', code, str(request), str(Path(__file__).resolve().parent)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 23, proc.stderr)
        transaction, = self.journal.glob('*.json')
        intent = json.loads(transaction.read_bytes())
        self.assertEqual(intent['state'], 'intent')
        self.assertEqual((self.root / 'pkg/label.py').read_text(), 'label = None\n')
        stage = self.root / intent['staging_paths']['pkg/label.py']
        self.assertTrue(stage.is_file())
        core.recover(self.root, transaction)
        recovered = json.loads(transaction.read_bytes())
        self.assertEqual(core.tree(self.root), recovered['expected_after'])
        self.assertFalse(stage.exists())
        self.assertEqual(len(recovered['recovery_attempts'][0]['registered_staging_to_remove']), 1)

    def test_tampered_registered_stage_is_retained_and_rejected(self):
        decisions = self.decisions()
        def fail(index, name):
            raise OSError('partial')
        with self.assertRaises(OSError):
            core.integrate(self.root, self.base, decisions, self.journal, fail)
        transaction, = self.journal.glob('*.json')
        intent = json.loads(transaction.read_bytes())
        stage = self.root / intent['staging_paths']['pkg/quantity.py']
        stage.write_text('malicious content')
        before = core.tree(self.root)
        with self.assertRaises(AssertionError):
            core.recover(self.root, transaction)
        self.assertEqual(core.tree(self.root), before)


if __name__ == '__main__':
    unittest.main()
