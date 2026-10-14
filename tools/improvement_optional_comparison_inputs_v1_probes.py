"""Actor-free treatment, naming and protected-source injection probes."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import improvement_optional_comparison_inputs_v1 as inputs


class Probes(unittest.TestCase):
    def test_balanced_matrix_and_actual_native_name_constraints(self):
        rows = inputs.sequence()
        self.assertEqual(rows, inputs.sequence())
        self.assertEqual(len(rows), 6)
        self.assertEqual(len({r['run_id'] for r in rows}), 6)
        for row in rows:
            inputs.row_valid(row)
            self.assertRegex(row['actor_path'], r'^/root/[a-z0-9_]+$')
        changed = dict(rows[0], repeat=True)
        with self.assertRaises(Exception):
            inputs.row_valid(changed)

    def test_skill_is_added_inside_root_export_and_hook_always_restored(self):
        for condition in inputs.CONDITIONS:
            with self.subTest(condition=condition), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                case = root / 'improvement_cases/fresh-optional-cohort-v1/O01'
                (case / 'repo/lib').mkdir(parents=True)
                (case / 'repo/lib/source.dart').write_text('public starting source')
                (case / 'public').mkdir()
                (case / 'public/request.md').write_text('public task')
                skill = root / 'snapshots' / condition
                skill.mkdir(parents=True)
                (skill / 'SKILL.md').write_text('selected skill ' + condition)
                row = next(r for r in inputs.sequence()
                           if r['case_id'] == 'O01' and r['condition'] == condition)
                folder = root / 'runtime' / row['run_id']
                (folder / 'root').mkdir(parents=True)
                deadline = time.time() + 60
                original = inputs.runtime.source.export
                with patch.object(inputs, 'ROOT', root):
                    task = inputs.public_task(row)
                    self.assertIn('zero, one or two', task)
                    self.assertNotIn('exactly 2', task)
                    with inputs.skill_export(row, folder):
                        inventory = inputs.runtime.source.inventory(case / 'repo', deadline)
                        inputs.runtime.source.export(case / 'repo', inventory,
                                                     folder / 'root/repo', deadline)
                    self.assertIs(inputs.runtime.source.export, original)
                    target = folder / 'root/repo/.agents/skills/codify/SKILL.md'
                    self.assertEqual(target.exists(), condition != 'A')
                    if condition != 'A':
                        self.assertEqual(target.read_text(), 'selected skill ' + condition)
                        self.assertIn('Every allocated worker', task)
                    self.assertEqual((folder / 'root/repo/lib/source.dart').read_text(),
                                     'public starting source')
                    with self.assertRaisesRegex(RuntimeError, 'original failure'):
                        with inputs.skill_export(row, folder):
                            raise RuntimeError('original failure')
                    self.assertIs(inputs.runtime.source.export, original)


if __name__ == '__main__':
    unittest.main()
