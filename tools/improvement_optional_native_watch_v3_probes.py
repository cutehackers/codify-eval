"""Synthetic native samples and real filesystem observer closure controls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import improvement_optional_native_watch_v3 as watch
import improvement_optional_routes_v3_probes as fixtures


class ObserverControls(unittest.TestCase):
    def fixture(self):
        events,binding,_,_=fixtures.Controls().fixture()
        return events,binding

    def sample(self,events,binding,**kwargs):
        return watch.sample(fixtures.encode(events),binding['agent_path'],binding['parent_native_id'],**kwargs)

    def test_original_full_completion_has_no_cleanup_or_qualification(self):
        events,binding=self.fixture();value=self.sample(events,binding)
        self.assertTrue(value['normal_completion_observed']);self.assertEqual(value['completed_turns'],1)
        self.assertFalse(value['native_qualified']);self.assertFalse(value['cleanup_authorized'])

    def test_incomplete_trailing_append_never_proves_completion(self):
        events,binding=self.fixture();raw=fixtures.encode(events)+b'{"timestamp":'
        value=watch.sample(raw,binding['agent_path'],binding['parent_native_id'])
        self.assertFalse(value['raw_prefix_complete']);self.assertFalse(value['normal_completion_observed'])
        self.assertEqual(value['raw_bytes'],len(raw))

    def test_open_context_is_not_completion(self):
        events,binding=self.fixture();value=self.sample(events[:-2],binding)
        self.assertFalse(value['normal_completion_observed']);self.assertEqual(value['completed_turns'],0)

    def test_model_reasoning_or_collaboration_changes_denied(self):
        for field,value in [('model','gpt-6-sol'),('effort','high'),('collaboration_mode',{'settings':{'model':'gpt-6.1-sol','reasoning_effort':'high'}})]:
            events,binding=self.fixture();events[2]['payload'][field]=value
            with self.assertRaises(ValueError):self.sample(events,binding)

    def test_parent_path_and_nested_origin_conflicts_denied(self):
        for location in ('parent_thread_id','agent_path','nested'):
            events,binding=self.fixture()
            if location=='nested':events[0]['payload']['source']['subagent']['thread_spawn']['parent_thread_id']='foreign'
            else:events[0]['payload'][location]='foreign'
            with self.assertRaises(ValueError):self.sample(events,binding)

    def test_append_rewrite_and_duplicate_header_denied(self):
        events,binding=self.fixture()
        with self.assertRaises(ValueError):self.sample(events,binding,previous=b'wrong')
        events.insert(1,copy.deepcopy(events[0]))
        with self.assertRaises(ValueError):self.sample(events,binding)

    def test_task_complete_without_original_final_denied(self):
        events,binding=self.fixture();events.pop(-2)
        with self.assertRaises(ValueError):self.sample(events,binding)

    def test_extra_turn_or_repeated_completion_denied(self):
        for event in ('context','completion'):
            events,binding=self.fixture();events.append(copy.deepcopy(events[2] if event=='context' else events[-1]));events[-1]['timestamp']='2026-10-12T00:00:15Z'
            with self.assertRaises(ValueError):self.sample(events,binding)

    def test_nonfinite_duplicate_json_or_incomplete_header_denied(self):
        events,binding=self.fixture();raw=fixtures.encode(events)
        for changed in (raw.replace(b'"id": "native-root"',b'"id":"native-root","id":"other"'),
                        raw.replace(b'"id": "native-root"',b'"id":"native-root","bad":1e999'),b'{'):
            with self.assertRaises(ValueError):watch.sample(changed,binding['agent_path'],binding['parent_native_id'])

    def test_real_regular_reader_denies_symlink_and_preserves_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'native';path.write_bytes(b'partial');link=Path(folder)/'link';link.symlink_to(path)
            self.assertEqual(watch.native_bytes(path),b'partial')
            with self.assertRaises(OSError):watch.native_bytes(link)

    def test_truncation_during_read_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'native';path.write_bytes(b'original bytes')
            original_read=watch.os.read
            def truncated(fd,amount):
                path.write_bytes(b'x')
                return original_read(fd,amount)
            with patch.object(watch.os,'read',side_effect=truncated):
                with self.assertRaises(ValueError):watch.native_bytes(path)

    def test_pathname_replacement_during_read_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'native';path.write_bytes(b'original bytes')
            original_read=watch.os.read
            def replaced(fd,amount):
                path.rename(Path(folder)/'old-native');path.write_bytes(b'new source bytes')
                return original_read(fd,amount)
            with patch.object(watch.os,'read',side_effect=replaced):
                with self.assertRaises(ValueError):watch.native_bytes(path)

    def test_ordinary_append_during_read_preserves_original_observed_prefix(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'native';path.write_bytes(b'original bytes')
            original_read=watch.os.read
            def appended(fd,amount):
                with path.open('ab') as stream:stream.write(b' extra')
                return original_read(fd,amount)
            with patch.object(watch.os,'read',side_effect=appended):
                self.assertTrue(watch.native_bytes(path).startswith(b'original bytes'))

    def service(self,pending=False):
        events,binding=self.fixture();started=watch.core.instant('2026-10-12T00:00:00Z').timestamp()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();folder=root/'runtime/probe';(folder/'registry').mkdir(parents=True);(folder/'registry').rmdir()
            tree={'.':{'kind':'directory','mode':493},**{f'{n}.dart':{'kind':'file','mode':420,'sha256':'a'*64} for n in range(3)}}
            with patch.object(watch.time,'time',return_value=started+20):watch.registry.create(folder/'registry','probe','O01','A',started,tree,[f'{n}.dart' for n in range(3)])
            native=root/'native.jsonl';native.write_bytes(fixtures.encode(events))
            def discover(path):
                watch.atomic_json(folder/'native-observer/stop.json',{'reason':'coordinator_stop','root_path':binding['agent_path'],'parent_id':binding['parent_native_id']},exclusive=True)
                if pending:raise ValueError('Expected one owned session for '+path+', found 0')
                return native
            original_replay=watch.registry.read
            def locked_replay(folder):
                import fcntl
                with (Path(folder)/'lock').open('a+b') as stream:
                    with self.assertRaises(BlockingIOError):fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
                return original_replay(folder)
            with patch.object(watch.registry,'read',side_effect=locked_replay),patch.object(watch,'ROOT',root),patch.object(watch,'find_session',side_effect=discover),patch.object(watch.time,'time',return_value=started+20):
                value=watch.supervise(folder,binding['agent_path'],binding['parent_native_id'])
            terminal=json.loads((folder/'native-observer/terminal.json').read_bytes())
            return value,terminal

    def test_real_filesystem_service_observes_original_complete_source(self):
        value,terminal=self.service();self.assertTrue(value['all_registered_normal_completions_observed'])
        self.assertEqual(terminal['reason'],'coordinator_stop');self.assertFalse(terminal['cleanup_authorized'])

    def test_coordinator_stop_with_missing_native_source_never_means_completed(self):
        value,terminal=self.service(pending=True)
        self.assertEqual(value['pending_native_jobs'],['root']);self.assertFalse(value['all_registered_normal_completions_observed'])
        self.assertFalse(terminal['normal_completions_observed'])


if __name__=='__main__':unittest.main()
