"""Actual isolated Git cache refresh and protected-index regression controls."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import improvement_optional_runtime_v10 as runtime


class IndexControls(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.origin=self.base/'origin';self.origin.mkdir()
        self.env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')
        (self.origin/'lib').mkdir();(self.origin/'lib/codec.dart').write_text('initial\n')
        (self.origin/'README.md').write_text('protected\n')
        self.git(self.origin,'init','-q')

    def git(self,folder,*args):
        return subprocess.run(['git',*args],cwd=folder,env=self.env,check=True,capture_output=True,text=True).stdout

    def checkout(self,disabled):
        if disabled:self.git(self.origin,'config','diff.autoRefreshIndex','false')
        self.git(self.origin,'add','.')
        self.git(self.origin,'-c','user.name=Fixture','-c','user.email=fixture@localhost','commit','-q','-m','baseline')
        copied=self.base/'worker';shutil.copytree(self.origin,copied)
        before=runtime.source.inventory(copied)
        (copied/'lib/codec.dart').write_text('implemented\n')
        return copied,before

    def test_original_default_diff_refresh_reproduces_false_positive(self):
        copied,before=self.checkout(False)
        self.git(copied,'diff','--check');self.git(copied,'diff','--stat')
        after=runtime.source.inventory(copied)
        self.assertNotEqual(before['git_entities']['.git/index'],after['git_entities']['.git/index'])
        with self.assertRaisesRegex(ValueError,'Git administrative tree changed'):
            runtime.source.check_changes(before,after,['lib/codec.dart'])
        self.assertEqual(self.git(copied,'diff','--cached'),'')

    def test_prebaseline_configuration_preserves_exact_git_guard(self):
        copied,before=self.checkout(True)
        self.assertEqual(self.git(copied,'config','--get','diff.autoRefreshIndex').strip(),'false')
        self.git(copied,'diff','--check');self.git(copied,'diff','--stat')
        after=runtime.source.inventory(copied)
        self.assertEqual(before['git_entities'],after['git_entities'])
        runtime.source.check_changes(before,after,['lib/codec.dart'])

    def test_actual_staging_still_changes_index_and_is_rejected(self):
        copied,before=self.checkout(True)
        self.git(copied,'add','lib/codec.dart')
        after=runtime.source.inventory(copied)
        self.assertNotEqual(self.git(copied,'diff','--cached'),'')
        with self.assertRaisesRegex(ValueError,'Git administrative tree changed'):
            runtime.source.check_changes(before,after,['lib/codec.dart'])


if __name__=='__main__':unittest.main()
