"""Versioned supplemental H01 GUI evidence; never alters grading or source artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
FREE_FLOOR = 3 * 1024**3
FREEZE = ROOT/'results/heldout-runtime-probe-v1/freeze.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_hashes(source):
    return {p.relative_to(source).as_posix(): sha(p) for p in sorted(source.rglob('*'))
            if p.is_file() and not any(x in {'.git', '.dart_tool', 'build'} for x in p.relative_to(source).parts)}


def pins():
    paths = ['tools/heldout_gui.py', 'tools/heldout_runtime.py', 'scripts/software_runtime.py',
             'runtime/image.json', 'fixtures/H01/task.md', 'fixtures/H01/repo/pubspec.yaml']
    paths += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'software_cases/W01/repo/linux').rglob('*')) if p.is_file()]
    return {p: sha(ROOT/p) for p in paths}


def execute(source, path, image_id, identity):
    if path.exists():
        raise ValueError('Evidence exists; choose a new explicit version')
    if shutil.disk_usage(ROOT).free < FREE_FLOOR:
        raise RuntimeError('Less than 3 GiB free before build')
    before = artifact_hashes(source)
    path.mkdir(parents=True)
    repo = path/'repo'
    shutil.copytree(source, repo, ignore=shutil.ignore_patterns('.git', '.dart_tool', 'build', '.agents'))
    scaffolding = 'existing_actor_linux'
    if not (repo/'linux').exists():
        shutil.copytree(ROOT/'software_cases/W01/repo/linux', repo/'linux')
        scaffolding = 'external_W01_linux_scaffolding'
    wrapper = repo/'heldout_maximum_zero_host.dart'
    if wrapper.exists():
        raise ValueError('External host path collides with artifact')
    wrapper.write_text("import 'package:flutter/material.dart';\nimport 'lib/main.dart' as app;\nvoid main() => runApp(const MaterialApp(home: app.QuantityPage(maximum: 0)));\n")
    checks = []
    container = 'heldout-probe-' + hashlib.sha256(str(path).encode()).hexdigest()[:16]
    result = {'identity': identity, 'image_id': image_id, 'scaffolding': scaffolding,
              'source': str(source), 'artifact_before': before, 'checks': checks,
              'evidence_tier': 'external_linux_release_executable', 'supplemental_only': True,
              'host_variants': {'maximum5': 'unaltered artifact main.dart',
                                'maximum0': 'external host imports public QuantityPage(maximum:0)'},
              'limitation': 'Linux scaffolding and maximum0 host exist only in the external copy. No grading criteria are changed.'}
    def command(cmd, timeout):
        started = time.monotonic()
        process = subprocess.run(['docker', 'exec', container, 'timeout', f'{timeout}s', 'bash', '-lc', cmd],
                                 capture_output=True, text=True, timeout=timeout + 15)
        checks.append({'command': cmd, 'exit_code': process.returncode,
                       'output': process.stdout + process.stderr,
                       'elapsed_seconds': time.monotonic() - started})
        return process.returncode == 0
    try:
        subprocess.run(['docker', 'run', '-d', '--name', container, '--network', 'none',
                        '-v', f'{repo}:/work/repo', '-v', f'{ROOT}:/grader:ro',
                        '-v', f'{path}:/evidence', image_id, 'sleep', 'infinity'],
                       check=True, capture_output=True, text=True)
        command('Xvfb :99 -screen 0 1280x900x24 >/evidence/xvfb.log 2>&1 &', 10)
        variants = []
        for maximum in (5, 0):
            if shutil.disk_usage(ROOT).free < FREE_FLOOR:
                raise RuntimeError('Less than 3 GiB free before variant build')
            target = '' if maximum == 5 else ' --target heldout_maximum_zero_host.dart'
            built = command('cd /work/repo && flutter pub get --offline && flutter build linux --release --no-pub' + target, 600)
            gui = None
            if built:
                binaries = [p for p in repo.glob('build/linux/*/release/bundle/*') if p.is_file() and p.stat().st_mode & 0o111]
                if len(binaries) != 1:
                    raise RuntimeError(f'Expected one release binary, got {binaries}')
                executable = binaries[0]
                release = path/f'release-maximum{maximum}'
                shutil.copytree(executable.parent, release)
                binary_hash = sha(release/executable.name)
                binary = f'/evidence/release-maximum{maximum}/' + executable.name
                command('DISPLAY=:99 dbus-run-session -- python3 /grader/tools/heldout_gui.py ' + shlex.quote(binary) +
                        f' /evidence/maximum{maximum} --maximum {maximum}', 90)
                gui_path = path/f'maximum{maximum}/gui-result.json'
                gui = json.loads(gui_path.read_text()) if gui_path.exists() else None
            variants.append({'maximum': maximum, 'build_pass': built,
                             'release_executable_sha256': binary_hash if built else None, 'gui': gui,
                             'pass': built and gui is not None and gui['status'] == 'pass'})
        result['variants'] = variants
        result['pass'] = all(v['pass'] for v in variants)
    except Exception as error:
        result.update(error=str(error), **{'pass': False})
    finally:
        subprocess.run(['docker', 'rm', '-f', container], capture_output=True)
        result['artifact_after'] = artifact_hashes(source)
        result['artifact_unchanged'] = before == result['artifact_after']
        result['pass'] = result.get('pass', False) and result['artifact_unchanged']
        (path/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def check(run_id, version='v1'):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run_id) or not re.fullmatch(r'[A-Za-z0-9_-]+', version):
        raise ValueError('Unsafe run or version identifier')
    freeze = json.loads(FREEZE.read_text())
    if freeze['pins'] != pins():
        raise RuntimeError('Frozen probe or dependency pins drifted')
    run = json.loads((ROOT/'runtime'/run_id/'run.json').read_text())
    if run['case_id'] != 'H01':
        raise ValueError('This public-task supplemental probe supports H01 only')
    if run['image_id'] != freeze['image_id']:
        raise ValueError('Runtime image differs from qualification image')
    path = ROOT/'results/heldout-runtime-probe-v1/runs'/run_id/version
    return execute(ROOT/'runtime'/run_id/'repo', path, run['image_id'], run_id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run')
    parser.add_argument('--version', default='v1')
    args = parser.parse_args()
    result = check(args.run, args.version)
    print(json.dumps({k: v for k, v in result.items() if k not in {'checks', 'artifact_before', 'artifact_after', 'variants'}}, indent=2))
