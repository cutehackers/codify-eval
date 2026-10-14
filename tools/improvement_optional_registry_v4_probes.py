"""Filesystem final lease release controls, not native/container authority."""
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

import improvement_optional_registry_v4 as registry
import improvement_optional_checkout_artifacts_v2 as checkout
import improvement_optional_checkout_artifacts_v2_probes as fixtures


class LeaseReleaseControls(unittest.TestCase):
    setUp = fixtures.CheckoutControls.setUp
    contribution = fixtures.CheckoutControls.contribution
    install = fixtures.CheckoutControls.install

    def proofs(self, state, choices):
        transaction = self.install(state, choices)
        return (checkout.file_pin(transaction), self.intent_pins[-1],
                checkout.file_pin(transaction.with_name(transaction.stem + '.commit.json')))

    def release(self, proofs): return registry.release_after_install(self.registry, *proofs)

    def test_accepted_raw_install_releases_leases_and_root_can_correct_implementation(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart'], {'lib/a.dart': b'accepted'})
        proofs = self.proofs(state, [choice]); current = checkout.source.inventory(self.repo)['source_entities']
        with self.assertRaises(ValueError): registry.check_root_changes(registry.read(self.registry), current)
        released = self.release(proofs); self.assertEqual(released['active_leases'], {})
        self.assertEqual(len(released['workers']), 1)
        (self.repo / 'lib/a.dart').write_bytes(b'root final correction')
        self.assertTrue(registry.check_root_changes(registry.read(self.registry), checkout.source.inventory(self.repo)['source_entities']))

    def test_two_decisions_accept_reject_keep_both_consumed_slots(self):
        _, a, _, _, _ = self.contribution(['lib/a.dart'], {'lib/a.dart': b'accepted'})
        state, b, _, _, _ = self.contribution(['lib/b.dart'], {'lib/b.dart': b'rejected'}, decision='reject')
        released = self.release(self.proofs(state, [a, b]))
        self.assertEqual(len(released['workers']), 2); self.assertEqual(released['active_leases'], {})
        self.assertEqual((self.repo / 'lib/b.dart').read_bytes(), b'b old\n')

    def test_readonly_review_and_noop_or_rejected_release(self):
        _, a, _, _, _ = self.contribution([], mode='review', findings='Review public behavior.')
        state, b, _, _, _ = self.contribution(['lib/a.dart'], decision='reject')
        self.assertEqual(self.release(self.proofs(state, [a, b]))['active_leases'], {})

    def test_solo_final_install_has_no_dummy_worker(self):
        state = registry.read(self.registry); released = self.release(self.proofs(state, []))
        self.assertEqual(released['workers'], {}); self.assertEqual(released['active_leases'], {})

    def test_no_repeat_final_release_or_new_allocation_after_integration(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart'])
        proofs = self.proofs(state, [choice]); released = self.release(proofs)
        with self.assertRaises(ValueError): self.release(proofs)
        with self.assertRaises(ValueError): registry.reserve_worker(self.registry, 'later worker', ['lib/b.dart'],
                                             checkout.source.inventory(self.repo)['source_entities'])
        self.assertEqual(registry.read(self.registry), released)

    def test_canonical_decision_tamper_retains_leases(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart'], {'lib/a.dart': b'new'})
        proofs = self.proofs(state, [choice]); path = Path(choice['path']); value = json.loads(path.read_bytes())
        value['reason'] = 'modified'; path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): self.release(proofs)
        self.assertEqual(registry.read(self.registry)['active_leases'], {'lib/a.dart': 'worker1'})

    def test_wrong_or_tampered_original_commit_pins_rejected(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart'])
        proofs = self.proofs(state, [choice])
        for index in range(3):
            changed = list(proofs); changed[index] = dict(changed[index], sha256='0' * 64)
            with self.assertRaises(ValueError): self.release(changed)
        changed = list(proofs); changed[0] = dict(changed[0], mode=float(changed[0]['mode']))
        with self.assertRaises(ValueError): self.release(changed)

    def test_actual_raw_source_or_cache_drift_blocks_release_before_event(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart'])
        proofs = self.proofs(state, [choice]); before = registry.read(self.registry)
        for name in ('lib/models.dart', 'build/artifact'):
            path = self.repo / name; old = path.read_bytes(); path.write_bytes(b'drift')
            with self.assertRaises(ValueError): self.release(proofs)
            path.write_bytes(old)
        self.assertEqual(registry.read(self.registry), before)

    def test_release_after_original_deadline_denied(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart'])
        proofs = self.proofs(state, [choice]); later = state['configuration']['deadline'] + 1
        with patch.object(registry.time, 'time', return_value=later):
            with self.assertRaises(ValueError): self.release(proofs)
        self.assertEqual(registry.read(self.registry)['active_leases'], {'lib/a.dart': 'worker1'})

    def test_released_root_still_cannot_change_tests_git_or_modes(self):
        released = self.release(self.proofs(registry.read(self.registry), []))
        path = self.repo / 'lib/models.dart'; path.write_bytes(b'forbidden')
        with self.assertRaises(ValueError): registry.check_root_changes(released, checkout.source.inventory(self.repo)['source_entities'])

    def test_valid_future_install_receipts_cannot_release_before_committed_time(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart'])
        future = state['configuration']['deadline'] - 5
        with patch.object(checkout.time, 'time', return_value=future): proofs = self.proofs(state, [choice])
        with self.assertRaises(ValueError): self.release(proofs)
        self.assertEqual(registry.read(self.registry)['active_leases'], {'lib/a.dart': 'worker1'})

    def test_original_replay_release_event_cannot_predate_terminal_commit(self):
        state, choice, _, _, _ = self.contribution(['lib/a.dart'])
        proofs = self.proofs(state, [choice]); released = self.release(proofs)
        event_path = self.registry / 'events' / f'{released["event_count"]-1:04d}.json'
        event = json.loads(event_path.read_bytes()); prior = state['configuration']['started_at']
        reserve = json.loads((self.registry / 'events/0000.json').read_bytes())
        event['at'] = reserve['at']; event_path.write_text(json.dumps(event))
        with self.assertRaises(ValueError): registry.read(self.registry)


if __name__ == '__main__': unittest.main()
