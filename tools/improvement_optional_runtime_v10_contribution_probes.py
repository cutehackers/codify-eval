"""Mocked Docker fences plus real filesystem contribution pipeline only."""
import copy
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch

import improvement_optional_runtime_v10 as runtime
import improvement_optional_checkout_artifacts_v2_probes as fixtures


class ContributionRuntimeControls(unittest.TestCase):
    def setUp(self):
        fixtures.CheckoutControls.setUp(self)
        prior = self.base / 'prior'; self.repo.rename(prior); self.repo.mkdir(); shutil.move(prior, self.repo / 'repo'); self.repo /= 'repo'
        (self.base / 'events').mkdir(); self.caps = {'root': 'a' * 48, 'worker1': 'b' * 48, 'worker2': 'c' * 48}
        config = runtime.registry.read(self.registry)['configuration']
        self.state = {'run_id': 'probe', 'configuration_sha256': 'runtime-configuration', 'phase': 'running',
                      'started_at': config['started_at'], 'deadline': config['deadline'], 'events': 0, 'first_error': None,
                      'editable_paths': config['editable_paths'], 'jobs': {'root': {'status': 'running', 'container_id': 'root-id',
                       'capability_sha256': runtime.hashed(self.caps['root']), 'baseline': self.baseline}}}
        runtime.save(self.base, self.state)
        self.inspect_mock = patch.object(runtime, 'inspect', return_value={'State': {'Running': False}}); self.inspect_mock.start(); self.addCleanup(self.inspect_mock.stop)
        self.stop_mock = patch.object(runtime, 'stop', side_effect=lambda folder, job, cleanup=False: runtime.status(folder, job, 'stopped')); self.stop_mock.start(); self.addCleanup(self.stop_mock.stop)
        self.start_mock = patch.object(runtime, 'start', side_effect=lambda folder, job: runtime.status(folder, job, 'running')); self.start_mock.start(); self.addCleanup(self.start_mock.stop)

    def worker(self, scope, changes=None, mode='write'):
        members = runtime.registry.reserve_worker(self.registry, 'public task', scope, runtime.source.inventory(self.repo)['source_entities'], mode)
        slot = list(members['workers'])[-1]; repo = self.base / slot / 'repo'; repo.parent.mkdir(); shutil.copytree(self.repo, repo)
        baseline = runtime.source.inventory(repo)
        for name, raw in (changes or {}).items(): (repo / name).write_bytes(raw)
        state = runtime.load(self.base); state['jobs'][slot] = {'status': 'running', 'container_id': slot + '-id',
            'capability_sha256': runtime.hashed(self.caps[slot]), 'baseline': baseline}; runtime.save(self.base, state)
        return slot

    def decide(self, slot, decision='accept', findings=''):
        sealed = runtime.seal(self.base, slot, self.caps[slot], findings)
        viewed = runtime.view(self.base, self.caps['root'], slot)
        result = runtime.decide(self.base, self.caps['root'], slot, viewed['view'], decision, 'original reason')
        return sealed, viewed, result

    def test_solo_integrates_no_dummy_worker_and_restarts_root(self):
        result = runtime.integrate(self.base, self.caps['root']); self.assertFalse(result['runtime_qualified'])
        self.assertEqual(runtime.registry.read(self.registry)['workers'], {})
        self.assertEqual(runtime.load(self.base)['jobs']['root']['status'], 'running')

    def test_multi_file_accept_preserves_root_own_edit_and_closed_worker(self):
        slot = self.worker(['lib/a.dart', 'lib/b.dart'], {'lib/a.dart': b'worker a', 'lib/b.dart': b'worker b'})
        self.decide(slot); (self.repo / 'lib/c.dart').write_bytes(b'root independent')
        runtime.integrate(self.base, self.caps['root'])
        self.assertEqual((self.repo / 'lib/a.dart').read_bytes(), b'worker a')
        self.assertEqual((self.repo / 'lib/c.dart').read_bytes(), b'root independent')
        self.assertEqual(runtime.registry.read(self.registry)['active_leases'], {})
        self.assertEqual(runtime.load(self.base)['jobs'][slot]['status'], 'sealed_stopped')
        with self.assertRaises(ValueError): runtime.role(self.base, slot, self.caps[slot])

    def test_two_workers_accept_reject_require_both_original_views(self):
        a = self.worker(['lib/a.dart'], {'lib/a.dart': b'accepted'}); b = self.worker(['lib/b.dart'], {'lib/b.dart': b'rejected'})
        self.decide(a); self.decide(b, 'reject'); runtime.integrate(self.base, self.caps['root'])
        self.assertEqual((self.repo / 'lib/a.dart').read_bytes(), b'accepted')
        self.assertEqual((self.repo / 'lib/b.dart').read_bytes(), b'b old\n')

    def test_readonly_findings_and_noop_contribution(self):
        a = self.worker([], mode='review'); b = self.worker(['lib/b.dart'])
        self.decide(a, findings='Review input authorization.'); self.decide(b)
        runtime.integrate(self.base, self.caps['root']); self.assertEqual(runtime.source.inventory(self.repo), self.baseline)

    def test_missing_seal_or_decision_denied_before_root_stop(self):
        slot = self.worker(['lib/a.dart']); before = runtime.load(self.base)
        with self.assertRaises(ValueError): runtime.integrate(self.base, self.caps['root'])
        self.assertEqual(runtime.load(self.base), before)
        runtime.seal(self.base, slot, self.caps[slot]); before = runtime.load(self.base)
        with self.assertRaises(FileNotFoundError): runtime.integrate(self.base, self.caps['root'])
        self.assertEqual(runtime.load(self.base), before)

    def test_wrong_root_cap_and_worker_root_operation_rejected(self):
        slot = self.worker(['lib/a.dart']); before = runtime.load(self.base)
        with self.assertRaises(ValueError): runtime.seal(self.base, slot, self.caps['root'])
        with self.assertRaises(ValueError): runtime.view(self.base, self.caps[slot], slot)
        self.assertEqual(runtime.load(self.base), before)

    def test_worker_scope_and_git_violation_preserves_runtime_first_error(self):
        slot = self.worker(['lib/a.dart'], {'lib/models.dart': b'forbidden'})
        with self.assertRaises(ValueError): runtime.seal(self.base, slot, self.caps[slot])
        self.assertEqual(runtime.load(self.base)['phase'], 'failed_preservation_required')
        self.assertIsNotNone(runtime.load(self.base)['first_error'])

    def test_invalid_review_findings_rejected_before_stopping_worker(self):
        slot = self.worker([], mode='review'); before = runtime.load(self.base)
        with self.assertRaises(ValueError): runtime.seal(self.base, slot, self.caps[slot])
        self.assertEqual(runtime.load(self.base), before)

    def test_unknown_or_forged_view_ref_denied_without_decision(self):
        slot = self.worker(['lib/a.dart']); runtime.seal(self.base, slot, self.caps[slot])
        viewed = runtime.view(self.base, self.caps['root'], slot)
        with self.assertRaises(ValueError): runtime.decide(self.base, self.caps['root'], slot,
                                            dict(viewed['view'], sha256='0' * 64), 'accept', 'reason')
        self.assertFalse((self.registry / 'decisions' / (slot + '.json')).exists())

    def test_new_allocation_after_final_release_denied_before_root_stop(self):
        runtime.integrate(self.base, self.caps['root']); before = runtime.load(self.base)
        with self.assertRaises(ValueError): runtime.worker(self.base, self.caps['root'], 'later', ['lib/a.dart'])
        self.assertEqual(runtime.load(self.base), before)

    def test_public_checks_keep_inner_failure_and_no_positive_software_claim(self):
        outcomes = [{'exit_code': 1, 'output_complete': True}, {'exit_code': 0, 'output_complete': True}]
        with patch.object(runtime, 'command', side_effect=outcomes) as command:
            result = runtime.verify(self.base, self.caps['root'])
        self.assertEqual(result['public']['exit_code'], 1); self.assertEqual(result['analyze']['exit_code'], 0)
        self.assertEqual(command.call_count, 2); self.assertFalse(result['software_pass_qualified'])

    def test_encoded_seal_overflow_after_stop_preserves_failure_and_lease(self):
        changes = {f'lib/{name}.dart': b'x' * (1024 * 1024) for name in ('a', 'b', 'c')}
        slot = self.worker(list(changes), changes)
        with self.assertRaises(ValueError): runtime.seal(self.base, slot, self.caps[slot], '\x00' * (1024 * 1024))
        state = runtime.load(self.base); self.assertEqual(state['phase'], 'failed_preservation_required')
        self.assertIsNotNone(state['first_error']); self.assertEqual(state['jobs'][slot]['status'], 'stopped')
        self.assertEqual(len(runtime.registry.read(self.registry)['active_leases']), 3)

    def test_generated_symlink_snapshot_failure_after_root_stop_is_preserved(self):
        (self.repo / 'build/invalid-link').symlink_to(self.repo / 'lib/models.dart')
        with self.assertRaises(ValueError): runtime.integrate(self.base, self.caps['root'])
        state = runtime.load(self.base); self.assertEqual(state['phase'], 'failed_preservation_required')
        self.assertIsNotNone(state['first_error']); self.assertEqual(state['jobs']['root']['status'], 'stopped')


if __name__ == '__main__': unittest.main()
