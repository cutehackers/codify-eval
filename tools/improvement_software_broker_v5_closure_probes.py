"""Injected closure failures on real journals; no native/model/Docker qualification."""
import hashlib
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

import improvement_software_broker_v5 as broker

ROOT=broker.ROOT
BASE=ROOT/'runtime/protocol-probes/software-broker-v5-closure-probes'
OUT=ROOT/'results/improvement-v1/software-broker-v5-closure-probes.json'


class Closure(unittest.TestCase):
    def setup_case(self,name,kind):
        folder=BASE/name;folder.mkdir(parents=True)
        expected={'.':{'kind':'directory','mode':493}}
        transaction=folder/'transaction.json';transaction.write_text(json.dumps({'expected_after':expected}))
        state={'phase':'verified','transaction':str(transaction),'actions':[],'bindings':{},'first_error':None}
        broker.save(folder,state)
        registration={'coordinator_source':str(folder/'parent.jsonl'),'actors':{j:{'path':'/root/product/'+j} for j in broker.JOBS}}
        runtime_state={'started_at':time.time()-2,'jobs':{j:{'status':'stopped','container':'owned-'+j} for j in broker.JOBS}}
        sources={j:folder/(j+'.jsonl') for j in broker.JOBS}
        for p in sources.values():p.write_bytes(b'synthetic-native\n')
        registration['coordinator_source']=str(sources['root'])
        def bind(f,r,s,j):return sources[j].read_bytes(),str(sources[j])
        def native(raw,reg,job,root):
            counters=None if kind=='missing_cost' and job=='label' else {'input_tokens':10,'cached_input_tokens':2,'output_tokens':2,'total_tokens':12}
            return {'broker_requests':[],'usage':{'native_session_id':'uuid-'+job,'usage':counters,'completions':[{'completed_at':1}]}}
        cleanup_observation=[]
        def cleanup(f):
            saved=broker.load(f)
            attempt=json.loads(Path(saved['closure_attempts'][-1]).read_bytes())
            self.assertIn('native',attempt);self.assertIn('product_tokens_as_of_attempt',attempt)
            cleanup_observation.append(attempt['state'])
            if kind=='cleanup_failure':raise ValueError('injected cleanup failure')
            for row in runtime_state['jobs'].values():row['status']='removed'
            if kind=='late_append':sources['label'].write_bytes(sources['label'].read_bytes()+b'late\n')
            if kind=='concurrent_abort':(folder/'abort-intent.json').write_text('{"original_reason":"injected abort"}')
        patches=[patch.object(broker,'folder_for',return_value=folder),patch.object(broker,'config',return_value=registration),
                 patch.object(broker,'bind_actor',side_effect=bind),patch.object(broker,'audit',side_effect=native),
                 patch.object(broker,'runtime_completed',return_value={'call_id':'synthetic-status'}),
                 patch.object(broker.runtime,'load',return_value=runtime_state),patch.object(broker.runtime,'stop'),
                 patch.object(broker,'preserve_tmp'),patch.object(broker.runtime,'cleanup',side_effect=cleanup),
                 patch.object(broker.artifacts,'tree',return_value=expected)]
        return folder,patches,cleanup_observation
    def perform(self,name,kind,success):
        folder,patches,observations=self.setup_case(name,kind)
        import contextlib
        with contextlib.ExitStack() as stack:
            for p in patches:stack.enter_context(p)
            if success:result=broker.close('synthetic')
            else:
                with self.assertRaises(ValueError):broker.close('synthetic')
                result=broker.load(folder)
        attempt=json.loads(Path(result['closure_attempts'][-1]).read_bytes())
        self.assertTrue(observations)
        self.assertEqual(result['phase'],'closed_protocol_as_of_seal' if success else 'closure_invalidated')
        self.assertEqual(attempt['state'],'closed_protocol_as_of_seal' if success else 'failed')
        self.assertIn('native',attempt);self.assertIn('product_tokens_as_of_attempt',attempt)
        self.assertFalse(result.get('complete_final_cost',False))
        return result
    def test_normal_preserves_before_cleanup(self):self.perform('normal','normal',True)
    def test_cleanup_failure_keeps_proofs(self):self.perform('cleanup-failure','cleanup_failure',False)
    def test_late_append_revokes_acceptance(self):self.perform('late-append','late_append',False)
    def test_abort_after_cleanup_prevents_acceptance(self):self.perform('concurrent-abort','concurrent_abort',False)
    def test_missing_tokens_preserved_null(self):
        result=self.perform('missing-cost','missing_cost',True)
        self.assertEqual(result['product_tokens_as_of_seal'],{k:None for k in ('input_tokens','cached_input_tokens','output_tokens','total_tokens')})
    def test_bounded_archive_failure_fallback_same_container(self):
        folder=BASE/'archive-fallback';folder.mkdir(parents=True)
        with patch.object(broker,'archive_tmp',side_effect=[ValueError('injected64MiB guard'),None]) as archive,patch.object(broker.shutil,'disk_usage',return_value=type('Space',(),{'free':6*1024**3})()):
            broker.preserve_tmp(folder,'same-stopped-container','label')
        self.assertEqual(archive.call_count,2)
        self.assertEqual(archive.call_args_list[0].args[1],archive.call_args_list[1].args[1])
        self.assertLessEqual(archive.call_args_list[1].kwargs['limit'],2*1024**3)
        self.assertIn('archive_failed',(folder/'events.jsonl').read_text())


if __name__=='__main__':
    assert not OUT.exists() and not BASE.exists()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Closure))
    report={'status':'pass' if result.wasSuccessful() else 'fail','injected_tests':result.testsRun,
            'failures':[(str(t),s) for t,s in result.failures],'errors':[(str(t),s) for t,s in result.errors],
            'native_and_runtime_are_mocked':True,'real_journals_preserved':True,'actual_model_actors':0,
            'full_broker_qualified':False,'superiority_proven':False,
            'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),ROOT/'tools/improvement_software_broker_v5.py')}}
    with OUT.open('x') as f:json.dump(report,f,indent=2)
    raise SystemExit(0 if result.wasSuccessful() else 1)
