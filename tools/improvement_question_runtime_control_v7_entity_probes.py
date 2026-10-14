"""Review-to-freeze mode continuity, no product/native allocations."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import improvement_question_runtime_control_v7 as control


class Probes(unittest.TestCase):
    def test_review_entities_reject_same_sha_mode_change(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'source.py'; source.write_text('same bytes')
            expected=control.entity(source)
            review=root/'review.json'; review.write_text(json.dumps({
                'verdict':'pass','issues':[], 'source_hashes':{'source.py':expected['sha256']},
                'source_entities':{'source.py':expected}}))
            with patch.object(control,'ROOT',root):
                control.check_review(review,set(),[source])
                source.chmod(0o600 if expected['mode']!=0o600 else 0o644)
                self.assertEqual(control.legacy.sha(source),expected['sha256'])
                with self.assertRaisesRegex(AssertionError,'Review source entity changed'):
                    control.check_review(review,set(),[source])

    def test_source_entity_only_review_is_consumed_and_cannot_add_symlink(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); source=root/'source.py'; source.write_text('same bytes')
            review=root/'review.json'; review.write_text(json.dumps({
                'verdict':'pass','issues':[], 'source_entities':{'source.py':control.entity(source)}}))
            with patch.object(control,'ROOT',root):
                names=set(); control.check_review(review,names,[source]); self.assertIn(source,names)
                moved=root/'other.py'; source.rename(moved); source.symlink_to(moved)
                with self.assertRaises(AssertionError): control.check_review(review,set(),[source])


if __name__=='__main__': unittest.main()
