"""Replay retained genuine controls, never allocate or rewrite original evidence."""
import json
import unittest
from pathlib import Path

import improvement_optional_completed_failure_gate_v1 as subject


def arguments(scenario):
    folder = Path(__file__).resolve().parents[1] / 'runtime' / ('native-optional-control-v9-' + scenario)
    output = folder / 'native-close'
    inputs = json.loads((output / 'dispatch-inputs.json').read_bytes())
    audit = json.loads((output / 'audit.json').read_bytes())
    state, rows = inputs['state'], inputs['rows']
    config = state['configuration']
    workers = {row['intent']['agent_path']: (output / (job + '.jsonl')).read_bytes()
               for job, row in rows.items() if job != 'root'}
    locators = {row['intent']['agent_path']: json.loads((output / (job + '-locator.json')).read_bytes())['path']
                for job, row in rows.items()}
    provision = {'run_id': config['run_id'], 'configuration_sha256': subject.original.membership.registry.sha(config),
                 'jobs': {job: row['provision'] for job, row in rows.items()}}
    return {'config': config, 'state': state, 'root_intent': rows['root']['intent'],
            'worker_intents': {job: row['intent'] for job, row in rows.items() if job != 'root'},
            'coordinator_raw': (output / 'coordinator.jsonl').read_bytes(),
            'root_raw': (output / 'root.jsonl').read_bytes(), 'worker_raw_by_path': workers,
            'provision': provision, 'registry_folder': folder / 'registry', 'locators': locators,
            'inventory_call_id': audit['original_no_more_delivery_commitment']['inventory_call_id'],
            'commitment': audit['original_no_more_delivery_commitment']}


class CompletedFailureGate(unittest.TestCase):
    def test_genuine_zero_one_two_member_native_replays(self):
        for count, scenario in enumerate(('solo', 'one_worker', 'two_workers'), 1):
            with self.subTest(scenario=scenario):
                value = subject.verify(**arguments(scenario))
                self.assertEqual(len(value['membership']['members']), count)
                self.assertTrue(value['normal_terminal_failure_gate_pass'])
                self.assertIsNone(value['software_pass'])
                self.assertFalse(value['cleanup_authorized'])

    def test_missing_worker_source_and_locator_deny(self):
        for key in ('worker_raw_by_path', 'locators'):
            args = arguments('one_worker'); args[key] = {}
            with self.subTest(key=key), self.assertRaises(ValueError):
                subject.verify(**args)

    def test_wrong_inventory_or_commitment_deny(self):
        for mutation in ('call', 'delivery', 'members'):
            args = arguments('solo')
            if mutation == 'call': args['inventory_call_id'] = 'unknown'
            if mutation == 'delivery': args['commitment']['no_more_delivery'] = False
            if mutation == 'members': args['commitment']['member_paths'] = []
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                subject.verify(**args)


if __name__ == '__main__':
    unittest.main()
