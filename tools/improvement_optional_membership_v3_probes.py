"""Real filesystem releases with synthetic native joins, never live actor proof."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

import improvement_optional_membership_v3 as adapter
import improvement_optional_membership_v2_probes as native_fixtures
import improvement_optional_registry_v4_probes as release_fixtures


class FinalMembershipControls(unittest.TestCase):
    setUp = release_fixtures.LeaseReleaseControls.setUp
    contribution = release_fixtures.LeaseReleaseControls.contribution
    install = release_fixtures.LeaseReleaseControls.install
    proofs = release_fixtures.LeaseReleaseControls.proofs
    release = release_fixtures.LeaseReleaseControls.release

    def finalized(self, count=2, failed=False):
        choices = []
        state = adapter.registry.read(self.registry)
        for i in range(count):
            state, choice, *_ = self.contribution([f'lib/{"abc"[i]}.dart'],
                {f'lib/{"abc"[i]}.dart': b'worker change\n'}, decision='accept' if i == 0 else 'reject')
            choices.append(choice)
        if failed:
            state = adapter.registry.append(self.registry, state, 'allocation_error',
                slot='worker1', error={'type':'RuntimeError','message':'original ambiguous allocation'})
        self.release(self.proofs(state, choices))
        return adapter.registry.read(self.registry)

    def join(self, state):
        n = len(state['workers']); values = native_fixtures.Controls().fixture(n)
        config = state['configuration']; start = config['started_at']
        def stamp(at): return datetime.fromtimestamp(at, timezone.utc).isoformat()
        for index in (4, 5):
            events = adapter.original.core.parse(values[index])
            for event in events:
                event['timestamp'] = stamp(start + adapter.original.core.instant(event['timestamp']).timestamp()
                                           - adapter.original.core.instant('2026-10-12T00:00:00Z').timestamp())
            values[index] = native_fixtures.raw(events)
        for path, raw in values[6].items():
            events = adapter.original.core.parse(raw)
            for event in events:
                event['timestamp'] = stamp(start + adapter.original.core.instant(event['timestamp']).timestamp()
                                           - adapter.original.core.instant('2026-10-12T00:00:00Z').timestamp())
            values[6][path] = native_fixtures.raw(events)
        values[0] = config; values[1] = state
        for job, intent in {'root':values[2], **values[3]}.items():
            intent['at'] = stamp(start + 0.01 if job == 'root' else start + 5)
            intent['configuration_sha256'] = adapter.original.digest(config)
            intent['reservation_worker_sha256'] = None if job == 'root' else adapter.original.worker_digest(state['workers'][job])
            values[7]['jobs'][job]['intent_sha256'] = adapter.original.digest(intent)
        values[7]['configuration_sha256'] = adapter.original.digest(config)
        return values[:8] + [self.registry]

    def test_zero_one_two_final_release_keeps_all_actor_members(self):
        # Each iteration owns a separate filesystem fixture and original ledger.
        for count in range(3):
            with self.subTest(count=count):
                self.setUp(); state = self.finalized(count)
                proof = adapter.reconcile_membership(*self.join(state))
                self.assertEqual(len(proof['members']), count + 1)
                self.assertEqual(len(proof['attempts']), count)
                self.assertTrue(proof['provided_allocation_joins_complete'])
                self.assertEqual(state['active_leases'], {})
                self.assertIsNotNone(proof['final_integration_release'])
                self.assertFalse(proof['native_qualified'])
                self.assertFalse(proof['whole_cost_qualified'])

    def test_original_failed_allocation_is_retained_after_release(self):
        state = self.finalized(1, failed=True)
        proof = adapter.reconcile_membership(*self.join(state))
        self.assertEqual(proof['attempts'][0]['registry_errors'][0]['message'], 'original ambiguous allocation')
        self.assertEqual(len(proof['members']), 2)

    def test_unreleased_reservation_still_holds_lease(self):
        state, *_ = self.contribution(['lib/a.dart'])
        proof = adapter.reconcile_membership(*self.join(state))
        self.assertIsNone(proof['final_integration_release'])
        self.assertEqual(state['active_leases'], {'lib/a.dart':'worker1'})

    def test_missing_receipt_after_release_stays_unknown(self):
        state = self.finalized(1); values = self.join(state)
        events = adapter.original.core.parse(values[5]); events.pop(); values[5] = native_fixtures.raw(events)
        proof = adapter.reconcile_membership(*values)
        self.assertEqual(proof['pending_allocation_slots'], ['worker1'])
        self.assertEqual(len(proof['observed_unbound_sources']), 1)

    def test_supplied_workers_cannot_be_removed_when_leases_empty(self):
        state = self.finalized(1); values = self.join(state)
        values[1] = copy.deepcopy(state); values[1]['workers'] = {}
        with self.assertRaises(ValueError): adapter.reconcile_membership(*values)

    def test_numeric_type_forgery_rejected(self):
        state = self.finalized(0); values = self.join(state)
        values[1] = copy.deepcopy(state); values[1]['event_count'] = float(state['event_count'])
        with self.assertRaises(ValueError): adapter.reconcile_membership(*values)

    def test_original_commit_tamper_denies_snapshot(self):
        state = self.finalized(1)
        event = json.loads((self.registry/'events/0001.json').read_bytes())
        Path(event['commitment']['path']).write_bytes(b'{}\n')
        with self.assertRaises(ValueError): adapter.reservation_prefix(self.registry)

    def test_release_event_clock_tamper_denies_snapshot(self):
        self.finalized(1); path = self.registry/'events/0001.json'
        event = json.loads(path.read_bytes()); event['at'] = 0; path.write_text(json.dumps(event))
        with self.assertRaises(ValueError): adapter.reservation_prefix(self.registry)

    def test_symlink_registry_or_events_denied(self):
        link = self.base/'registry-link'; link.symlink_to(self.registry, target_is_directory=True)
        with self.assertRaises(ValueError): adapter.reservation_prefix(link)
        (self.registry/'events').rename(self.registry/'original-events')
        (self.registry/'events').symlink_to(self.registry/'original-events', target_is_directory=True)
        with self.assertRaises(ValueError): adapter.reservation_prefix(self.registry)


if __name__ == '__main__': unittest.main()
