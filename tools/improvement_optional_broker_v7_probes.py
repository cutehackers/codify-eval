"""Pure public transport controls. No Docker/model allocation."""
import concurrent.futures
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import improvement_optional_broker_v7 as broker


class BrokerControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name).resolve(); self.caps = {j: c * 48 for j, c in zip(sorted(broker.JOBS), 'abc')}
        self.state = {'run_id': 'run', 'configuration_sha256': 'configuration', 'phase': 'running',
                      'started_at': time.time() - 1, 'deadline': time.time() + 1200, 'editable_paths': ['lib/a.dart', 'lib/b.dart'],
                      'jobs': {j: {'status': 'running', 'capability_sha256': broker.runtime.hashed(c)}
                               for j, c in self.caps.items()}}
        broker.runtime.save(self.folder, self.state)
        for job, cap in self.caps.items():
            directory = self.folder / job / 'input'; directory.mkdir(parents=True)
            (directory / 'request.txt').write_text('Original task ' + job)
            broker.register(self.folder, job, cap)

    def call(self, op, data=None, job='root'):
        return broker.dispatch(self.folder, job, self.caps[job], op, {} if data is None else data)

    def read(self, job='root'):
        value, code = self.call('read', job=job); self.assertEqual(code, 0); return value

    def test_wrong_capability_has_no_action_or_execution(self):
        with patch.object(broker.runtime, 'command') as command:
            with self.assertRaises(ValueError): broker.dispatch(self.folder, 'root', 'f' * 48, 'exec', {'command': 'x'})
            command.assert_not_called()
        self.assertEqual(broker.ledger(self.folder, 'root'), [])

    def test_exec_before_read_is_preserved_failure_without_execution(self):
        with patch.object(broker.runtime, 'command') as command:
            value, code = self.call('exec', {'command': 'x'}); self.assertEqual(code, 1)
            command.assert_not_called()
        self.assertEqual(broker.ledger(self.folder, 'root')[0]['status'], 'failed')
        self.assertEqual(self.call('read')[1], 1)

    def test_exact_read_once_and_ledger_join(self):
        self.assertEqual(self.read()['result']['text'], 'Original task root')
        self.assertEqual(self.call('read')[1], 1)
        self.assertEqual([a['status'] for a in broker.ledger(self.folder, 'root')], ['completed', 'failed'])

    def test_original_task_drift_and_symlink_rejected(self):
        p = self.folder / 'root/input/request.txt'; p.write_text('Changed')
        self.assertEqual(self.call('read')[1], 1)
        p = self.folder / 'worker1/input/request.txt'; p.unlink(); p.symlink_to(self.folder / 'root/input/request.txt')
        self.assertEqual(self.call('read', job='worker1')[1], 1)

    def test_roles_cannot_provision_workers_or_use_unimplemented_operations(self):
        self.read('worker1')
        with patch.object(broker.runtime, 'worker') as worker:
            self.assertEqual(self.call('worker', {'goal': 'g', 'scope': ['lib/a.dart']}, 'worker1')[1], 1)
            worker.assert_not_called()
        self.read()
        for op in ('seal', 'read_reply', 'cleanup'):
            self.assertEqual(self.call(op)[1], 1)

    def test_malformed_worker_rejected_before_stop_or_reservation(self):
        self.read()
        with patch.object(broker.runtime, 'worker') as worker:
            for data in ({'goal': 'g', 'scope': ['test/x']}, {'goal': 'g', 'scope': [1]},
                         {'goal': '', 'scope': ['lib/a.dart']}, {'goal': 'g', 'scope': []},
                         {'goal': 'g', 'scope': ['lib/a.dart'], 'mode': 'review'},
                         {'goal': 'g', 'scope': ['lib/a.dart'], 'hidden': True}):
                self.assertEqual(self.call('worker', data)[1], 1)
            worker.assert_not_called()

    def test_inner_exit_is_not_rewritten_and_whole_raw_result_retained(self):
        self.read(); result = {'exit_code': 7, 'stdout': 'out', 'stderr': 'failure', 'output_complete': True}
        with patch.object(broker.runtime, 'command', return_value=result):
            value, code = self.call('exec', {'command': 'exit 7', 'seconds': 1})
        self.assertEqual(code, 0); self.assertEqual(value['result']['exit_code'], 7)
        self.assertEqual(broker.ledger(self.folder, 'root')[-1]['result'], result)

    def test_duplicate_json_keys_and_nonfinite_are_rejected(self):
        for text in ('{"command":"a","command":"b"}', '{"seconds":1e999}', '{"seconds":NaN}'):
            with self.assertRaises(ValueError): broker.strict.decoded(text)

    def test_unreceipted_intent_blocks_more_work(self):
        self.read(); path = self.folder / 'broker/root/actions/000000/receipt.json'; path.unlink()
        with patch.object(broker.runtime, 'command') as command:
            with self.assertRaises(ValueError): self.call('exec', {'command': 'x'})
            command.assert_not_called()
        self.assertEqual(broker.ledger(self.folder, 'root')[0]['status'], 'pending')

    def test_receipt_intent_hash_drift_rejected(self):
        self.read(); path = self.folder / 'broker/root/actions/000000/intent.json'
        value = json.loads(path.read_text()); value['request']['op'] = 'exec'; path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): broker.ledger(self.folder, 'root')

    def test_same_job_serializes_and_different_jobs_overlap(self):
        self.read('worker1'); self.read('worker2'); barrier = threading.Barrier(2)
        def execute(*args): barrier.wait(timeout=2); return {'exit_code': 0}
        with patch.object(broker.runtime, 'command', side_effect=execute):
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(self.call, 'exec', {'command': 'x'}, job) for job in ('worker1', 'worker2')]
                for f in futures: self.assertEqual(f.result(timeout=3)[1], 0)
        active = [0, 0]; guard = threading.Lock()
        def serialized(*args):
            with guard: active[0] += 1; active[1] = max(active)
            time.sleep(.03)
            with guard: active[0] -= 1
            return {'exit_code': 0}
        with patch.object(broker.runtime, 'command', side_effect=serialized):
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(self.call, 'exec', {'command': 'x'}, 'worker1') for _ in range(2)]
                for f in futures: self.assertEqual(f.result(timeout=3)[1], 0)
        self.assertEqual(active[1], 1)

    def test_closed_or_expired_rejected_before_action(self):
        for key, value in (('phase', 'closing'), ('deadline', time.time() - 1)):
            state = dict(self.state, **{key: value}); broker.runtime.save(self.folder, state)
            with self.assertRaises(ValueError): self.call('read')
        self.assertEqual(broker.ledger(self.folder, 'root'), [])

    def test_action_ids_are_unique_across_job_ledgers(self):
        for job in sorted(broker.JOBS): self.read(job)
        rows = [broker.ledger(self.folder, job)[0] for job in sorted(broker.JOBS)]
        self.assertEqual([r['action_id'] for r in rows], [0, 1, 2])

    def test_malformed_intent_schema_configuration_role_and_types_denied(self):
        self.read(); path = self.folder / 'broker/root/actions/000000/intent.json'
        original = json.loads(path.read_text())
        variants = [dict(original, number=False), dict(original, action_id=False), dict(original, run_id='foreign'),
                    dict(original, configuration_sha256='foreign'), dict(original, started_at=True),
                    dict(original, extra=True), dict(original, request={'job': 'worker1', 'op': 'read', 'data': {}})]
        for value in variants:
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError): broker.ledger(self.folder, 'root')
        path.write_text(json.dumps(original))

    def test_receipt_schema_pending_boolean_clock_and_extra_fields_denied(self):
        self.read(); path = self.folder / 'broker/root/actions/000000/receipt.json'
        original = json.loads(path.read_text())
        for value in (dict(original, status='pending'), dict(original, finished_at=True), dict(original, error={}),
                      dict(original, finished_at=self.state['deadline'] + 1), dict(original, result=[])):
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError): broker.ledger(self.folder, 'root')

    def test_directory_sequence_gap_denied(self):
        self.read(); directory = self.folder / 'broker/root/actions'
        (directory / '000000').rename(directory / '000001')
        with self.assertRaises(ValueError): broker.ledger(self.folder, 'root')

    def test_invalid_control_denied_before_action(self):
        path = self.folder / 'broker/root/control.json'; original = json.loads(path.read_text())
        for value in (dict(original, request_bytes=True), dict(original, native_qualified=0),
                      dict(original, request_sha256='invalid'), dict(original, extra=True)):
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError): self.call('read')
        self.assertEqual(broker.ledger(self.folder, 'root'), [])

    def test_complete_raw_limit_control_character_output_replays(self):
        self.read(); result = {'exit_code': 0, 'stdout': '\x00' * (16 * 1024 * 1024), 'stderr': '', 'output_complete': True}
        with patch.object(broker.runtime, 'command', return_value=result):
            value, code = self.call('exec', {'command': 'bounded control-byte output'})
        self.assertEqual(code, 0)
        replay = broker.ledger(self.folder, 'root')[-1]
        self.assertEqual(replay['result'], result)
        path = self.folder / 'broker/root/actions/000001/receipt.json'
        self.assertGreater(path.stat().st_size, 40 * 1024 * 1024)
        self.assertLess(path.stat().st_size, broker.LIMIT)

    def test_successful_lazy_worker_registration_and_failed_registration(self):
        self.read(); directory = self.folder / 'broker/worker1'
        import shutil
        shutil.rmtree(directory)
        result = {'job': 'worker1', 'capability': self.caps['worker1'], 'snapshot_sha256': 'snapshot'}
        with patch.object(broker.runtime, 'worker', return_value=result), patch.object(broker.native_dispatch,'prepare',return_value={'native_bootstrap':'original prepared bootstrap'}):
            value, code = self.call('worker', {'goal': 'task', 'scope': ['lib/a.dart']})
        self.assertEqual(code, 0)
        self.assertEqual(value['result']['job'], 'worker1')
        self.assertEqual(self.read('worker1')['result']['text'], 'Original task worker1')
        with patch.object(broker.runtime, 'worker', return_value=result), patch.object(broker.runtime, 'failure') as fail:
            value, code = self.call('worker', {'goal': 'task', 'scope': ['lib/a.dart']})
            self.assertEqual(code, 1); fail.assert_called_once()

    def test_prepared_worker_intent_failure_preserves_runtime_failure_and_failed_receipt(self):
        self.read()
        import shutil
        shutil.rmtree(self.folder/'broker/worker1')
        result={'job':'worker1','capability':self.caps['worker1'],'snapshot_sha256':'snapshot'}
        error=ValueError('original native intent failure')
        with patch.object(broker.runtime,'worker',return_value=result), patch.object(broker.native_dispatch,'prepare',side_effect=error), patch.object(broker.runtime,'failure') as fail:
            value,code=self.call('worker',{'goal':'task','scope':['lib/a.dart']})
            self.assertEqual(code,1);fail.assert_called_once_with(self.folder,error)
        self.assertEqual(broker.ledger(self.folder,'root')[-1]['error']['message'],str(error))

    def test_root_contribution_operations_have_exact_runtime_calls_and_ledger_results(self):
        self.read(); view = {'path': '/owned/view', 'sha256': 'digest'}
        cases = [('view', {'slot': 'worker1'}, 'view', (self.folder, self.caps['root'], 'worker1')),
                 ('decide', {'slot': 'worker1', 'view': view, 'decision': 'reject', 'reason': 'original'},
                  'decide', (self.folder, self.caps['root'], 'worker1', view, 'reject', 'original')),
                 ('integrate', {}, 'integrate', (self.folder, self.caps['root'])),
                 ('verify', {}, 'verify', (self.folder, self.caps['root']))]
        for op, data, method, args in cases:
            result = {'evidence': op, 'native_qualified': False}
            with patch.object(broker.runtime, method, return_value=result) as call:
                body, code = self.call(op, data); self.assertEqual(code, 0); self.assertEqual(body['result'], result)
                call.assert_called_once_with(*args)
            self.assertEqual(broker.ledger(self.folder, 'root')[-1]['result'], result)

    def test_worker_seal_and_forbidden_root_operations(self):
        self.read('worker1')
        with patch.object(broker.runtime, 'seal', return_value={'artifact': 'original'}) as seal:
            body, code = self.call('seal', {'findings': 'bounded'}, 'worker1')
            self.assertEqual(code, 0); seal.assert_called_once_with(self.folder, 'worker1', self.caps['worker1'], 'bounded')
        for op in ('view', 'decide', 'integrate', 'verify'):
            with patch.object(broker.runtime, op) as method:
                self.assertEqual(self.call(op, {}, 'worker1')[1], 1); method.assert_not_called()

    def test_extra_artifact_operation_fields_rejected_before_runtime_effect(self):
        self.read()
        for op, data in [('view', {'slot': 'worker1', 'path': '/foreign'}), ('integrate', {'anything': True}),
                         ('verify', {'command': 'custom'}), ('decide', {'slot': 'worker1'})]:
            with patch.object(broker.runtime, op) as method:
                self.assertEqual(self.call(op, data)[1], 1); method.assert_not_called()

    def test_two_full_raw_limit_verify_results_replay_after_json_expansion(self):
        self.read(); raw = '\x00' * (16 * 1024 * 1024)
        result = {'public': {'exit_code': 1, 'stdout': raw, 'stderr': '', 'output_complete': True},
                  'analyze': {'exit_code': 0, 'stdout': raw, 'stderr': '', 'output_complete': True}}
        with patch.object(broker.runtime, 'verify', return_value=result):
            body, code = self.call('verify'); self.assertEqual(code, 0)
        self.assertEqual(broker.ledger(self.folder, 'root')[-1]['result'], result)
        path = self.folder / 'broker/root/actions/000001/receipt.json'
        self.assertGreater(path.stat().st_size, 128 * 1024 * 1024); self.assertLess(path.stat().st_size, broker.LIMIT)

    def test_unserializable_or_overflow_callback_is_failed_receipt_not_success(self):
        self.read()
        for result in ({'number': float('nan')}, ['not an object']):
            with patch.object(broker.runtime, 'verify', return_value=result), patch.object(broker.runtime, 'failure') as failure:
                body, code = self.call('verify'); self.assertEqual(code, 1); failure.assert_called_once()
            self.assertEqual(broker.ledger(self.folder, 'root')[-1]['status'], 'failed')
        with patch.object(broker, 'LIMIT', 2048), patch.object(broker.runtime, 'verify', return_value={'large': 'x' * 2048}), patch.object(broker.runtime, 'failure') as failure:
            body, code = self.call('verify'); self.assertEqual(code, 1); failure.assert_called_once()
        self.assertEqual(broker.ledger(self.folder, 'root')[-1]['status'], 'failed')

    def test_final_callback_timestamp_cannot_emit_late_completed_success(self):
        self.read(); deadline = self.state['deadline']
        with patch.object(broker.runtime, 'verify', return_value={'evidence': 'done'}), patch.object(broker.runtime, 'failure') as failure:
            with patch.object(broker.time, 'time', side_effect=[deadline-10, deadline-9, deadline-2, deadline+1, deadline+2]):
                body, code = self.call('verify')
            self.assertEqual(code, 1); self.assertEqual(body['status'], 'error'); failure.assert_called_once()
        row = broker.ledger(self.folder, 'root')[-1]
        self.assertEqual(row['status'], 'failed'); self.assertIn('Final callback receipt', row['error']['message'])


if __name__ == '__main__': unittest.main()
