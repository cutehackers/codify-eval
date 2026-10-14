"""Control driver preregistration and preparation failure tests, no SDK/actors."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import improvement_optional_native_control_v1 as driver


class DriverControls(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();self.base=self.root/'results';self.base.mkdir()
        (self.root/'runtime').mkdir();self.case=self.root/'case';(self.case/'public').mkdir(parents=True);(self.case/'repo').mkdir()
        (self.case/'public/request.md').write_text('Visible domain requirements only.\n')
        (self.case/'metadata.json').write_text(json.dumps({'editable_paths':['a','b','c']}))
        for attribute,value in [('ROOT',self.root),('BASE',self.base),('CASE',self.case),('FREEZE',self.base/'freeze.json')]:
            context=patch.object(driver,attribute,value);context.start();self.addCleanup(context.stop)

    def test_public_task_contains_only_public_case_plus_control_policy(self):
        for scenario,count in driver.COUNTS.items():
            task=driver.public_task(scenario)
            self.assertIn(f'exactly {count} cumulative worker',task);self.assertIn('Visible domain requirements',task)
            self.assertNotIn('oracle',task);self.assertNotIn('reference implementation',task)

    def test_unregistered_or_missing_prior_control_rejected_before_create(self):
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create') as create:
            with self.assertRaises(ValueError):driver.prepare('unregistered','coordinator')
            with self.assertRaises(FileNotFoundError):driver.prepare('one_worker','coordinator')
            create.assert_not_called()

    def test_existing_namespace_never_restarted_or_cleaned(self):
        (self.root/'runtime/native-optional-control-v1-solo').mkdir()
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create') as create,patch.object(driver.runtime,'cleanup') as cleanup:
            with self.assertRaises(ValueError):driver.prepare('solo','coordinator')
            create.assert_not_called();cleanup.assert_not_called()

    def test_original_preparation_error_is_preserved_and_owned_actorfree_cleanup_runs(self):
        error=ValueError('original preparation failure')
        def create(folder,*args):folder.mkdir();raise error
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create',side_effect=create),patch.object(driver.runtime,'failure') as failure,patch.object(driver.runtime,'cleanup',return_value={'removed':True}) as cleanup:
            with self.assertRaisesRegex(ValueError,'original preparation failure'):driver.prepare('solo','coordinator')
            failure.assert_called_once();cleanup.assert_called_once()
        result=json.loads((self.base/'fresh-optional-native-control-preparation-v1-solo.json').read_bytes())
        self.assertEqual(result['first_error']['message'],str(error));self.assertEqual(result['model_actors_allocated'],0)
        self.assertTrue(result['owned_cleanup']['removed']);self.assertFalse(result['native_qualified'])

    def test_cleanup_failure_does_not_replace_original_error(self):
        error=ValueError('original setup')
        def create(folder,*args):folder.mkdir();raise error
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create',side_effect=create),patch.object(driver.runtime,'failure'),patch.object(driver.runtime,'cleanup',side_effect=ValueError('cleanup unknown')):
            with self.assertRaisesRegex(ValueError,'original setup'):driver.prepare('solo','coordinator')
        result=json.loads((self.base/'fresh-optional-native-control-preparation-v1-solo.json').read_bytes())
        self.assertEqual(result['first_error']['message'],'original setup');self.assertEqual(result['cleanup_error']['message'],'cleanup unknown')

    def test_preparation_emits_exact_observer_route_without_allocating_models(self):
        def create(folder,*args):folder.mkdir();return {'root_capability':'a'*48}
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create',side_effect=create),patch.object(driver.runtime,'load',return_value={'started_at':100,'deadline':1300}),patch.object(driver.broker,'register'),patch.object(driver.dispatch,'create',return_value={'native_bootstrap':'original role bootstrap'}):
            value=driver.prepare('solo','coordinator')
        self.assertEqual(value['model_actors_allocated'],0)
        self.assertEqual(value['actor_path'],'/root/native_optional_control_v1_solo')
        self.assertEqual(value['observer_argv'][-3:],['native-optional-control-v1-solo',value['actor_path'],'coordinator'])
        self.assertFalse(value['native_qualified'])


if __name__=='__main__':unittest.main()
