import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from snapshot import publish_snapshot, ConflictError, IntegrityError

class Behavior(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'snapshots'
    def tearDown(self):self.tmp.cleanup()
    def make(self,entries=None):return publish_snapshot(self.root,'daily',{'a.txt':b'old'} if entries is None else entries)
    def test_nested_binary_manifest(self):
        entries={'nested/a.bin':bytes(range(256)),'empty':b''};out=self.make(entries)
        self.assertEqual(out,self.root/'daily')
        self.assertEqual({p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()},set(entries)|{'manifest.json'})
        for key,value in entries.items():self.assertEqual((out/key).read_bytes(),value)
        self.assertEqual(json.loads((out/'manifest.json').read_text()),{'files':{k:hashlib.sha256(v).hexdigest() for k,v in entries.items()}})
    def test_empty_snapshot(self):
        out=self.make({});self.assertEqual(json.loads((out/'manifest.json').read_text()),{'files':{}})
    def test_idempotent_without_replacement(self):
        out=self.make();before={p.name:(p.stat().st_ino,p.read_bytes()) for p in out.iterdir()}
        self.assertEqual(self.make(),out)
        self.assertEqual(before,{p.name:(p.stat().st_ino,p.read_bytes()) for p in out.iterdir()})
    def test_conflict_preserves(self):
        out=self.make();before=(out/'manifest.json').read_bytes()
        with self.assertRaises(ConflictError):self.make({'a.txt':b'new'})
        self.assertEqual((out/'a.txt').read_bytes(),b'old');self.assertEqual((out/'manifest.json').read_bytes(),before)
    def test_invalid_paths_create_nothing(self):
        for key in ['/abs','../escape','a/../b','./x','a//b','a/','a\\b','a\x00b','manifest.json','manifest.json/x','']:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):self.make({key:b'x'})
                self.assertFalse(self.root.exists())
    def test_invalid_ids_create_nothing(self):
        for identifier in ['','../x','.x','a b','a'*65,3]:
            with self.subTest(identifier=identifier):
                with self.assertRaises(ValueError):publish_snapshot(self.root,identifier,{})
                self.assertFalse(self.root.exists())
    def test_invalid_content_and_collision(self):
        for entries in [{'a':'text'},{'a':bytearray(b'x')},{'a':b'x','a/b':b'y'},[],{1:b'x'}]:
            with self.subTest(entries=entries):
                with self.assertRaises(ValueError):self.make(entries)
                self.assertFalse(self.root.exists())
    def test_corrupt_bytes_not_repaired(self):
        out=self.make();(out/'a.txt').write_bytes(b'broken')
        with self.assertRaises(IntegrityError):self.make()
        self.assertEqual((out/'a.txt').read_bytes(),b'broken')
    def test_missing_and_extra_files(self):
        out=self.make();(out/'a.txt').unlink()
        with self.assertRaises(IntegrityError):self.make()
        (out/'a.txt').write_bytes(b'old');(out/'extra').write_bytes(b'extra')
        with self.assertRaises(IntegrityError):self.make()
    def test_malformed_manifest(self):
        out=self.make()
        for content in ['not json','[]','{"files": []}','{"files": {}, "extra": 1}','{"files": {"a.txt": "bad"}}']:
            with self.subTest(content=content):
                (out/'manifest.json').write_text(content)
                with self.assertRaises(IntegrityError):self.make()
                self.assertEqual((out/'manifest.json').read_text(),content)
    def test_integrity_before_conflict(self):
        out=self.make();(out/'a.txt').write_bytes(b'bad')
        with self.assertRaises(IntegrityError):self.make({'different':b'data'})
    def test_invalid_input_before_integrity(self):
        out=self.make();(out/'a.txt').write_bytes(b'bad')
        with self.assertRaises(ValueError) as raised:self.make({'../escape':b'x'})
        self.assertNotIsInstance(raised.exception,IntegrityError)
    def test_symlinks_rejected(self):
        out=self.make();external=Path(self.tmp.name)/'external';external.write_bytes(b'old')
        (out/'a.txt').unlink();(out/'a.txt').symlink_to(external)
        with self.assertRaises(IntegrityError):self.make()
        self.assertEqual(external.read_bytes(),b'old')
    def test_root_and_destination_symlinks(self):
        real=Path(self.tmp.name)/'real';real.mkdir();self.root.symlink_to(real,target_is_directory=True)
        with self.assertRaises(ValueError):self.make()
        self.root.unlink();self.root.mkdir();(self.root/'daily').symlink_to(real,target_is_directory=True)
        with self.assertRaises(IntegrityError):self.make()
        self.assertEqual(list(real.iterdir()),[])
    def test_promotion_failure_cleanup_and_retry(self):
        self.root.mkdir();sentinel=self.root/'unrelated';sentinel.write_bytes(b'keep')
        publish_snapshot(self.root,'prior',{'p':b'prior'})
        before={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        real_replace=os.replace
        def fail(source,destination):
            staged=Path(source)
            self.assertEqual((staged/'a.txt').read_bytes(),b'old')
            self.assertTrue((staged/'manifest.json').exists())
            self.assertFalse(Path(destination).exists())
            raise OSError('injected promotion failure')
        with patch('os.replace',side_effect=fail):
            with self.assertRaises(OSError):self.make()
        self.assertEqual(before,{p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual({p.name for p in self.root.iterdir()},{'unrelated','prior'})
        self.assertEqual((self.make()/'a.txt').read_bytes(),b'old')
