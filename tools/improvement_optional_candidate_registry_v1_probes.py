import tempfile
import time
import subprocess
import sys
from pathlib import Path
import unittest

import improvement_optional_candidate_registry_v1 as adapter


class CandidateRegistry(unittest.TestCase):
    def setUp(self):
        self.tree = {'.': {'kind': 'directory', 'mode': 0o755}}
        self.paths = ['a.dart', 'b.dart', 'c.dart']
        self.tree.update({p: {'kind': 'file', 'mode': 0o644, 'sha256': '0' * 64}
                          for p in self.paths})

    def test_new_condition_replays_with_original_registry_and_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'ledger'
            state = adapter.create(folder, 'fresh-C17', 'O01', 'C17',
                                   time.time() - 1, self.tree, self.paths)
            config = state['configuration']
            self.assertEqual(config['condition'], 'C17')
            self.assertEqual(config['deadline'], config['started_at'] + 1200)
            adapter.registry.reserve_worker(folder, 'first', ['a.dart'], self.tree)
            adapter.registry.reserve_worker(folder, 'second', ['b.dart'], self.tree)
            with self.assertRaises(ValueError):
                adapter.registry.reserve_worker(folder, 'third', ['c.dart'], self.tree)
            self.assertEqual(len(adapter.registry.read(folder)['workers']), 2)
            with self.assertRaises(FileExistsError):
                adapter.create(folder, 'fresh-C17', 'O01', 'C17',
                               time.time() - 1, self.tree, self.paths)

    def test_original_creation_unchanged_and_hook_restores(self):
        original = adapter.runtime.registry.create
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                original(Path(tmp) / 'original', 'original', 'O01', 'C17',
                         time.time() - 1, self.tree, self.paths)
            self.assertFalse((Path(tmp) / 'original').exists())
        with adapter.creation_hook():
            self.assertIs(adapter.runtime.registry.create, adapter.create)
        self.assertIs(adapter.runtime.registry.create, original)
        with self.assertRaises(RuntimeError):
            with adapter.creation_hook():
                raise RuntimeError('prospective preparation failure')
        self.assertIs(adapter.runtime.registry.create, original)

    def test_actual_mixed_version_subprocess_readers_accept_c17(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'ledger'
            adapter.create(folder, 'subprocess-C17', 'O02', 'C17',
                           time.time() - 1, self.tree, self.paths)
            code = (
                'import importlib,sys; '
                'm=importlib.import_module(sys.argv[1]); '
                'r=getattr(m,"runtime",m); '
                's=r.registry.read(sys.argv[2]); '
                'assert s["configuration"]["condition"]=="C17"; '
                'assert s["configuration"]["worker_cap"]==2; '
                'assert s["configuration"]["retries"]==0'
            )
            for module in ('improvement_optional_broker_v10',
                           'improvement_optional_broker_v6',
                           'improvement_optional_runtime_v10'):
                result = subprocess.run([sys.executable, '-c', code, module, str(folder)],
                                        capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_invalid_identity_clock_scope_denied_before_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            for case, condition, started, paths in [
                ('O03', 'C17', time.time() - 1, self.paths),
                ('O01', 'C16', time.time() - 1, self.paths),
                ('O01', 'C17', True, self.paths),
                ('O01', 'C17', time.time() - 1, ['a.dart'] * 3),
            ]:
                folder = Path(tmp) / 'denied'
                with self.assertRaises(ValueError):
                    adapter.create(folder, 'denied', case, condition, started,
                                   self.tree, paths)
                self.assertFalse(folder.exists())


if __name__ == '__main__':
    unittest.main()
