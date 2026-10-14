"""Pure prospective registry controls. No native/Docker qualification."""
import copy
import json
from pathlib import Path
import tempfile
import time
import subprocess
import sys
import unittest
from unittest.mock import patch

import improvement_optional_registry_v2 as registry


class RegistryControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'registry'
        self.base = {'.': {'kind':'directory','mode':0o755},
                     'lib': {'kind':'directory','mode':0o755}}
        for name in ('a','b','c','models'):
            self.base[f'lib/{name}.dart'] = {'kind':'file','mode':0o644,'sha256':'a'*64}
        self.paths = ['lib/a.dart','lib/b.dart','lib/c.dart']
        self.started = time.time()
        registry.create(self.folder,'probe','O01','A',self.started,self.base,self.paths)

    def reserve(self, scope, **kwargs):
        return registry.reserve_worker(self.folder,'bounded public task',scope,self.base,**kwargs)

    def test_solo_valid_no_dummy_worker(self):
        state=registry.read(self.folder)
        self.assertEqual(state['workers'],{})
        changed=copy.deepcopy(self.base)
        for name in self.paths: changed[name]['sha256']='b'*64
        self.assertTrue(registry.check_root_changes(state,changed))
        self.assertFalse(state['configuration']['native_qualified'])

    def test_two_independent_leases_and_root_remaining_file(self):
        self.reserve(['lib/a.dart']); state=self.reserve(['lib/b.dart'])
        changed=copy.deepcopy(self.base);changed['lib/c.dart']['sha256']='b'*64
        self.assertTrue(registry.check_root_changes(state,changed))
        changed['lib/a.dart']['sha256']='c'*64
        with self.assertRaises(ValueError): registry.check_root_changes(state,changed)

    def test_overlap_denied_before_new_intent(self):
        self.reserve(['lib/a.dart'])
        with self.assertRaises(ValueError):self.reserve(['lib/a.dart','lib/b.dart'])
        self.assertEqual(len(registry.read(self.folder)['workers']),1)

    def test_failed_intent_consumes_cap_and_holds_lease(self):
        self.reserve(['lib/a.dart'])
        registry.allocation_error(self.folder,'worker1',RuntimeError('ambiguous spawn'))
        self.reserve(['lib/b.dart'])
        registry.allocation_error(self.folder,'worker2',RuntimeError('create failed'))
        with self.assertRaises(ValueError):self.reserve(['lib/c.dart'])
        state=registry.read(self.folder)
        self.assertEqual(len(state['workers']),2)
        self.assertEqual(len(state['active_leases']),2)
        self.assertEqual(state['workers']['worker1']['errors'][0]['message'],'ambiguous spawn')

    def test_new_worker_cannot_clone_root_drift_inside_existing_lease(self):
        self.reserve(['lib/a.dart'])
        snapshot=copy.deepcopy(self.base);snapshot['lib/a.dart']['sha256']='b'*64
        with self.assertRaises(ValueError):
            registry.reserve_worker(self.folder,'other public task',['lib/b.dart'],snapshot)
        self.assertEqual(registry.read(self.folder)['event_count'],1)

    def test_replay_rejects_consistent_hash_of_snapshot_with_existing_lease_drift(self):
        self.reserve(['lib/a.dart']);self.reserve(['lib/b.dart'])
        p=self.folder/'events/0001.json';event=json.loads(p.read_bytes())
        event['worker']['snapshot']['lib/a.dart']['sha256']='b'*64
        event['worker']['snapshot_sha256']=registry.sha(event['worker']['snapshot'])
        p.write_text(json.dumps(event))
        with self.assertRaises(ValueError):registry.read(self.folder)

    def test_new_snapshot_can_include_root_edits_outside_active_lease(self):
        self.reserve(['lib/a.dart'])
        snapshot=copy.deepcopy(self.base);snapshot['lib/b.dart']['sha256']='b'*64
        state=registry.reserve_worker(self.folder,'other task',['lib/b.dart'],snapshot)
        self.assertTrue(registry.check_root_changes(state,snapshot))

    def test_review_reservation_rejects_existing_write_lease_drift(self):
        self.reserve(['lib/a.dart'])
        snapshot=copy.deepcopy(self.base);snapshot['lib/a.dart']['sha256']='b'*64
        with self.assertRaises(ValueError):
            registry.reserve_worker(self.folder,'review',[],snapshot,mode='review')
        self.assertEqual(registry.read(self.folder)['event_count'],1)

    def test_ambiguous_failed_allocation_lease_still_guards_new_snapshot(self):
        self.reserve(['lib/a.dart'])
        registry.allocation_error(self.folder,'worker1',RuntimeError('ambiguous'))
        snapshot=copy.deepcopy(self.base);snapshot['lib/a.dart']['sha256']='b'*64
        with self.assertRaises(ValueError):
            registry.reserve_worker(self.folder,'other task',['lib/b.dart'],snapshot)
        self.assertEqual(registry.read(self.folder)['event_count'],2)

    def test_review_worker_no_write_lease_but_consumes_slot(self):
        state=self.reserve([],mode='review')
        self.assertEqual(state['active_leases'],{})
        with self.assertRaises(ValueError):self.reserve(['lib/a.dart'],mode='review')
        self.reserve([],mode='review')
        with self.assertRaises(ValueError):self.reserve([],mode='review')

    def test_exact_original_deadline_denied(self):
        with patch.object(registry.time,'time',return_value=self.started+1200):
            with self.assertRaises(ValueError):self.reserve(['lib/a.dart'])
        self.assertEqual(registry.read(self.folder)['event_count'],0)

    def test_clock_crossing_before_persist_denied_without_event(self):
        with patch.object(registry.time,'time',side_effect=[self.started+1199,self.started+1200]):
            with self.assertRaises(ValueError):self.reserve(['lib/a.dart'])
        self.assertEqual(registry.read(self.folder)['event_count'],0)

    def test_protected_content_mode_and_tree_drift_denied(self):
        for kind in ('content','mode','addition','kind'):
            changed=copy.deepcopy(self.base)
            if kind=='content':changed['lib/models.dart']['sha256']='b'*64
            elif kind=='mode':changed['lib/a.dart']['mode']=0o600
            elif kind=='addition':changed['unexpected']={'kind':'directory','mode':0o755}
            else:changed['lib/a.dart']={'kind':'directory','mode':0o644}
            with self.assertRaises(ValueError):registry.reserve_worker(self.folder,'goal',['lib/a.dart'],changed)
        self.assertEqual(registry.read(self.folder)['event_count'],0)

    def test_no_namespace_reuse(self):
        with self.assertRaises(FileExistsError):
            registry.create(self.folder,'probe','O01','A',self.started,self.base,self.paths)

    def test_chain_gap_and_prior_event_rewrite_rejected(self):
        self.reserve(['lib/a.dart']);self.reserve(['lib/b.dart'])
        first=self.folder/'events/0000.json'
        original=first.read_bytes();event=json.loads(original)
        event['worker']['goal']='rewritten'
        first.write_text(json.dumps(event))
        with self.assertRaises(ValueError):registry.read(self.folder)
        first.write_bytes(original);first.rename(self.folder/'events/0002.json')
        with self.assertRaises(ValueError):registry.read(self.folder)

    def test_invalid_scope_and_entities(self):
        for scope in ([], ['lib/models.dart'], ['../a'], ['lib/a.dart','lib/a.dart']):
            with self.assertRaises(ValueError):self.reserve(scope)
        invalid=copy.deepcopy(self.base);invalid['lib/a.dart']['sha256']='garbage'
        with self.assertRaises(ValueError):registry.reserve_worker(self.folder,'goal',['lib/a.dart'],invalid)

    def processes(self, scopes):
        code = ('import json,sys;import improvement_optional_registry_v2 as r;'
                'r.reserve_worker(sys.argv[1],"public task",json.loads(sys.argv[2]),json.loads(sys.argv[3]))')
        actors=[subprocess.Popen([sys.executable,'-c',code,str(self.folder),json.dumps(scope),json.dumps(self.base)],
                                 cwd=Path(__file__).parent,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                for scope in scopes]
        for actor in actors:actor.communicate(timeout=10)
        return [actor.returncode for actor in actors]

    def test_concurrent_disjoint_reservations_have_distinct_intents(self):
        self.assertEqual(self.processes([['lib/a.dart'],['lib/b.dart']]),[0,0])
        state=registry.read(self.folder)
        self.assertEqual(state['event_count'],2)
        self.assertEqual(set(state['workers']),{'worker1','worker2'})

    def test_concurrent_overlapping_reservation_only_one_commits(self):
        results=self.processes([['lib/a.dart'],['lib/a.dart']])
        self.assertEqual(sorted(results),[0,1])
        self.assertEqual(registry.read(self.folder)['event_count'],1)


if __name__=='__main__':
    unittest.main()
