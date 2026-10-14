"""Actual owned Docker abort/deadline probes; not model/case qualification."""
import hashlib
import json
import time
from pathlib import Path

from prepare import ROOT, tree_hash
import improvement_dialogue_phase_v2 as phase
from improvement_dialogue_io_v2 import run_command


def main():
    fixture = ROOT / 'runtime/protocol-probes/dialogue-v2-fixture'
    fixture.mkdir(parents=True)
    repo = fixture / 'repo'
    repo.mkdir()
    (repo / 'README.md').write_text('Controlled protocol probe repository.\n')
    task = fixture / 'task.md'; task.write_text('Create policy.json for retention. The retention duration and cutoff inclusion have not been decided. Ask the user for those decisions before implementing. Preserve README.md.\n')
    reply = fixture / 'reply.txt'; reply.write_text('Use 30 days. Keep a record exactly 30 days old.\n')
    baseline_name = 'results/improvement-v1/C4-development-freeze-v1.json'
    baseline = json.loads((ROOT / baseline_name).read_text())
    pins = dict(baseline['source_hashes'])
    for name in [baseline_name, *phase.HELPERS, 'tools/improvement_dialogue_lifecycle_v2_probes.py',
                 'tools/improvement_dialogue_native_v2_probes.py', 'results/improvement-v1/dialogue-native-v2-probes.json']:
        pins[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    results = []
    for mode in ('abort', 'deadline'):
        run_id = 'control-probe-dialogue-lifecycle-v2-' + mode
        config = {'run_id': run_id, 'model': 'gpt-6.1-sol', 'effort': 'medium', 'time_limit_seconds': 1200,
                  'image_id': json.loads((ROOT / 'runtime/image.json').read_text())['image_id'],
                  'source_repo': str(repo.relative_to(ROOT)), 'source_repo_sha256': tree_hash(repo),
                  'task_path': str(task.relative_to(ROOT)), 'task_sha256': hashlib.sha256(task.read_bytes()).hexdigest(),
                  'reply_path': str(reply.relative_to(ROOT)), 'reply_sha256': hashlib.sha256(reply.read_bytes()).hexdigest(),
                  'slots': ['retention_days', 'cutoff_boundary'], 'source_hashes': pins}
        path = fixture / (mode + '-configuration.json')
        with path.open('x') as stream:
            json.dump(config, stream, indent=2)
        created = phase.create(path)
        folder = phase.directory(run_id)
        try:
            assert not any((folder / 'control-inputs').iterdir())
            denied = run_command(run_id, "printf 'changed' > README.md")
            assert denied['exit_code'] != 0 and denied['repository_writable'] is False
            assert (folder / 'repo/README.md').read_bytes() == (repo / 'README.md').read_bytes()
            if mode == 'abort':
                final = phase.abort(run_id, 'Controlled interruption-before-actor allocation probe')
            else:
                with phase.locked(folder):
                    state = phase.read(folder / 'state.json')
                    state['started_at'] = time.time() - 3600
                    phase.persist(folder, state)
                expired = run_command(run_id, "printf 'late write' > README.md")
                assert expired['exit_code'] == 124
                final = expired['failure_proof']
            assert final['cleanup_verified']
            assert final['usage'] is None and final['usage_unavailable'] is not None
            assert final['complete_final_cost'] is False
            assert all(row.get('removed') or row.get('absence_verified_by_healthy_inventory') for row in final['containers'])
            assert (folder / 'first-failure.json').exists()
            assert (folder / 'repo/README.md').read_bytes() == (repo / 'README.md').read_bytes()
            results.append({'run_id': run_id, 'mode': mode, 'status': 'pass', 'configuration_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'denied_write_sha256': hashlib.sha256(json.dumps(denied, sort_keys=True).encode()).hexdigest(),
                            'first_failure_sha256': hashlib.sha256((folder / 'first-failure.json').read_bytes()).hexdigest(),
                            'abort_sample_sha256': hashlib.sha256((folder / 'abort-sample-1.json').read_bytes()).hexdigest(),
                            'no_native_actor_allocated': True, 'complete_cost_not_claimed': True})
        except Exception as error:
            phase.abort(run_id, error)
            raise
    output = {'status': 'pass', 'scope': 'Actual Docker RO denial and owned-resource abort/deadline lifecycle before any actor allocation. No semantic, native two-turn or final-cost qualification.',
              'source_hashes': pins, 'probes': results}
    target = ROOT / 'results/improvement-v1/dialogue-lifecycle-v2-probes.json'
    with target.open('x') as stream:
        json.dump(output, stream, indent=2)
    print(json.dumps({'status': output['status'], 'probes': results}))


if __name__ == '__main__':
    main()
