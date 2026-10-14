"""Safe inventory/projection controls. No actor/container qualification."""
import copy
import os
from pathlib import Path
import tempfile
import time
import unittest

import improvement_optional_source_v1 as source
from improvement_software_artifacts_v3 import tree


class SourceProjectionControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.repo=self.base/'repo';(self.repo/'lib').mkdir(parents=True)
        (self.repo/'test').mkdir();(self.repo/'lib/main.dart').write_text('source\n')
        (self.repo/'test/contract_test.dart').write_text('protected test\n')
        (self.repo/'pubspec.lock').write_text('prepared dependency lock\n')
        (self.repo/'.git').mkdir();(self.repo/'.git/HEAD').write_text('protected ref\n')
        self.before=source.inventory(self.repo)

    def test_large_cache_is_fully_inventoried_then_excluded_from_export(self):
        (self.repo/'.dart_tool').mkdir();(self.repo/'.dart_tool/kernel').write_bytes(b'x'*(2*1024*1024))
        (self.repo/'build').mkdir();(self.repo/'build/result').write_bytes(b'build')
        snapshot=source.inventory(self.repo)
        self.assertIn('.dart_tool/kernel',snapshot['all_entities'])
        self.assertNotIn('.dart_tool/kernel',snapshot['source_entities'])
        self.assertTrue(source.check_changes(self.before,snapshot,['lib/main.dart']))
        destination=self.base/'canonical';source.export(self.repo,snapshot,destination)
        self.assertEqual(tree(destination),snapshot['source_entities'])
        self.assertFalse((destination/'.git').exists())

    def test_nested_build_name_is_protected_not_recursively_ignored(self):
        (self.repo/'lib/build').mkdir();(self.repo/'lib/build/data.dart').write_text('new')
        with self.assertRaises(ValueError):source.check_changes(self.before,source.inventory(self.repo),['lib/main.dart'])

    def test_public_test_lock_and_git_changes_denied(self):
        for name in ('test/contract_test.dart','pubspec.lock','.git/HEAD'):
            path=self.repo/name;original=path.read_bytes();path.write_bytes(b'tampered')
            with self.assertRaises(ValueError):source.check_changes(self.before,source.inventory(self.repo),['lib/main.dart'])
            path.write_bytes(original)

    def test_editable_contents_allowed_but_mode_denied(self):
        path=self.repo/'lib/main.dart';path.write_text('implementation')
        self.assertTrue(source.check_changes(self.before,source.inventory(self.repo),['lib/main.dart']))
        os.chmod(path,0o600)
        with self.assertRaises(ValueError):source.check_changes(self.before,source.inventory(self.repo),['lib/main.dart'])

    def test_symlinks_and_fifo_inside_generated_not_hidden(self):
        cache=self.repo/'.dart_tool';cache.mkdir()
        foreign=self.base/'foreign';foreign.write_text('never follow')
        link=cache/'link';link.symlink_to(foreign)
        with self.assertRaises(ValueError):source.inventory(self.repo)
        link.unlink();os.mkfifo(link)
        with self.assertRaises(ValueError):source.inventory(self.repo)
        with self.assertRaises(ValueError):source.read_file(link)

    def test_generated_root_symlink_and_nondirectory_denied(self):
        path=self.repo/'build';path.symlink_to(self.repo/'lib',target_is_directory=True)
        with self.assertRaises(ValueError):source.inventory(self.repo)
        path.unlink();path.write_text('invalid generated root')
        with self.assertRaises(ValueError):source.inventory(self.repo)

    def test_byte_entity_and_original_deadline_bounds(self):
        with self.assertRaises(ValueError):source.inventory(self.repo,max_bytes=1)
        with self.assertRaises(ValueError):source.inventory(self.repo,max_entities=2)
        with self.assertRaises(ValueError):source.inventory(self.repo,deadline=time.time()-1)
        with self.assertRaises(ValueError):source.inventory(self.repo,deadline=float('inf'))

    def test_stale_or_forged_projection_denied_before_export(self):
        forged=copy.deepcopy(self.before);forged['source_entities'].update(forged['git_entities'])
        destination=self.base/'canonical'
        with self.assertRaises(ValueError):source.export(self.repo,forged,destination)
        self.assertFalse(destination.exists())
        (self.repo/'lib/main.dart').write_text('changed')
        with self.assertRaises(ValueError):source.export(self.repo,self.before,destination)
        self.assertFalse(destination.exists())

    def test_export_cannot_write_inside_checkout_or_reuse_namespace(self):
        with self.assertRaises(ValueError):source.export(self.repo,self.before,self.repo/'new')
        destination=self.base/'canonical';source.export(self.repo,self.before,destination)
        with self.assertRaises(FileExistsError):source.export(self.repo,self.before,destination)


if __name__=='__main__':unittest.main()
