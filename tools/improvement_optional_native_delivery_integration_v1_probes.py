"""Retrospective actual worker routes/observation joins, never promotion."""
import hashlib
import json
from pathlib import Path
import unittest
import tempfile
from contextlib import nullcontext
from unittest.mock import patch

import improvement_optional_native_watch_v4 as watch
import improvement_optional_routes_v5 as routes
import improvement_optional_native_audit_v4 as audit

ROOT=Path(__file__).resolve().parents[1]


class DeliveryIntegrationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder=ROOT/'runtime/native-optional-control-v7-one_worker';out=cls.folder/'native-close'
        cls.root_raw=(out/'root.jsonl').read_bytes();cls.child_raw=(out/'worker1.jsonl').read_bytes()
        cls.contracts=json.loads((out/'contracts.json').read_bytes());cls.ledgers=json.loads((out/'ledgers.json').read_bytes())
        cls.root_header=watch.core.parse(cls.root_raw)[0]['payload'];cls.child_header=watch.core.parse(cls.child_raw)[0]['payload']

    def test_actual_parent_and_child_terminal_samples_keep_full_raw_hashes(self):
        path=self.root_header['agent_path'];child=self.child_header['agent_path']
        value=watch.sample(self.root_raw,path,self.root_header['parent_thread_id'],child_sources={child:self.child_raw})
        self.assertTrue(value['normal_completion_observed']);self.assertEqual(value['raw_sha256'],hashlib.sha256(self.root_raw).hexdigest())
        self.assertTrue(watch.sample(self.child_raw,child,self.root_header['id'],child_sources={})['normal_completion_observed'])
        self.assertFalse(value['cleanup_authorized']);self.assertFalse(value['native_qualified'])

    def role(self,raw,header,children):
        path=header['agent_path'];binding={'agent_path':path,'actor_native_id':header['id'],'parent_native_id':header['parent_thread_id']}
        context=next(e['payload'] for e in watch.core.parse(raw) if e['type']=='turn_context')
        return routes.audit_member(raw,binding,self.contracts[path],json.dumps(self.ledgers[path]).encode(),
            {'turn_ids':[context['turn_id']],'native_sha256':hashlib.sha256(raw).hexdigest(),'approved':True},children)

    def test_worker_failed_seal_receipt_is_preserved_and_route_closed(self):
        value=self.role(self.child_raw,self.child_header,{})
        self.assertEqual(value['broker_request_count'],6);self.assertFalse(value['native_qualified'])
        self.assertEqual(self.ledgers[self.child_header['agent_path']][-1]['status'],'failed')

    def test_original_parent_failure_stays_denied_after_delivery_fix(self):
        with self.assertRaisesRegex(ValueError,'Action/native request coverage mismatch'):
            self.role(self.root_raw,self.root_header,{self.child_header['agent_path']:self.child_raw})

    def test_supervisor_collects_worker_source_before_parent_final_classification(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary).resolve();folder=base/'runtime/probe';folder.mkdir(parents=True)
            state=watch.registry.read(self.folder/'registry');config=state['configuration']
            (folder/'registry').mkdir();(folder/'registry/configuration.json').write_text(json.dumps(config))
            root_source=base/'root.jsonl';child_source=base/'child.jsonl';root_source.write_bytes(self.root_raw);child_source.write_bytes(self.child_raw)
            sources={self.root_header['agent_path']:root_source,self.child_header['agent_path']:child_source}
            original_write=watch.atomic_json
            def write(path,value,**options):
                original_write(path,value,**options)
                if path.name=='ready.json':original_write(path.parent/'stop.json',{'reason':'coordinator_stop','root_path':self.root_header['agent_path'],'parent_id':self.root_header['parent_thread_id']},exclusive=True)
            now=config['started_at']+600
            with patch.object(watch,'ROOT',base),patch.object(watch.registry,'locked',return_value=nullcontext()),patch.object(watch.registry,'read',return_value=state),patch.object(watch,'find_session',side_effect=lambda p:sources[p]),patch.object(watch.time,'time',side_effect=[now,now+.1,now+.2]),patch.object(watch,'atomic_json',side_effect=write):
                value=watch.supervise(folder,self.root_header['agent_path'],self.root_header['parent_thread_id'])
            self.assertEqual(len(value['members']),2);self.assertTrue(value['all_registered_normal_completions_observed'])
            self.assertEqual(value['pending_native_jobs'],[]);self.assertFalse(value['native_qualified'])


if __name__=='__main__':unittest.main()
