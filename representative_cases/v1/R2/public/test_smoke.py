import tempfile
import unittest
from pathlib import Path
from outbox import Outbox

class Smoke(unittest.TestCase):
    def test_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            box = Outbox(Path(directory) / 'outbox.sqlite')
            try:
                identifier = box.enqueue('shop', 'welcome', {'email': 'user@example.test'})
                self.assertEqual(box.claim('shop', 0, 10, 1)[0]['id'], identifier)
                self.assertTrue(box.complete('shop', identifier))
                self.assertEqual(box.claim('shop', 20, 10, 1), [])
            finally:
                box.close()
