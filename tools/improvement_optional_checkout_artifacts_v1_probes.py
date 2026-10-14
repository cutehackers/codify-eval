"""Raw checkout transaction and real process-death controls, no Docker/model."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import improvement_optional_checkout_artifacts_v1 as checkout


class CheckoutControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name); self.repo = self.base / 'root'; (self.repo / 'lib').mkdir(parents=True)
        for name in ('a', 'b', 'c', 'models'): (self.repo / f'lib/{name}.dart').write_text(name + ' old\n')
        (self.repo / 'test').mkdir(); (self.repo / 'test/contract.dart').write_text('public tests\n')
        (self.repo / 'pubspec.lock').write_text('prepared lock\n')
        (self.repo / '.git').mkdir(); (self.repo / '.git/HEAD').write_text('protected ref\n')
        (self.repo / '.dart_tool').mkdir(); (self.repo / '.dart_tool/kernel').write_bytes(b'x' * (2 * 1024 * 1024))
        (self.repo / 'build').mkdir(); (self.repo / 'build/artifact').write_bytes(b'generated\n')
        self.baseline = checkout.source.inventory(self.repo); self.registry = self.base / 'registry'
        checkout.registry.create(self.registry, 'probe', 'O01', 'A', time.time(), self.baseline['source_entities'],
                                 ['lib/a.dart', 'lib/b.dart', 'lib/c.dart'])
        self.out = self.base / 'artifacts'; self.out.mkdir(); self.journal = self.base / 'journal'

    def contribution(self, scope, changes=None, decision='accept', mode='write', findings=''):
        state = checkout.registry.reserve_worker(self.registry, 'public task', scope,
                                                checkout.source.inventory(self.repo)['source_entities'], mode)
        slot = list(state['workers'])[-1]; worker = self.base / slot; shutil.copytree(self.repo, worker)
        baseline = checkout.source.inventory(worker)
        for name, raw in (changes or {}).items(): (worker / name).write_bytes(raw)
        sealed = checkout.seal_checkout(worker, state, slot, baseline, self.out / (slot + '-export'),
                                        self.out / (slot + '-seal.json'), findings)
        view, _ = checkout.artifacts.view(state, sealed['artifact'], self.out / (slot + '-view.json'))
        choice = checkout.artifacts.decide(state, sealed['artifact'], view, decision, 'original reason',
                                          self.registry / 'decisions' / (slot + '.json'), registry_folder=self.registry)
        return state, choice, worker, baseline, sealed

    def install(self, state, choices, **kwargs):
        return checkout.install(self.repo, state, choices, self.baseline, checkout.source.inventory(self.repo),
                                self.journal, self.registry, **kwargs)

    def test_solo_preserves_full_raw_checkout_and_holds_qualification(self):
        path = self.install(checkout.registry.read(self.registry), [])
        self.assertEqual(checkout.source.inventory(self.repo), self.baseline)
        value = json.loads(path.read_bytes()); self.assertEqual(value['after_payloads'], {})
        self.assertFalse(value['leases_released']); self.assertFalse(value['native_qualified'])

    def test_multi_file_contribution_keeps_unleased_root_edit_and_large_cache_git(self):
        state, choice, _, _, sealed = self.contribution(['lib/a.dart', 'lib/b.dart'],
                                                       {'lib/a.dart': b'a new\n', 'lib/b.dart': b'b new\n'})
        (self.repo / 'lib/c.dart').write_text('root own change\n')
        before = checkout.source.inventory(self.repo)
        path = self.install(state, [choice]); value = json.loads(path.read_bytes())
        self.assertEqual((self.repo / 'lib/c.dart').read_text(), 'root own change\n')
        self.assertEqual((self.repo / 'lib/a.dart').read_bytes(), b'a new\n')
        self.assertEqual(checkout.source.inventory(self.repo), value['expected_after_inventory'])
        self.assertEqual(checkout.source.inventory(self.repo)['git_entities'], before['git_entities'])
        self.assertFalse((Path(sealed['export']) / '.dart_tool').exists())

    def test_accept_reject_and_readonly_review_all_need_original_decisions(self):
        _, accepted, _, _, _ = self.contribution(['lib/a.dart'], {'lib/a.dart': b'accepted'})
        state, rejected, _, _, _ = self.contribution([], mode='review', findings='Review public permissions.', decision='reject')
        path = self.install(state, [accepted, rejected]); value = json.loads(path.read_bytes())
        self.assertEqual(len(value['decisions']), 2); self.assertEqual((self.repo / 'lib/a.dart').read_bytes(), b'accepted')

    def test_all_rejected_and_noop_do_not_change_any_raw_entity(self):
        _, rejected, _, _, _ = self.contribution(['lib/a.dart'], {'lib/a.dart': b'rejected'}, decision='reject')
        state, noop, _, _, _ = self.contribution(['lib/b.dart'])
        self.install(state, [rejected, noop]); self.assertEqual(checkout.source.inventory(self.repo), self.baseline)

    def test_worker_protected_source_git_modes_and_nested_generated_names_denied(self):
        state, _, worker, baseline, _ = self.contribution(['lib/a.dart'])
        for name in ('test/contract.dart', 'pubspec.lock', '.git/HEAD'):
            path = worker / name; original = path.read_bytes(); path.write_bytes(b'tampered')
            with self.assertRaises(ValueError): checkout.seal_checkout(worker, state, 'worker1', baseline, self.out / 'bad-export', self.out / 'bad-seal')
            path.write_bytes(original)
        (worker / 'lib/build').mkdir(); (worker / 'lib/build/hidden').write_text('not ignored')
        with self.assertRaises(ValueError): checkout.seal_checkout(worker, state, 'worker1', baseline, self.out / 'bad-export', self.out / 'bad-seal')

    def test_special_cache_entities_are_not_hidden(self):
        state, _, worker, baseline, _ = self.contribution(['lib/a.dart'])
        link = worker / '.dart_tool/link'; link.symlink_to(self.repo / 'lib/models.dart')
        with self.assertRaises(ValueError): checkout.seal_checkout(worker, state, 'worker1', baseline, self.out / 'bad-export', self.out / 'bad-seal')

    def test_missing_duplicate_or_modified_decision_denied_before_source_writes(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart'], {'lib/a.dart': b'new'})
        for choices in ([], [choice, choice], [dict(choice, sha256='0' * 64)]):
            with self.assertRaises(ValueError): self.install(state, choices)
            self.assertEqual(checkout.source.inventory(self.repo), self.baseline)
        self.assertFalse(any(self.journal.glob('*.json')))

    def test_root_leased_and_protected_git_changes_denied_before_install(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart'], {'lib/a.dart': b'new'})
        for name in ('lib/a.dart', '.git/HEAD', 'test/contract.dart'):
            path = self.repo / name; old = path.read_bytes(); path.write_bytes(b'root forbidden')
            with self.assertRaises(ValueError): self.install(state, [choice])
            path.write_bytes(old)
        self.assertFalse(any(self.journal.glob('*.json')))

    def test_partial_install_exception_restores_every_raw_entity_preserving_first_failure(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart', 'lib/b.dart'], {'lib/a.dart': b'new a', 'lib/b.dart': b'new b'})
        def fail(index, name): raise RuntimeError('original partial error')
        with self.assertRaises(RuntimeError) as caught: self.install(state, [choice], after_each=fail)
        value = json.loads(Path(caught.exception.preserved_transaction).read_bytes())
        self.assertEqual(value['state'], 'rolled_back_preserved_failure'); self.assertEqual(value['first_error']['message'], 'original partial error')
        self.assertEqual(checkout.source.inventory(self.repo), self.baseline)

    def test_unknown_cache_mutation_during_failure_is_retained_not_overwritten(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart'], {'lib/a.dart': b'new'})
        def fail(index, name):
            (self.repo / 'build/artifact').write_text('unknown drift'); raise RuntimeError('first failure')
        with self.assertRaises(RuntimeError) as caught: self.install(state, [choice], after_each=fail)
        value = json.loads(Path(caught.exception.preserved_transaction).read_bytes())
        self.assertEqual(value['state'], 'failed_pending_rollback'); self.assertIn('rollback_error', value)
        self.assertEqual(value['first_error']['message'], 'first failure')
        self.assertEqual((self.repo / 'build/artifact').read_text(), 'unknown drift')

    def test_deadline_denial_precedes_transaction_or_payload_write(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart'], {'lib/a.dart': b'new'})
        with self.assertRaises(ValueError): self.install(state, [choice], deadline=time.time() - 1)
        self.assertEqual(checkout.source.inventory(self.repo), self.baseline)
        self.assertFalse(any(self.journal.glob('*.json')))

    def test_real_process_death_retains_intent_and_recovers_full_checkout(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart', 'lib/b.dart'], {'lib/a.dart': b'new a', 'lib/b.dart': b'new b'})
        args = self.base / 'args.json'; args.write_text(json.dumps({'state': state, 'choices': [choice], 'baseline': self.baseline}))
        code = '''import json,os,sys
from pathlib import Path
import improvement_optional_checkout_artifacts_v1 as c
d=json.loads(Path(sys.argv[1]).read_bytes());repo=Path(sys.argv[2])
c.install(repo,d['state'],d['choices'],d['baseline'],c.source.inventory(repo),sys.argv[3],sys.argv[4],after_each=lambda i,n:os._exit(19))
'''
        result = subprocess.run([sys.executable, '-c', code, str(args), str(self.repo), str(self.journal), str(self.registry)],
                                cwd=Path(__file__).parent, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 19, result.stderr.decode()); paths = list(self.journal.glob('*.json')); self.assertEqual(len(paths), 1)
        self.assertEqual(json.loads(paths[0].read_bytes())['state'], 'intent')
        checkout.rollback(self.repo, paths[0]); self.assertEqual(checkout.source.inventory(self.repo), self.baseline)


if __name__ == '__main__': unittest.main()
