"""Actor-free admission, ownership and failure sequencing probes."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import improvement_optional_deadline_control_v1 as subject


class ControlPreparation(unittest.TestCase):
    def test_unfrozen_denies_before_sdk_and_intent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); base = root / 'results'; base.mkdir()
            with patch.object(subject, 'ROOT', root), patch.object(subject, 'BASE', base), \
                    patch.object(subject, 'checked', side_effect=ValueError('not frozen')), \
                    patch.object(subject.shared.runtime, 'create') as create:
                with self.assertRaises(ValueError): subject.prepare('controller')
                create.assert_not_called()
                self.assertEqual(list(base.iterdir()), [])

    def invoke(self, fail=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); base = root / 'results'; base.mkdir()
            (root / 'runtime').mkdir()
            value = {'run_name': subject.deadline.CONTROL, 'actor_path': subject.deadline.CONTROL_ACTOR,
                     'task': subject.TASK}
            order = []
            def create(folder, starting, case, condition, task, paths, record_ownership):
                folder.mkdir(); record_ownership(folder); order.append('owned')
                if fail: raise ValueError('original preparation error')
                return {'root_capability': 'mock_capability'}
            with patch.object(subject, 'ROOT', root), patch.object(subject, 'BASE', base), \
                    patch.object(subject, 'checked', return_value=value), \
                    patch.object(subject.shared.runtime, 'create', side_effect=create), \
                    patch.object(subject.shared.runtime, 'load', return_value={'started_at': 1000, 'deadline': 2200}), \
                    patch.object(subject.shared.broker, 'register'), \
                    patch.object(subject.shared.dispatch, 'create', return_value={'encrypted_request': 'mock'}), \
                    patch.object(subject.shared.runtime, 'failure', side_effect=lambda *args: (_ for _ in ()).throw(ValueError('preservation error'))), \
                    patch.object(subject.shared.runtime, 'cleanup', side_effect=lambda *args: order.append('cleanup') or {'removed': True}):
                if fail:
                    with self.assertRaisesRegex(ValueError, 'original preparation error'): subject.prepare('controller')
                else:
                    subject.prepare('controller')
            output = json.loads((base / 'fresh-optional-deadline-control-preparation-v1.json').read_bytes())
            self.assertTrue((base / 'fresh-optional-deadline-control-allocation-intent-v1.json').is_file())
            return output, order

    def test_original_clock_and_zero_model_allocations(self):
        output, order = self.invoke()
        self.assertEqual((output['original_started_at'], output['deadline']), (1000, 2200))
        self.assertEqual(output['model_actors_allocated'], 0)
        self.assertEqual(order, ['owned'])
        self.assertFalse(output['comparison_admitted'])

    def test_cleanup_attempted_even_if_failure_preservation_raises(self):
        output, order = self.invoke(True)
        self.assertEqual(order, ['owned', 'cleanup'])
        self.assertEqual(output['first_error']['message'], 'original preparation error')
        self.assertEqual(output['preservation_error']['message'], 'preservation error')


if __name__ == '__main__':
    unittest.main()
