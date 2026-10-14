import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import improvement_optional_normal_close_v1 as subject


class NormalClose(unittest.TestCase):
    def invoke(self, row, config=None, failure=None, classification=None):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / 'runtime' / row['run_id']
            (folder / 'native-close/combined-verifier').mkdir(parents=True)
            # Actual verifier returns numeric IDs, persisted JSON string keys.
            receipt = {'fixture_receipt': True, 'machine': {'tests': {2: 'first', 10: 'second'}}}
            (folder / 'native-close/combined-verifier/receipt.json').write_text(json.dumps(receipt))
            state = {'run_id': '0123456789abcdef0123456789abcdef', 'started_at': 1000, 'deadline': 2200}
            config = config or {**state, **{key: row[key] for key in ('case_id', 'condition')}}
            dispatch = {'root_path': row['actor_path'], 'coordinator_id': 'coordinator',
                        'run_id': state['run_id'], 'configuration_sha256': subject.original.runtime.registry.sha(config),
                        'runtime_configuration_sha256': 'runtime_hash'}
            (folder / 'native-dispatch').mkdir()
            (folder / 'native-dispatch/configuration.json').write_text(json.dumps(dispatch))
            (root / 'parent.jsonl').write_text(json.dumps({'type': 'session_meta', 'payload': {'id': 'coordinator'},
                                                         'timestamp': '2026-10-13T00:00:00Z'}) + '\n')
            outcome = {'first_error': failure, 'owned_cleanup_verified': True,
                       'source_fences_unchanged': True, 'verification': receipt,
                       'whole_observed_seconds': 37, 'usage': {'total_tokens': 42}}
            with patch.object(subject.inputs, 'ROOT', root), \
                    patch.object(subject.inputs, 'case_directory', return_value=root / row['case_id']), \
                    patch.object(subject.original.runtime.registry, 'read', return_value={'configuration': config}), \
                    patch.object(subject.original.runtime, 'load', return_value=state), \
                    patch.object(subject.native_dispatch, 'runtime_identity', return_value='runtime_hash'), \
                    patch.object(subject.original, 'close', return_value=outcome) as close, \
                    patch.object(subject.classifier, 'classify', return_value=classification) as classify:
                value = subject.close(row, root / 'parent.jsonl', 'original-inventory-call')
                self.assertEqual(json.loads((folder / 'native-close/classified-outcome-v1.json').read_bytes()), value)
                return value, close.call_args, classify.call_count

    def test_exact_conditions_and_original_closer_routing(self):
        for row in subject.inputs.sequence():
            value, call, count = self.invoke(row, classification={'software_pass': True, 'classification': 'software_pass'})
            self.assertEqual(value['row'], row)
            self.assertEqual(call.args[-1].name, 'acceptance_test.dart')
            self.assertEqual(count, 1)
            self.assertFalse(value['comparison_admitted'])

    def test_original_error_never_inherits_false_default(self):
        value, _, count = self.invoke(subject.inputs.sequence()[0], failure={'message': 'audit failed'})
        self.assertIsNone(value['classification']['software_pass'])
        self.assertEqual(count, 0)

    def test_configuration_drift_denied_before_closer(self):
        row = subject.inputs.sequence()[0]
        with self.assertRaises(ValueError):
            self.invoke(row, config={'run_id': 'wrong', 'case_id': row['case_id'], 'condition': row['condition']})


if __name__ == '__main__':
    unittest.main()
