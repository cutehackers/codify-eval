import json
import tempfile
import unittest
from pathlib import Path
from snapshot import publish_snapshot

class Smoke(unittest.TestCase):
    def test_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            result=publish_snapshot(Path(directory)/'snapshots','daily',{'notes.txt':b'hello'})
            self.assertEqual((result/'notes.txt').read_bytes(),b'hello')
            self.assertIn('notes.txt',json.loads((result/'manifest.json').read_text())['files'])
