"""Failure lifecycle probes on real journals, mocked transport/native observations."""
import copy,hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import improvement_baseline_q02_v1 as runner
OUT=runner.ROOT/'results/improvement-v1/baseline-q02-lifecycle-probes-v1.json'
class Lifecycle(unittest.TestCase):
    def setup_case(self,root,running=True):
        source=root/'native.jsonl';source.write_bytes(b'synthetic-observed-prefix\n')
        metadata={'container':'owned-product','image_id':'pinned-image'}
        identity={'Id':'actual-id','Image':'pinned-image','HostConfig':{'NetworkMode':'none'},'Mounts':[{'Source':str(root/'runtime/run/repo')},{'Source':str(root/'runtime/run/control-inputs')}],'State':{'Running':running}}
        after=copy.deepcopy(identity);after['State']['Running']=False
        return source,metadata,identity,after
    def test_pending_actor_does_not_stop_or_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,m,identity,after=self.setup_case(root)
            with patch.object(runner,'ROOT',root),patch('collect.find_session',return_value=source),patch('improvement_usage_v4.snapshot',return_value={'native_completion_observed':False}),patch.object(runner.subprocess,'check_output') as inspect:
                with self.assertRaises(runner.prior.ActorNotTerminal):runner.quiesce('run',m,'/root/actual')
                inspect.assert_not_called()
    def test_diagnostic_failure_keeps_immutable_native_and_first_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,m,identity,after=self.setup_case(root)
            with patch.object(runner,'ROOT',root),patch('collect.find_session',return_value=source),patch('improvement_usage_v4.snapshot',return_value={'native_completion_observed':True}),patch.object(runner.subprocess,'check_output',side_effect=[json.dumps([identity]),json.dumps([after])]),patch.object(runner.subprocess,'run') as command,patch.object(runner.diagnostics,'preserve_tmp',side_effect=ValueError('injected archive byte budget')):
                with self.assertRaises(runner.EvidencePending):runner.quiesce('run',m,'/root/actual')
                self.assertFalse(any('rm' in c.args[0] for c in command.call_args_list))
            out=root/'results/run';journal=json.loads(next(out.glob('quiescence-attempt-*.json')).read_bytes())
            self.assertTrue(journal['needed_container_retained']);self.assertEqual(journal['first_error']['message'],'injected archive byte budget')
            self.assertEqual(Path(journal['source_copy']).read_bytes(),source.read_bytes());self.assertFalse((out/'quiescence.json').exists())
    def test_stop_timeout_kill_then_preserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,m,identity,after=self.setup_case(root)
            def cmd(args,**kw):
                if args[1]=='stop':raise subprocess.TimeoutExpired(args,10)
                return subprocess.CompletedProcess(args,0)
            with patch.object(runner,'ROOT',root),patch('collect.find_session',return_value=source),patch('improvement_usage_v4.snapshot',return_value={'native_completion_observed':True}),patch.object(runner.subprocess,'check_output',side_effect=[json.dumps([identity]),json.dumps([after])]),patch.object(runner.subprocess,'run',side_effect=cmd) as command,patch.object(runner.diagnostics,'preserve_tmp'):
                out=runner.quiesce('run',m,'/root/actual')
                self.assertIn(['docker','kill','owned-product'],[c.args[0] for c in command.call_args_list])
                self.assertEqual(json.loads((out/'quiescence.json').read_bytes())['state'],'preserved')
    def test_wrong_image_refused_before_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,m,identity,after=self.setup_case(root);identity['Image']='other-image'
            with patch.object(runner,'ROOT',root),patch('collect.find_session',return_value=source),patch('improvement_usage_v4.snapshot',return_value={'native_completion_observed':True}),patch.object(runner.subprocess,'check_output',return_value=json.dumps([identity])),patch.object(runner.subprocess,'run') as command:
                with self.assertRaises(runner.EvidencePending):runner.quiesce('run',m,'/root/actual')
                command.assert_not_called()
if __name__=='__main__':
    assert not OUT.exists()
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Lifecycle))
    paths=[Path(__file__),runner.ROOT/'tools/improvement_baseline_q02_v1.py']
    with OUT.open('x') as f:json.dump({'status':'pass' if r.wasSuccessful() else 'fail','tests':r.testsRun,'errors':[(str(t),s) for t,s in r.errors],'failures':[(str(t),s) for t,s in r.failures],'actual_Q02_actor_qualified':False,'superiority_proven':False,'source_hashes':{str(p.relative_to(runner.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}},f,indent=2)
    raise SystemExit(0 if r.wasSuccessful() else 1)
