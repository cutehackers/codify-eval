"""Actor-free DRAFT adapter tests. Synthetic admission is not launch authority."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import improvement_optional_comparison_driver_v1 as driver


class Probes(unittest.TestCase):
    def test_all_exact_rows_and_unqualified_rejection_before_effects(self):
        for row in driver.inputs.sequence():
            driver.paths(row)
            with patch.object(driver.runtime, 'create') as create:
                with self.assertRaisesRegex(ValueError, 'DRAFT unqualified'):
                    driver.prepare(row, 'original_parent')
                create.assert_not_called()
            with self.assertRaises(ValueError):
                driver.paths(dict(row, repeat=True))

    def fixture(self, root, condition, case_id='O01'):
        case = root / 'improvement_cases/fresh-optional-cohort-v1' / case_id
        (case / 'repo/lib').mkdir(parents=True)
        (case / 'repo/lib/service.dart').write_text('starting')
        (case / 'public').mkdir()
        (case / 'public/request.md').write_text('public synthetic contract')
        (case / 'metadata.json').write_text(json.dumps({'editable_paths': ['lib/service.dart']}))
        skill = root / 'snapshots' / condition
        skill.mkdir(parents=True)
        (skill / 'SKILL.md').write_text('synthetic selected ' + condition)
        return next(r for r in driver.inputs.sequence() if r['case_id'] == case_id and r['condition'] == condition)

    def test_prepare_routes_skill_inside_original_create_and_restores_hook(self):
        for registered in driver.inputs.sequence():
            condition, case_id = registered['condition'], registered['case_id']
            with self.subTest(condition=condition, case_id=case_id), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve(); row = self.fixture(root, condition, case_id)
                base = root / 'results/improvement-v1'; base.mkdir(parents=True)
                original = driver.runtime.source.export
                def create(folder, starting, case, treatment, task, scopes, record_ownership):
                    self.assertEqual((case, treatment), (case_id, condition))
                    self.assertIn('zero, one or two', task)
                    self.assertNotIn('Allocate exactly', task)
                    (folder / 'root').mkdir(parents=True); record_ownership(folder)
                    # Only create invokes the export; this is the original clock.
                    driver.runtime.source.export(starting, driver.runtime.source.inventory(starting),
                                                 folder / 'root/repo', None)
                    target = folder / 'root/repo/.agents/skills/codify/SKILL.md'
                    self.assertEqual(target.exists(), condition != 'A')
                    if target.exists(): self.assertEqual(target.read_text(), 'synthetic selected ' + condition)
                    return {'root_capability': 'cap'}
                with patch.object(driver, 'ROOT', root), patch.object(driver, 'BASE', base), \
                     patch.object(driver.inputs, 'ROOT', root), patch.object(driver, 'admission'), \
                     patch.object(driver, 'previous_reviews'), patch.object(driver.runtime, 'create', create), \
                     patch.object(driver.broker, 'register'), patch.object(driver.dispatch, 'create', return_value={'native_bootstrap': 'original'}), \
                     patch.object(driver.runtime, 'load', return_value={'started_at': 10, 'deadline': 1210}), \
                     patch.object(driver.runtime, 'failure'), patch.object(driver.runtime, 'cleanup'):
                    value = driver.prepare(row, 'parent_uuid')
                    self.assertEqual(value['root_dispatch']['native_bootstrap'], 'original')
                    self.assertEqual(value['deadline'], 1210)
                    with self.assertRaisesRegex(ValueError, 'No retry'):
                        driver.prepare(row, 'parent_uuid')
                self.assertIs(driver.runtime.source.export, original)

    def test_owned_failure_retained_cleanup_and_hook_restoration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve();row = self.fixture(root, 'C16');base = root / 'results/improvement-v1';base.mkdir(parents=True)
            original = driver.runtime.source.export
            def broken(folder, *args, **kwargs):
                folder.mkdir(parents=True);kwargs['record_ownership'](folder)
                raise RuntimeError('original preparation error')
            with patch.object(driver, 'ROOT', root), patch.object(driver, 'BASE', base), patch.object(driver.inputs, 'ROOT', root), \
                 patch.object(driver, 'admission'), patch.object(driver, 'previous_reviews'), patch.object(driver.runtime, 'create', broken), \
                 patch.object(driver.runtime, 'failure') as preserve, patch.object(driver.runtime, 'cleanup', side_effect=ValueError('cleanup failed')):
                with self.assertRaisesRegex(RuntimeError, 'original preparation error'):driver.prepare(row, 'parent')
                preserve.assert_called_once()
            self.assertIs(driver.runtime.source.export, original)
            value=json.loads((base/(row['run_id']+'-preparation.json')).read_text())
            self.assertEqual(value['first_error']['message'], 'original preparation error')
            self.assertEqual(value['cleanup_error']['message'], 'cleanup failed')
            self.assertFalse(value['native_qualified'])

    def test_sequence_requires_exact_original_review_and_no_retries(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(driver, 'BASE', Path(tmp)):
            rows=driver.inputs.sequence();driver.previous_reviews(rows[0])
            with self.assertRaises(FileNotFoundError):driver.previous_reviews(rows[1])
            path=Path(tmp)/(rows[0]['run_id']+'-independent-review.json')
            review={'run_id':'other','verdict':'pass','issues':[], 'complete_observation':True,'owned_cleanup_verified':True}
            path.write_text(json.dumps(review))
            with self.assertRaises(ValueError):driver.previous_reviews(rows[1])
            review['run_id']=rows[0]['run_id'];review['owned_cleanup_verified']=False;path.write_text(json.dumps(review))
            with self.assertRaises(ValueError):driver.previous_reviews(rows[1])
            review['owned_cleanup_verified']=True;path.write_text(json.dumps(review));driver.previous_reviews(rows[1])


if __name__ == '__main__':
    unittest.main()
