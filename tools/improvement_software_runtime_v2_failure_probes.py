"""Injected boundary probes, distinct from actual Docker observations."""
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import improvement_software_runtime_v2 as runtime

class Failures(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'runtime'
        self.folder.mkdir()
        self.cap = 'known-role-capability'
        self.first = {'type': 'OSError', 'message': 'original operation failed'}
        self.state = {'phase': 'running', 'deadline': time.time() + 100,
            'first_error': self.first, 'jobs': {'root': {
                'container': 'owned-test-only', 'container_id': 'known-id',
                'capability_sha256': runtime.hashed(self.cap),
                'status': 'running', 'commands': 0}}}
        runtime.persist(self.folder, self.state)

    def test_provisioning_expiry_denies_first_allocation(self):
        source = Path(self.temp.name) / 'starting'
        (source / 'pkg').mkdir(parents=True)
        for name in ('label', 'quantity'):
            (source / 'pkg' / (name + '.py')).write_text('pass\n')
        calls = [0]
        def clock():
            calls[0] += 1
            return 0 if calls[0] == 1 else 3
        folder = Path(self.temp.name) / 'expired-provision'
        with patch.object(runtime.time, 'time', clock), patch.object(runtime, 'docker') as docker:
            with self.assertRaisesRegex(ValueError, 'deadline'):
                runtime.create(folder, source, {j: 'test' for j in runtime.JOBS}, seconds=1)
            docker.assert_not_called()
        state = runtime.load(folder)
        self.assertEqual(state['jobs'], {})
        self.assertEqual(state['first_error']['type'], 'ValueError')
        self.assertEqual(state['phase'], 'closed_runtime_only')

    def test_start_receipt_budget_expiry_denies_exec(self):
        now = [time.time()]
        real_event = runtime.event
        def event(folder, value):
            real_event(folder, value)
            if value['op'] == 'command_start':
                now[0] += 200
        with patch.object(runtime.time, 'time', lambda: now[0]), \
                patch.object(runtime, 'inspect', return_value={'State': {'Running': True}}), \
                patch.object(runtime, 'event', event), patch.object(runtime, 'docker') as docker:
            with self.assertRaisesRegex(ValueError, 'deadline'):
                runtime.command(self.folder, 'root', self.cap, 'touch late')
            docker.assert_not_called()
        events = [json.loads(x) for x in (self.folder / 'events.jsonl').read_text().splitlines()]
        self.assertEqual([e['op'] for e in events], ['command_start'])
        self.assertEqual(runtime.load(self.folder)['jobs']['root']['commands'], 1)

    def test_stop_and_kill_failure_retains_owned_job_and_first_error(self):
        def docker(args, **kwargs):
            if args[0] == 'stop':
                raise runtime.subprocess.TimeoutExpired('docker stop', 30)
            if args[0] == 'kill':
                raise OSError('kill unavailable')
            self.fail('Unexpected remove/other Docker command')
        with patch.object(runtime, 'inspect', return_value={'State': {'Running': True}}), \
                patch.object(runtime, 'docker', docker):
            with self.assertRaisesRegex(ValueError, 'cleanup unverified'):
                runtime.cleanup(self.folder)
        state = runtime.load(self.folder)
        self.assertEqual(state['phase'], 'cleanup_failed')
        self.assertEqual(state['jobs']['root']['status'], 'running')
        self.assertEqual(state['first_error'], self.first)
        self.assertEqual(state['cleanup_errors'][0]['message'], 'kill unavailable')

    def test_unobservable_owned_job_is_retained(self):
        with patch.object(runtime, 'inspect', side_effect=ValueError('identity unavailable')), \
                patch.object(runtime, 'docker') as docker:
            with self.assertRaisesRegex(ValueError, 'cleanup unverified'):
                runtime.cleanup(self.folder)
            docker.assert_not_called()
        state = runtime.load(self.folder)
        self.assertEqual(state['jobs']['root']['status'], 'running')
        self.assertEqual(state['first_error'], self.first)
        self.assertEqual(state['cleanup_errors'][0]['message'], 'identity unavailable')

    def test_original_creation_error_survives_cleanup_error(self):
        source = Path(self.temp.name) / 'starting'
        (source / 'pkg').mkdir(parents=True)
        for name in ('label', 'quantity'):
            (source / 'pkg' / (name + '.py')).write_text('pass\n')
        def docker(args, **kwargs):
            if args[0] == 'inspect':
                return runtime.subprocess.CompletedProcess(args, 1, '', 'No such object: owned')
            if args[0] == 'create':
                raise OSError('original create error')
            self.fail('Unexpected Docker command')
        folder = Path(self.temp.name) / 'creation-failure'
        with patch.object(runtime, 'docker', docker), \
                patch.object(runtime, 'cleanup', side_effect=PermissionError('cleanup error')):
            with self.assertRaisesRegex(OSError, 'original create error') as raised:
                runtime.create(folder, source, {j: 'test' for j in runtime.JOBS})
        self.assertEqual(raised.exception.cleanup_error, 'cleanup error')
        self.assertEqual(runtime.load(folder)['first_error'],
                         {'type': 'OSError', 'message': 'original create error'})

if __name__ == '__main__':
    out = Path(__file__).resolve().parents[1] / 'results/improvement-v1/software-runtime-v2-failure-probes.json'
    if out.exists():
        raise ValueError('Probe evidence already exists')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Failures)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'status': 'injected_failure_probes_pass' if result.wasSuccessful() else 'fail',
              'tests_run': result.testsRun, 'failures': [str(t) for t, _ in result.failures],
              'errors': [str(t) for t, _ in result.errors], 'injected_only': True,
              'actual_docker_calls': 0, 'native_binding_qualified': False,
              'broker_qualified': False, 'superiority_proven': False,
              'source_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in [Path(__file__).resolve(), Path(runtime.__file__).resolve()]}}
    with out.open('x') as f:
        json.dump(report, f, indent=2); f.write('\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
