"""Actor-free J01 prepare/public/remove/private lifecycle, not model evidence."""
import json
from pathlib import Path
import shutil
import subprocess
import time

import improvement_J01_solo_pilot_v1 as pilot
from improvement_software_artifacts_v3 import atomic_json

ROOT = pilot.ROOT
RUN = 'control-probe-fresh-J01-solo-runtime-v2-J01-C0-1'
OUT = ROOT / 'results/improvement-v1/fresh-J01-solo-runtime-control-v2'
WORK = ROOT / 'runtime/protocol-probes/fresh-J01-solo-runtime-control-v2'


def run():
    assert not OUT.exists() and not WORK.exists() and not (ROOT / 'runtime' / RUN).exists()
    assert not subprocess.check_output(['docker', 'ps', '-a', '-q', '--filter', 'name=codify-'], text=True, timeout=30).strip()
    OUT.mkdir(); WORK.mkdir()
    case = pilot.case_directory('J01')
    meta = pilot.legacy.read(case / 'metadata.json')
    files = pilot.closure() | {Path(__file__).resolve(), ROOT / 'tools/improvement_J01_native_watch_v1.py',
        ROOT / 'tools/improvement_J01_watch_supervisor_v1.py', ROOT / 'runtime/image.json', ROOT / 'AGENTS.md'}
    files.update(p for p in case.rglob('*') if p.is_file())
    files.update(p for p in (ROOT / 'snapshots/C0').rglob('*') if p.is_file())
    pins = {str(p.relative_to(ROOT)): pilot.legacy.sha(p) for p in files}
    started = time.time()
    summary = {'status': 'RUNNING', 'model_actors_allocated': 0, 'source_hashes': pins,
        'image_id': pilot.IMAGE, 'original_started_at': started, 'superiority_proven': False,
        'native_actor_route_qualified': False, 'new_case_lifecycle_control_only': True}
    atomic_json(OUT / 'summary.json', summary, exclusive=True)
    metadata = None
    try:
        pilot.legacy.prepare.case_directory = pilot.case_directory
        pilot.legacy.prepare.prepare('J01', 'C0', 1, 'control-probe-fresh-J01-solo-runtime-v2')
        folder = ROOT / 'runtime' / RUN
        metadata = pilot.legacy.read(folder / 'run.json')
        identity = json.loads(subprocess.check_output(['docker', 'inspect', metadata['container']], text=True, timeout=30))[0]
        assert identity['Image'] == pilot.IMAGE
        metadata.update(container_id=identity['Id'], started_at=started, agent_started_at=started,
            time_limit_seconds=1200, user_turn_limit=1, actor_allocated=False)
        atomic_json(folder / 'run.json', metadata)
        pilot.legacy.owned_identity(metadata)
        cmd = f'python3 {ROOT}/tools/agent_io.py --run {RUN} --cmd "flutter pub get --offline"'
        dep = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=150)
        record = json.loads(dep.stdout)
        assert dep.returncode == record['exit_code'] == 0
        atomic_json(OUT / 'dependency-command.json', {'outer_exit': dep.returncode, 'record': record}, exclusive=True)
        prepared = pilot.protected_tree(folder / 'repo')
        atomic_json(OUT / 'prepared-entities.json', prepared, exclusive=True)
        reference = case / meta['private_reference']
        assert reference.is_file() and not reference.is_symlink() and reference.resolve().is_relative_to(case.resolve())
        shutil.copyfile(reference, folder / 'repo/lib/implementation.dart')
        changes, scope = pilot.scope_changes(prepared, pilot.protected_tree(folder / 'repo'), ['lib/implementation.dart'])
        assert scope and changes == ['lib/implementation.dart']
        subprocess.run(['docker', 'stop', '-t', '2', metadata['container']], capture_output=True, check=True, timeout=10)
        assert not pilot.legacy.owned_identity(metadata)['State']['Running']
        public_source = WORK / 'public-source'
        shutil.copytree(folder / 'repo', public_source, ignore=shutil.ignore_patterns('.git', '.dart_tool', 'build', '__pycache__'))
        assert not (public_source / 'test/acceptance_test.dart').exists()
        public = pilot.verify(public_source, WORK / 'public-verification', started + 1200, expected_tests=2)
        atomic_json(OUT / 'public-receipt.json', public, exclusive=True)
        assert pilot.complete_observation(public, 2) and public['pass']
        pilot.legacy.diagnostics.preserve_tmp(OUT, metadata['container'], 'product')
        cleanup = pilot.legacy.remove_owned(metadata)
        summary['product_cleanup'] = cleanup
        summary['allocation_through_product_cleanup_seconds'] = cleanup['finished_at'] - started
        assert summary['allocation_through_product_cleanup_seconds'] <= 1200
        private_source = WORK / 'private-source'
        shutil.copytree(public_source, private_source)
        shutil.copyfile(pilot.acceptance_path(case, meta), private_source / 'test/acceptance_test.dart')
        private_started = time.time()
        private = pilot.verify(private_source, WORK / 'private-verification', private_started + 600, expected_tests=33)
        atomic_json(OUT / 'private-receipt.json', private, exclusive=True)
        assert pilot.complete_observation(private, 33) and private['pass']
        assert private_started > cleanup['finished_at']
        summary.update(status='pass', public_tests=2, full_tests=33,
            private_started_after_product_removed=True, private_started_at=private_started,
            all_owned_resources_removed=True)
    except Exception as error:
        summary.update(status='fail', error={'type': type(error).__name__, 'message': str(error)})
        if metadata is not None:
            try:
                found = subprocess.run(['docker', 'inspect', metadata['container']], capture_output=True, text=True, timeout=30)
                if found.returncode == 0:
                    if json.loads(found.stdout)[0]['State']['Running']:
                        subprocess.run(['docker', 'stop', '-t', '2', metadata['container']], capture_output=True, check=True, timeout=10)
                    summary['failure_product_cleanup'] = pilot.legacy.remove_owned(metadata)
            except Exception as cleanup_error:
                summary['cleanup_error'] = str(cleanup_error)
    for name, digest in pins.items():
        if pilot.legacy.sha(ROOT / name) != digest:
            summary.update(status='fail', source_drift=name)
    summary['finished_at'] = time.time()
    atomic_json(OUT / 'summary.json', summary)
    return summary


if __name__ == '__main__':
    result = run()
    print(json.dumps({k: v for k, v in result.items() if k != 'source_hashes'}))
    raise SystemExit(0 if result['status'] == 'pass' else 1)
