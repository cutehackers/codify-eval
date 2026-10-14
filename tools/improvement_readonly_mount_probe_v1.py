"""Real Docker read-only boundary probes, separate from model evaluation."""
import hashlib
import json
import subprocess
from pathlib import Path

from prepare import ROOT


def main():
    folder = ROOT / 'runtime/protocol-probes/readonly-mount-v1'
    folder.mkdir(parents=True)
    repo, inputs = folder / 'repo', folder / 'inputs'
    repo.mkdir(); inputs.mkdir()
    (repo / 'protected.txt').write_text('original\n')
    original = hashlib.sha256((repo / 'protected.txt').read_bytes()).hexdigest()
    image = json.loads((ROOT / 'runtime/image.json').read_text())['image_id']
    name = 'codify-protocol-readonly-mount-v1'
    if subprocess.run(['docker', 'inspect', name], capture_output=True).returncode == 0:
        raise ValueError('Existing container; preserve prior attempt')
    result = {'status': 'pending', 'image_id': image, 'name': name,
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': 'Actual Docker RO mounts only; no native delivery/question/model qualification'}
    try:
        subprocess.run(['docker', 'run', '-d', '--name', name, '--network', 'none',
                        '--label', 'codify.protocol.probe=readonly-mount-v1',
                        '-v', str(repo) + ':/work/repo:ro', '-v', str(inputs) + ':/eval-input:ro',
                        image, 'sleep', 'infinity'], check=True, capture_output=True)
        identity = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]
        assert identity['Image'] == image and identity['HostConfig']['NetworkMode'] == 'none'
        assert len(identity['Mounts']) == 2 and all(not m['RW'] for m in identity['Mounts'])
        result['identity_before'] = identity
        code = '''import errno,json,os,pathlib
base=pathlib.Path('/work/repo'); protected=base/'protected.txt'
alias=pathlib.Path('/tmp/codify-probe-alias');alias.symlink_to(base,target_is_directory=True)
def revert():
 protected.write_text('changed');protected.write_text('original\\n')
operations=[('create',lambda:(base/'new.txt').write_text('new')),
 ('edit',lambda:protected.write_text('changed')),
 ('delete',lambda:protected.unlink()),('write_and_revert',revert),
 ('rename',lambda:protected.rename(base/'renamed.txt')),
 ('scratch_symlink_to_repo',lambda:(alias/'protected.txt').write_text('changed')),
 ('parent_path_to_repo',lambda:pathlib.Path('/work/repo/../repo/protected.txt').write_text('changed')),
 ('early_control_write',lambda:pathlib.Path('/eval-input/turn-2.txt').write_text('forged'))]
out=[]
for name,operation in operations:
 try:
  operation();out.append({'name':name,'denied':False})
 except OSError as error:
  out.append({'name':name,'denied':error.errno==errno.EROFS,'errno':error.errno})
pathlib.Path('/tmp/codify-probe-scratch').write_text('scratch usable')
assert all(row['denied'] for row in out),out
assert protected.read_text()=='original\\n'
assert not pathlib.Path('/eval-input/turn-2.txt').exists()
print(json.dumps({'operations':out,'scratch_writable':True,'protected_unchanged':True}))
'''
        execution = subprocess.run(['docker', 'exec', name, 'python3', '-c', code], capture_output=True, text=True, timeout=30)
        result['execution'] = {'exit_code': execution.returncode, 'stdout': execution.stdout, 'stderr': execution.stderr}
        assert execution.returncode == 0, execution.stderr
        result.update(json.loads(execution.stdout))
        assert hashlib.sha256((repo / 'protected.txt').read_bytes()).hexdigest() == original
        assert list(inputs.iterdir()) == []
        result['status'] = 'pass'
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        current = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True)
        if current.returncode == 0:
            identity = json.loads(current.stdout)[0]
            if identity['Config'].get('Labels', {}).get('codify.protocol.probe') != 'readonly-mount-v1':
                raise ValueError('Refuse cleanup of unowned container')
            subprocess.run(['docker', 'stop', '-t', '2', name], check=True, capture_output=True)
            result['identity_stopped'] = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]
            result['docker_diff'] = subprocess.check_output(['docker', 'diff', name], text=True)
            with (folder / 'container-tmp.tar').open('xb') as stream:
                subprocess.run(['docker', 'cp', name + ':/tmp', '-'], check=True, stdout=stream, stderr=subprocess.PIPE)
            subprocess.run(['docker', 'rm', name], check=True, capture_output=True)
            result['owned_container_removed'] = True
        target = ROOT / 'results/improvement-v1/readonly-mount-v1-probe.json'
        with target.open('x') as stream:
            json.dump(result, stream, indent=2)
    print(json.dumps({k: result[k] for k in ('status', 'operations', 'owned_container_removed')}))


if __name__ == '__main__':
    main()
