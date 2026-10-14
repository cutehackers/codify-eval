"""Control driver preregistration and preparation failure tests, no SDK/actors."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import improvement_optional_native_control_v9 as driver


class DriverControls(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve();self.base=self.root/'results';self.base.mkdir()
        (self.root/'runtime').mkdir();self.case=self.root/'case';(self.case/'public').mkdir(parents=True);(self.case/'repo').mkdir()
        (self.case/'public/request.md').write_text('Visible domain requirements only.\n')
        (self.case/'private').mkdir();(self.case/'private/acceptance_test.dart').write_text('evaluator private fixture')
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
        (self.root/'runtime/native-optional-control-v9-solo').mkdir()
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create') as create,patch.object(driver.runtime,'cleanup') as cleanup:
            with self.assertRaises(ValueError):driver.prepare('solo','coordinator')
            create.assert_not_called();cleanup.assert_not_called()

    def test_original_preparation_error_is_preserved_and_owned_actorfree_cleanup_runs(self):
        error=ValueError('original preparation failure')
        def create(folder,*args,record_ownership=None):folder.mkdir();record_ownership(folder);raise error
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create',side_effect=create),patch.object(driver.runtime,'failure') as failure,patch.object(driver.runtime,'cleanup',return_value={'removed':True}) as cleanup:
            with self.assertRaisesRegex(ValueError,'original preparation failure'):driver.prepare('solo','coordinator')
            failure.assert_called_once();cleanup.assert_called_once()
        result=json.loads((self.base/'fresh-optional-native-control-preparation-v9-solo.json').read_bytes())
        self.assertEqual(result['first_error']['message'],str(error));self.assertEqual(result['model_actors_allocated'],0)
        self.assertTrue(result['owned_cleanup']['removed']);self.assertFalse(result['native_qualified'])

    def test_cleanup_failure_does_not_replace_original_error(self):
        error=ValueError('original setup')
        def create(folder,*args,record_ownership=None):folder.mkdir();record_ownership(folder);raise error
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create',side_effect=create),patch.object(driver.runtime,'failure'),patch.object(driver.runtime,'cleanup',side_effect=ValueError('cleanup unknown')):
            with self.assertRaisesRegex(ValueError,'original setup'):driver.prepare('solo','coordinator')
        result=json.loads((self.base/'fresh-optional-native-control-preparation-v9-solo.json').read_bytes())
        self.assertEqual(result['first_error']['message'],'original setup');self.assertEqual(result['cleanup_error']['message'],'cleanup unknown')

    def test_race_lost_directory_is_not_modified_or_cleaned(self):
        def other_owner(folder,*args,record_ownership=None):
            folder.mkdir();(folder/'foreign-proof').write_text('another invocation')
            raise FileExistsError('another invocation owns runtime')
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create',side_effect=other_owner),patch.object(driver.runtime,'failure') as failure,patch.object(driver.runtime,'cleanup') as cleanup:
            with self.assertRaises(FileExistsError):driver.prepare('solo','coordinator')
            failure.assert_not_called();cleanup.assert_not_called()
        result=json.loads((self.base/'fresh-optional-native-control-preparation-v9-solo.json').read_bytes())
        self.assertFalse(result['runtime_ownership_observed'])
        self.assertEqual((self.root/'runtime/native-optional-control-v9-solo/foreign-proof').read_text(),'another invocation')

    def test_missing_coordinator_rejected_before_allocation(self):
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create') as create:
            for identity in ('',None,True,'bad identity'):
                with self.assertRaises(ValueError):driver.prepare('solo',identity)
            create.assert_not_called()

    def test_freeze_cannot_omit_reviews_or_dependencies(self):
        required={str(Path(module.__file__).resolve()):driver.entity(module.__file__) for module in (driver,driver.runtime,driver.broker,driver.dispatch,driver.observer,driver.audit,driver.closer,driver.verifier)}
        for name in driver.REVIEWS:(self.base/name).write_text(json.dumps({'verdict':'pass','issues':[],'source_entities':required}))
        original=driver.freeze();driver.checked_freeze()
        for changed in ('reviews','source_entities'):
            value=dict(original,**{changed:{}});driver.FREEZE.write_text(json.dumps(value))
            with self.assertRaises(ValueError):driver.checked_freeze()
        driver.FREEZE.write_text(json.dumps(original))

    def test_concurrent_loser_cannot_publish_output_or_cancel_winner(self):
        import concurrent.futures
        import threading
        entered=threading.Event();release=threading.Event();calls=[]
        def create(folder,*args,record_ownership=None):
            calls.append(folder);entered.set();self.assertTrue(release.wait(2))
            folder.mkdir();record_ownership(folder);return {'root_capability':'a'*48}
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create',side_effect=create),patch.object(driver.runtime,'load',return_value={'started_at':100,'deadline':1300}),patch.object(driver.broker,'register'),patch.object(driver.dispatch,'create',return_value={'native_bootstrap':'original role bootstrap'}),patch.object(driver.runtime,'failure') as failure,patch.object(driver.runtime,'cleanup') as cleanup:
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                winner=pool.submit(driver.prepare,'solo','coordinator');self.assertTrue(entered.wait(2))
                loser=pool.submit(driver.prepare,'solo','coordinator')
                try:
                    with self.assertRaises(FileExistsError):loser.result(2)
                finally:release.set()
                value=winner.result(2)
            failure.assert_not_called();cleanup.assert_not_called()
        self.assertEqual(len(calls),1);self.assertEqual(value['model_actors_allocated'],0)
        result=json.loads((self.base/'fresh-optional-native-control-preparation-v9-solo.json').read_bytes())
        self.assertEqual(result['root_dispatch']['native_bootstrap'],'original role bootstrap')

    def test_failed_attempt_admission_cannot_be_retried_with_same_namespace(self):
        error=ValueError('preallocation failure')
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create',side_effect=error) as create:
            with self.assertRaises(ValueError):driver.prepare('solo','coordinator')
            with self.assertRaises(ValueError):driver.prepare('solo','coordinator')
            self.assertEqual(create.call_count,1)

    def test_preparation_emits_exact_observer_route_without_allocating_models(self):
        def create(folder,*args,record_ownership=None):folder.mkdir();record_ownership(folder);return {'root_capability':'a'*48}
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create',side_effect=create),patch.object(driver.runtime,'load',return_value={'started_at':100,'deadline':1300}),patch.object(driver.broker,'register'),patch.object(driver.dispatch,'create',return_value={'native_bootstrap':'original role bootstrap'}):
            value=driver.prepare('solo','coordinator')
        self.assertEqual(value['model_actors_allocated'],0)
        self.assertEqual(value['actor_path'],'/root/native_optional_control_v9_solo')
        self.assertEqual(value['observer_argv'][-3:],['native-optional-control-v9-solo',value['actor_path'],'coordinator'])
        self.assertFalse(value['native_qualified'])

    def test_changed_private_grader_blocks_before_closure(self):
        required={str(Path(module.__file__).resolve()):driver.entity(module.__file__) for module in (driver,driver.runtime,driver.broker,driver.dispatch,driver.observer,driver.audit,driver.closer,driver.verifier)}
        for name in driver.REVIEWS:(self.base/name).write_text(json.dumps({'verdict':'pass','issues':[],'source_entities':required}))
        driver.freeze();(self.case/'private/acceptance_test.dart').write_text('changed private fixture')
        with patch.object(driver.closer,'close') as close:
            with self.assertRaises(ValueError):driver.close_control('solo','parent','inventory')
            close.assert_not_called()

    def test_foreign_preparation_blocks_before_closure(self):
        row={'scenario':'solo','folder':'foreign','actor_path':'foreign','model':'gpt-6.1-sol','effort':'medium'}
        (self.base/'fresh-optional-native-control-preparation-v9-solo.json').write_text(json.dumps(row))
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.closer,'close') as close:
            with self.assertRaises(ValueError):driver.close_control('solo','parent','inventory')
            close.assert_not_called()

    def test_valid_closure_uses_frozen_private_fixture_and_original_clock(self):
        folder=self.root/'runtime/native-optional-control-v9-solo';folder.mkdir()
        config={'case':'O01','condition':'A'};(folder/'configuration.json').write_text(json.dumps(config))
        row={'scenario':'solo','folder':str(folder),'actor_path':'/root/native_optional_control_v9_solo','model':'gpt-6.1-sol','effort':'medium','original_started_at':100,'deadline':1300}
        (self.base/'fresh-optional-native-control-preparation-v9-solo.json').write_text(json.dumps(row))
        state={'started_at':100,'deadline':1300,'configuration_sha256':driver.hashlib.sha256(driver.runtime.encoded(config)).hexdigest()}
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'load',return_value=state),patch.object(driver.closer,'close',return_value={'native_qualified':False}) as close:
            self.assertFalse(driver.close_control('solo','parent','inventory')['native_qualified'])
            close.assert_called_once_with(folder,'parent','inventory',self.case/'private/acceptance_test.dart')

    def test_own_preparation_feeds_closure_without_version_translation(self):
        config={'case':'O01','condition':'A'}
        state={'started_at':100,'deadline':1300}
        def create(folder,*args,record_ownership=None):
            folder.mkdir();record_ownership(folder)
            (folder/'configuration.json').write_text(json.dumps(config))
            state['configuration_sha256']=driver.hashlib.sha256(driver.runtime.encoded(config)).hexdigest()
            return {'root_capability':'a'*48}
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create',side_effect=create),patch.object(driver.runtime,'load',return_value=state),patch.object(driver.broker,'register'),patch.object(driver.dispatch,'create',return_value={'native_bootstrap':'original role bootstrap'}),patch.object(driver.closer,'close',return_value={'native_qualified':False}) as close:
            prepared=driver.prepare('solo','coordinator')
            result=driver.close_control('solo','parent','inventory')
        self.assertFalse(result['native_qualified'])
        close.assert_called_once_with(Path(prepared['folder']),'parent','inventory',self.case/'private/acceptance_test.dart')
        self.assertTrue((self.base/'fresh-optional-native-control-allocation-intent-v9-solo.json').exists())
        self.assertTrue((self.base/'fresh-optional-native-control-preparation-v9-solo.json').exists())

    def test_nonboolean_prior_success_cannot_allocate_next_control(self):
        outcome=self.base/'fresh-optional-native-control-outcome-v9-solo.json'
        for flags in ({'native_control_dimension_pass':'false','owned_cleanup_verified':'false'},
                      {'native_control_dimension_pass':1,'owned_cleanup_verified':True},
                      {'native_control_dimension_pass':True,'owned_cleanup_verified':1}):
            outcome.write_text(json.dumps(flags))
            with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'create') as create:
                with self.assertRaises(ValueError):driver.prepare('one_worker','coordinator')
                create.assert_not_called()

    def test_actual_runtime_canonical_hash_contract_and_changed_configuration(self):
        # Original runtime6solo JSON is pretty serialized while its stored hash
        # is over canonical encoded JSON. Reuse that actual schema in isolation.
        original=Path(__file__).resolve().parents[1]/'runtime/native-optional-control-v6-solo'
        config=json.loads((original/'configuration.json').read_bytes())
        native_state=json.loads((original/'state.json').read_bytes())
        self.assertEqual(driver.hashlib.sha256(driver.runtime.encoded(config)).hexdigest(),native_state['configuration_sha256'])
        self.assertNotEqual(driver.entity(original/'configuration.json')['sha256'],native_state['configuration_sha256'])
        folder=self.root/'runtime/native-optional-control-v9-solo';folder.mkdir()
        (folder/'configuration.json').write_text(json.dumps(config,indent=2)+'\n')
        row={'scenario':'solo','folder':str(folder),'actor_path':'/root/native_optional_control_v9_solo','model':'gpt-6.1-sol','effort':'medium','original_started_at':native_state['started_at'],'deadline':native_state['deadline']}
        (self.base/'fresh-optional-native-control-preparation-v9-solo.json').write_text(json.dumps(row))
        with patch.object(driver,'checked_freeze',return_value={}),patch.object(driver.runtime,'load',return_value=native_state),patch.object(driver.closer,'close',return_value={'native_qualified':False}) as close:
            driver.close_control('solo','parent','inventory');close.assert_called_once()
            close.reset_mock();config['task']='changed public task';(folder/'configuration.json').write_text(json.dumps(config,indent=2))
            with self.assertRaises(ValueError):driver.close_control('solo','parent','inventory')
            close.assert_not_called()

    def test_mixed_old_and_new_review_pins_normalize_only_after_exact_validation(self):
        required={str(Path(module.__file__).resolve()):driver.entity(module.__file__) for module in (driver,driver.runtime,driver.broker,driver.dispatch,driver.observer,driver.audit,driver.closer,driver.verifier)}
        for index,name in enumerate(driver.REVIEWS):
            pins={k:dict(v) for k,v in required.items()}
            if index%2:
                for row in pins.values():row.pop('bytes')
            (self.base/name).write_text(json.dumps({'verdict':'pass','issues':[],'source_entities':pins}))
        value=driver.freeze();driver.checked_freeze()
        self.assertTrue(all(type(row['bytes']) is int for row in value['source_entities'].values()))
        entity=driver.entity(driver.__file__)
        for key,bad in [('bytes',True),('mode',False),('bytes',entity['bytes']+1)]:
            altered=dict(entity);altered[key]=bad
            with self.assertRaises(ValueError):driver.reviewed_entity(driver.__file__,altered)

    def test_all_frozen_ancillary_pins_and_case_inventory_reject_numeric_aliases(self):
        import copy
        required={str(Path(module.__file__).resolve()):driver.entity(module.__file__) for module in (driver,driver.runtime,driver.broker,driver.dispatch,driver.observer,driver.audit,driver.closer,driver.verifier)}
        for name in driver.REVIEWS:(self.base/name).write_text(json.dumps({'verdict':'pass','issues':[],'source_entities':required}))
        original=driver.freeze()
        for field in ('driver_entity','private_acceptance_entity','public_entity','metadata_entity','reviews','case_inventory'):
            changed=copy.deepcopy(original)
            if field=='reviews':row=next(iter(changed[field].values()))
            elif field=='case_inventory':row=changed[field]['all_entities']['.']
            else:row=changed[field]
            row['mode']=float(row['mode']);driver.FREEZE.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):driver.checked_freeze()
        driver.FREEZE.write_text(json.dumps(original));driver.checked_freeze()


if __name__=='__main__':unittest.main()
