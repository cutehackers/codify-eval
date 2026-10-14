"""Coordinator closure ordering/source-fence controls without SDK or actors."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import improvement_optional_native_close_v4 as closer


class ClosureControls(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name).resolve()
        self.folder=self.root/'runtime/run';self.folder.mkdir(parents=True);(self.folder/'events').mkdir();(self.folder/'native-observer').mkdir()
        self.root_context=patch.object(closer,'ROOT',self.root);self.root_context.start();self.addCleanup(self.root_context.stop)
        self.native=self.root/'native.jsonl';self.raw=b'original native bytes\n';self.native.write_bytes(self.raw)
        source=self.folder/'final-export';(source/'test').mkdir(parents=True);(source/'test/public.dart').write_text('public')
        (self.folder/'events/00000.json').write_text(json.dumps({'op':'stopped_snapshot','job':'root','export':str(source),'scope_error':None}))
        (self.folder/'registry').mkdir();(self.folder/'registry/configuration.json').write_text(json.dumps({'case_id':'O01'}))
        self.acceptance=self.root/'improvement_cases/fresh-optional-cohort-v1/O01/private/acceptance_test.dart';self.acceptance.parent.mkdir(parents=True);self.acceptance.write_text('private test')
        self.state={'started_at':time.time()-10,'deadline':time.time()+1200,'jobs':{'root':{'status':'removed','container_id':'owned-id'}}}
        self.data={'proof':{'membership':{'root_path':'/root/product','coordinator_native_id':'parent'},'usage':{'total':'original'}},
            'raws':{'/root/product':self.raw},'locators':{'/root/product':self.native},'coordinator_raw':b'original coordinator\n','contracts':{},'ledgers':{}}

    def captured(self,*args):
        out=args[3]
        closer.preserve_raw(out,'root.jsonl',self.raw)
        closer.preserve_raw(out,'coordinator.jsonl',self.data['coordinator_raw'])
        closer.atomic_json(out/'contracts.json',self.data['contracts'],exclusive=True)
        closer.atomic_json(out/'ledgers.json',self.data['ledgers'],exclusive=True)
        return self.data

    def invoke(self):return closer.close(self.folder,self.root/'parent.jsonl','inventory',self.acceptance)

    def test_known_completed_fences_precede_cleanup_and_private_grading(self):
        sequence=[]
        def cleanup(folder):
            self.assertTrue((folder/'native-close/root.jsonl').exists());self.assertTrue((folder/'native-close/audit.json').exists())
            sequence.append('cleanup');return self.state
        def verify(source,folder,deadline,expected_tests):
            self.assertEqual(sequence,['cleanup']);self.assertTrue((source/'test/author_acceptance_test.dart').exists())
            self.assertEqual(deadline,self.state['deadline']);self.assertEqual(expected_tests,24)
            sequence.append('grading');return {'pass':True,'removed':True}
        with patch.object(closer.runtime,'load',return_value=self.state),patch.object(closer,'evidence',side_effect=self.captured),patch.object(closer.runtime,'cleanup',side_effect=cleanup),patch.object(closer.verifier,'verify',side_effect=verify):value=self.invoke()
        self.assertIsNone(value['first_error']);self.assertTrue(value['owned_cleanup_verified']);self.assertTrue(value['software_combined_pass'])
        self.assertEqual(sequence,['cleanup','grading']);self.assertFalse(value['native_qualified']);self.assertFalse(value['whole_final_cost_qualified'])

    def test_unknown_native_audit_denies_cleanup_and_grading(self):
        with patch.object(closer.runtime,'load',return_value=self.state),patch.object(closer,'evidence',side_effect=ValueError('original unknown allocation')),patch.object(closer.runtime,'cleanup') as cleanup,patch.object(closer.verifier,'verify') as verify:
            value=self.invoke();cleanup.assert_not_called();verify.assert_not_called()
        self.assertEqual(value['first_error']['message'],'original unknown allocation');self.assertFalse(value['owned_cleanup_verified'])

    def test_member_source_changed_before_cleanup_denies_effects(self):
        def changed(*args):self.native.write_bytes(b'changed');return self.captured(*args)
        with patch.object(closer.runtime,'load',return_value=self.state),patch.object(closer,'evidence',side_effect=changed),patch.object(closer.runtime,'cleanup') as cleanup:
            value=self.invoke();cleanup.assert_not_called()
        self.assertIn('before stopped cleanup',value['first_error']['message'])

    def test_member_source_changed_after_cleanup_blocks_grading(self):
        def changed(*args):self.native.write_bytes(b'late append');return self.state
        with patch.object(closer.runtime,'load',return_value=self.state),patch.object(closer,'evidence',side_effect=self.captured),patch.object(closer.runtime,'cleanup',side_effect=changed),patch.object(closer.verifier,'verify') as verify:
            value=self.invoke();verify.assert_not_called()
        self.assertTrue(value['owned_cleanup_verified']);self.assertIn('after cleanup',value['first_error']['message'])

    def test_cleanup_failure_retains_original_error_and_never_grades(self):
        with patch.object(closer.runtime,'load',return_value=self.state),patch.object(closer,'evidence',side_effect=self.captured),patch.object(closer.runtime,'cleanup',side_effect=ValueError('original cleanup failure')),patch.object(closer.verifier,'verify') as verify:
            value=self.invoke();verify.assert_not_called()
        self.assertEqual(value['first_error']['message'],'original cleanup failure');self.assertFalse(value['owned_cleanup_verified'])

    def test_no_overwritten_or_restarted_closure(self):
        (self.folder/'native-close').mkdir()
        with patch.object(closer.runtime,'cleanup') as cleanup:
            with self.assertRaises(FileExistsError):self.invoke()
            cleanup.assert_not_called()

    def test_capture_preserves_regular_bytes_and_denies_symlink_or_truncation(self):
        self.assertEqual(closer.capture(self.native,1024),self.raw)
        link=self.root/'link';link.symlink_to(self.native)
        with self.assertRaises(OSError):closer.capture(link,1024)
        original_read=closer.os.read
        def truncate(fd,size):self.native.write_bytes(b'x');return original_read(fd,size)
        with patch.object(closer.os,'read',side_effect=truncate):
            with self.assertRaises(ValueError):closer.capture(self.native,1024)

    def test_growth_during_precleanup_capture_denies_cleanup(self):
        original_read=closer.os.read
        def append(fd,size):
            raw=original_read(fd,size)
            with self.native.open('ab') as stream:stream.write(b'partial delivery')
            return raw
        with patch.object(closer.runtime,'load',return_value=self.state),patch.object(closer,'evidence',side_effect=self.captured),patch.object(closer.os,'read',side_effect=append),patch.object(closer.runtime,'cleanup') as cleanup:
            value=self.invoke();cleanup.assert_not_called()
        self.assertIn('changed during capture',value['first_error']['message'])
        self.assertEqual((self.folder/'native-close/root.jsonl').read_bytes(),self.raw)

    def test_same_size_rewrite_during_capture_denied(self):
        original_read=closer.os.read
        def rewrite(fd,size):
            raw=original_read(fd,size);self.native.write_bytes(b'x'*len(self.raw));return raw
        with patch.object(closer.os,'read',side_effect=rewrite):
            with self.assertRaises(ValueError):closer.capture(self.native,1024)

    def test_original_capture_preserved_when_semantic_audit_fails(self):
        directory=self.folder/'native-dispatch/intents';directory.mkdir(parents=True)
        row={'intent':{'agent_path':'/root/product'},'provision':{}}
        (directory/'root.json').write_text(json.dumps(row))
        parent=self.root/'parent.jsonl';parent.write_bytes(b'original coordinator\n')
        registry_state={'configuration':{'run_id':'run'},'workers':{}}
        with patch.object(closer.runtime,'load',return_value=self.state),patch.object(closer.runtime.registry,'read',return_value=registry_state),patch.object(closer,'find_session',return_value=self.native),patch.object(closer.audit.inventory.core,'parse',side_effect=ValueError('original semantic failure')),patch.object(closer.runtime,'cleanup') as cleanup,patch.object(closer.verifier,'verify') as verify:
            value=self.invoke();cleanup.assert_not_called();verify.assert_not_called()
        out=self.folder/'native-close'
        self.assertEqual(value['first_error']['message'],'original semantic failure')
        self.assertEqual((out/'root.jsonl').read_bytes(),self.raw)
        self.assertEqual((out/'coordinator.jsonl').read_bytes(),parent.read_bytes())
        self.assertEqual(json.loads((out/'root-locator.json').read_bytes())['path'],str(self.native))
        self.assertTrue((out/'dispatch-inputs.json').exists())


if __name__=='__main__':unittest.main()
