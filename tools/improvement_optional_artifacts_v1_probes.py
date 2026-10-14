"""Filesystem controls including actual subprocess death, no native/Docker pass."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import improvement_optional_registry_v2 as registry
import improvement_optional_artifacts_v1 as artifacts
from improvement_software_artifacts_v3 import tree


class ContributionControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.repo=self.base/'root';(self.repo/'lib').mkdir(parents=True)
        for name in ('a','b','c','models'):(self.repo/f'lib/{name}.dart').write_text(name+' old\n')
        self.initial=tree(self.repo);self.folder=self.base/'registry'
        registry.create(self.folder,'probe','O01','A',time.time(),self.initial,
                        ['lib/a.dart','lib/b.dart','lib/c.dart'])
        self.out=self.base/'artifacts';self.out.mkdir();self.journal=self.base/'integration'

    def contribution(self,scope,changes=None,decision='accept',mode='write',findings=''):
        state=registry.reserve_worker(self.folder,'public task',scope,tree(self.repo),mode)
        slot=list(state['workers'])[-1];worker=self.base/slot;shutil.copytree(self.repo,worker)
        for name,raw in (changes or {}).items():(worker/name).write_bytes(raw)
        seal=artifacts.seal(state,slot,worker,self.out/(slot+'-seal.json'),findings)
        view,_=artifacts.view(state,seal,self.out/(slot+'-view.json'))
        choice=artifacts.decide(state,seal,view,decision,'original reason',self.out/(slot+'-decision.json'))
        return state,choice,seal,worker

    def integrate(self,state,choices,**kwargs):
        return artifacts.integrate(self.repo,state,choices,tree(self.repo),self.journal,**kwargs)

    def test_solo_without_dummy_integration_or_worker(self):
        state=registry.read(self.folder);path=self.integrate(state,[])
        self.assertEqual(tree(self.repo),self.initial)
        value=json.loads(path.read_bytes());self.assertEqual(value['after_payloads'],{})
        self.assertFalse(value['native_qualified'])

    def test_one_worker_multiple_files_preserves_root_other_edit(self):
        state,choice,_,_=self.contribution(['lib/a.dart','lib/b.dart'],
                 {'lib/a.dart':b'a new\n','lib/b.dart':b'b new\n'})
        (self.repo/'lib/c.dart').write_text('root independent edit\n')
        self.integrate(state,[choice])
        self.assertEqual((self.repo/'lib/a.dart').read_bytes(),b'a new\n')
        self.assertEqual((self.repo/'lib/b.dart').read_bytes(),b'b new\n')
        self.assertEqual((self.repo/'lib/c.dart').read_text(),'root independent edit\n')

    def test_two_workers_accept_and_reject_retains_both_decisions(self):
        _,a,_,_=self.contribution(['lib/a.dart'],{'lib/a.dart':b'accepted'})
        state,b,_,_=self.contribution(['lib/b.dart'],{'lib/b.dart':b'rejected'},decision='reject')
        path=self.integrate(state,[a,b]);value=json.loads(path.read_bytes())
        self.assertEqual(len(value['decisions']),2)
        self.assertEqual((self.repo/'lib/a.dart').read_bytes(),b'accepted')
        self.assertEqual((self.repo/'lib/b.dart').read_text(),'b old\n')

    def test_all_rejected_no_patch_is_valid(self):
        state,choice,_,_=self.contribution(['lib/a.dart'],{'lib/a.dart':b'bad'},decision='reject')
        self.integrate(state,[choice]);self.assertEqual(tree(self.repo),self.initial)

    def test_read_only_findings_can_be_accepted_without_patch(self):
        state,choice,_,_=self.contribution([],mode='review',findings='Check import permissions before mutation.')
        self.integrate(state,[choice]);self.assertEqual(tree(self.repo),self.initial)

    def test_noop_write_contribution_allowed(self):
        state,choice,_,_=self.contribution(['lib/a.dart'])
        self.integrate(state,[choice]);self.assertEqual(tree(self.repo),self.initial)

    def test_missing_worker_decision_denied_before_transaction(self):
        state,choice,_,_=self.contribution(['lib/a.dart'],{'lib/a.dart':b'new'})
        with self.assertRaises(ValueError):self.integrate(state,[])
        self.assertEqual(tree(self.repo),self.initial)
        self.assertFalse(any(self.journal.glob('*.json')))

    def test_duplicate_decision_denied(self):
        _,choice,_,_=self.contribution(['lib/a.dart'])
        state,_,_,_=self.contribution(['lib/b.dart'])
        with self.assertRaises(ValueError):self.integrate(state,[choice,choice])

    def test_scope_violation_including_mode_and_unrelated_file(self):
        state,_,_,worker=self.contribution(['lib/a.dart'])
        (worker/'lib/models.dart').write_text('tampered')
        with self.assertRaises(ValueError):artifacts.seal(state,'worker1',worker,self.out/'bad.json')
        (worker/'lib/models.dart').write_text('models old\n')
        os.chmod(worker/'lib/a.dart',0o600)
        with self.assertRaises(ValueError):artifacts.seal(state,'worker1',worker,self.out/'bad.json')
        self.assertFalse((self.out/'bad.json').exists())

    def test_seal_cannot_write_inside_worker_repository(self):
        state,_,_,worker=self.contribution(['lib/a.dart'])
        with self.assertRaises(ValueError):artifacts.seal(state,'worker1',worker,worker/'seal.json')

    def test_pin_rejects_symlink(self):
        _,_,seal,_=self.contribution(['lib/a.dart'])
        link=self.out/'alias';link.symlink_to(seal['path'])
        with self.assertRaises(ValueError):artifacts.pin(link)

    def test_artifact_tamper_denied_before_integration(self):
        state,choice,seal,_=self.contribution(['lib/a.dart'],{'lib/a.dart':b'new'})
        Path(seal['path']).write_text('{}')
        with self.assertRaises(ValueError):self.integrate(state,[choice])
        self.assertEqual(tree(self.repo),self.initial)

    def test_view_from_other_worker_denied(self):
        _,_,seal,_=self.contribution(['lib/a.dart'])
        state,other,_,_=self.contribution(['lib/b.dart'])
        wrong_view=artifacts.pinned(other)['view']
        with self.assertRaises(ValueError):
            artifacts.decide(state,seal,wrong_view,'accept','reason',self.out/'wrong.json')

    def test_decision_cannot_overwrite_original(self):
        state,choice,seal,_=self.contribution(['lib/a.dart'])
        view=artifacts.pinned(choice)['view']
        with self.assertRaises(FileExistsError):
            artifacts.decide(state,seal,view,'reject','later reason',Path(choice['path']))

    def test_root_base_drift_denied_before_write(self):
        state,choice,_,_=self.contribution(['lib/a.dart'],{'lib/a.dart':b'new'})
        (self.repo/'lib/a.dart').write_text('root conflicting edit')
        with self.assertRaises(ValueError):self.integrate(state,[choice])
        self.assertEqual((self.repo/'lib/a.dart').read_text(),'root conflicting edit')

    def test_failure_after_first_write_restores_all_and_preserves_error(self):
        state,choice,_,_=self.contribution(['lib/a.dart','lib/b.dart'],
                                         {'lib/a.dart':b'a new','lib/b.dart':b'b new'})
        def fail(index,name):raise RuntimeError('injected after first replacement')
        with self.assertRaisesRegex(RuntimeError,'injected'):self.integrate(state,[choice],after_each=fail)
        self.assertEqual(tree(self.repo),self.initial)
        value=json.loads(next(self.journal.glob('*.json')).read_bytes())
        self.assertEqual(value['state'],'rolled_back_preserved_failure')
        self.assertEqual(value['first_error']['message'],'injected after first replacement')

    def test_failure_during_staging_restores_and_leaves_no_extra_file(self):
        state,choice,_,_=self.contribution(['lib/a.dart'],{'lib/a.dart':b'new'})
        def fail(index,name):raise RuntimeError('staging failure')
        with self.assertRaisesRegex(RuntimeError,'staging'):self.integrate(state,[choice],after_stage=fail)
        self.assertEqual(tree(self.repo),self.initial)

    def test_rollback_refuses_unrelated_injected_root_edits(self):
        state,choice,_,_=self.contribution(['lib/a.dart'],{'lib/a.dart':b'new'})
        def fail(index,name):
            (self.repo/'lib/models.dart').write_text('unexpected external edit')
            raise RuntimeError('original failure')
        with self.assertRaisesRegex(RuntimeError,'original failure'):self.integrate(state,[choice],after_each=fail)
        self.assertEqual((self.repo/'lib/models.dart').read_text(),'unexpected external edit')
        value=json.loads(next(self.journal.glob('*.json')).read_bytes())
        self.assertEqual(value['state'],'failed_pending_rollback')
        self.assertIn('rollback_error',value)

    def test_real_subprocess_death_at_staging_can_restore_registered_bytes(self):
        state,choice,_,_=self.contribution(['lib/a.dart'],{'lib/a.dart':b'new'})
        input_file=self.base/'process-input.json';input_file.write_text(json.dumps({'state':state,'choices':[choice],'tree':tree(self.repo)}))
        code='''import json,sys,os
from pathlib import Path
import improvement_optional_artifacts_v1 as a
d=json.loads(Path(sys.argv[1]).read_text())
def crash(index,name):os._exit(77)
a.integrate(sys.argv[2],d['state'],d['choices'],d['tree'],sys.argv[3],after_stage=crash)
'''
        result=subprocess.run([sys.executable,'-c',code,str(input_file),str(self.repo),str(self.journal)],
                              cwd=Path(__file__).parent,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,77,result.stderr)
        transaction=next(self.journal.glob('*.json'))
        self.assertEqual(json.loads(transaction.read_bytes())['state'],'intent')
        self.assertNotEqual(tree(self.repo),self.initial)
        artifacts.rollback(self.repo,transaction)
        self.assertEqual(tree(self.repo),self.initial)
        self.assertEqual(json.loads(transaction.read_bytes())['state'],'rolled_back_preserved_failure')


if __name__=='__main__':unittest.main()
