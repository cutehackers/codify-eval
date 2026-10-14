"""Actual owned containers, plus explicit injected failure/deadline probes."""
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

import improvement_software_runtime_v2 as runtime
from improvement_software_artifacts_v3 import atomic_json

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'runtime/protocol-probes/software-runtime-v2-actual'
OUT = ROOT / 'results/improvement-v1/software-runtime-v2-actual-probe.json'

def main():
    if WORK.exists() or OUT.exists():
        raise ValueError('Fresh probe namespace required')
    review = ROOT / 'results/improvement-v1/software-runtime-v2-review.json'
    data = json.loads(review.read_text())
    assert data['verdict'] == 'pass'
    for relative, expected in data['source_hashes'].items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    WORK.mkdir()
    source = WORK / 'starting'
    (source / 'pkg').mkdir(parents=True)
    (source / 'pkg/label.py').write_text('VALUE = "starting label"\n')
    (source / 'pkg/quantity.py').write_text('VALUE = "starting quantity"\n')
    (source / 'protected.txt').write_text('immutable\n')
    folder = WORK / 'jobs'
    receipt = {'status': 'frozen_not_run', 'rows': [],
        'sources': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [Path(__file__), ROOT / 'tools/improvement_software_runtime_v2.py',
                      ROOT / 'tools/improvement_software_artifacts_v3.py', review]},
        'native_binding_qualified': False, 'broker_qualified': False,
        'complete_final_cost': False, 'superiority_proven': False}
    atomic_json(OUT, receipt, exclusive=True)
    def record(name, passed, **evidence):
        receipt['rows'].append(dict(id=name, passed=bool(passed), **evidence))
        atomic_json(OUT, receipt)
        assert passed, name
    try:
        caps = runtime.create(folder, source, {j: 'Mechanical lifecycle test only.'
                                              for j in runtime.JOBS}, seconds=180)
        state = runtime.load(folder)
        identities = {j: runtime.inspect(folder, state, j) for j in runtime.JOBS}
        record('three_isolated_owned_containers',
            len({i['Id'] for i in identities.values()}) == 3
            and all(i['State']['Running'] for i in identities.values()),
            container_ids={j: i['Id'] for j, i in identities.items()})
        result = runtime.command(folder, 'root', caps['root'], 'echo forbidden > protected.txt')
        record('actual_root_readonly', result['exit_code'] != 0
            and (folder / 'root/repo/protected.txt').read_text() == 'immutable\n', result=result)
        result = runtime.command(folder, 'label', caps['label'], 'echo changed > pkg/label.py')
        record('worker_write_isolated', result['exit_code'] == 0
            and (folder / 'label/repo/pkg/label.py').read_text() == 'changed\n'
            and (folder / 'root/repo/pkg/label.py').read_bytes() == (source / 'pkg/label.py').read_bytes()
            and (folder / 'quantity/repo/pkg/label.py').read_bytes() == (source / 'pkg/label.py').read_bytes())
        count = runtime.load(folder)['jobs']['quantity']['commands']
        denied = False
        try:
            runtime.command(folder, 'quantity', caps['label'], 'touch forbidden')
        except ValueError:
            denied = True
        record('cross_job_capability_denied_before_exec', denied
            and runtime.load(folder)['jobs']['quantity']['commands'] == count
            and not (folder / 'quantity/repo/forbidden').exists())
        real_inspect = runtime.inspect
        def expire_after_inspect(f, s, j):
            info = real_inspect(f, s, j)
            s['deadline'] = time.time() - 1  # Deliberate deterministic expiry injection.
            return info
        denied = False
        with patch.object(runtime, 'inspect', expire_after_inspect):
            try:
                runtime.command(folder, 'quantity', caps['quantity'], 'touch late')
            except ValueError:
                denied = True
        record('expiry_after_inspection_denies_exec', denied
            and runtime.load(folder)['jobs']['quantity']['commands'] == count
            and not (folder / 'quantity/repo/late').exists(), injected=True)
        runtime.stop(folder, 'label')
        denied = False
        try:
            runtime.command(folder, 'label', caps['label'], 'touch after_stop')
        except ValueError:
            denied = True
        record('stopped_worker_denies_exec', denied
            and not real_inspect(folder, runtime.load(folder), 'label')['State']['Running'])
        real_docker = runtime.docker
        def fail_stop(args, **kwargs):
            if args[0] == 'stop':
                raise runtime.subprocess.TimeoutExpired(['docker'] + args, timeout=30)
            return real_docker(args, **kwargs)
        with patch.object(runtime, 'docker', fail_stop):
            runtime.cleanup(folder)
        final = runtime.load(folder)
        events = [json.loads(line) for line in (folder / 'events.jsonl').read_text().splitlines()]
        record('failed_stop_actual_kill_cleanup', final['phase'] == 'closed_runtime_only'
            and all(row['status'] == 'removed' for row in final['jobs'].values())
            and len([e for e in events if e['op'] == 'stop_error']) == 2,
            injected=True, cleanup_state=final['phase'])
        receipt['status'] = 'runtime_lifecycle_probe_pass'
    except BaseException as error:
        receipt['status'] = 'fail'
        receipt['first_error'] = {'type': type(error).__name__, 'message': str(error)}
        raise
    finally:
        if (folder / 'state.json').exists():
            try:
                if runtime.load(folder)['phase'] != 'closed_runtime_only':
                    runtime.cleanup(folder)
            except BaseException as error:
                receipt['status'] = 'cleanup_failed'
                receipt['cleanup_error'] = str(error)
        atomic_json(OUT, receipt)
    print(json.dumps({'status': receipt['status'], 'passed': len(receipt['rows'])}))

if __name__ == '__main__':
    main()
