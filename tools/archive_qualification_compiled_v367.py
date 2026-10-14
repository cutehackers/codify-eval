"""Archive exact completed qualification build outputs, retaining scored files."""
import json
import os
from pathlib import Path
import shutil
import stat
import tarfile
import tempfile
import time

from compact_completed_intermediates_v367 import ROOT, confined, path_evidence, sha, write_new
from clone_completed_duplicates_v366 import eligibility

PLAN = ROOT / 'results/qualification-compiled-storage-plan-v3.6.7.json'
MANIFEST = ROOT / 'results/frozen-qualification-compiled-storage-v3.6.7.json'
BASE = ROOT / 'runtime/software-validation'
NAMES = {'libflutter_linux_gtk.so', 'libapp.so', 'app.so',
         'kernel_blob.bin', 'MaterialIcons-Regular.otf'}


def archive_completed():
    registration = json.loads(MANIFEST.read_text())
    for name, expected in registration['source_sha256'].items():
        if sha(confined(ROOT / name)) != expected:
            raise ValueError('Qualification archive registration changed')
    plan = json.loads(PLAN.read_text())
    if plan['base'] != str(BASE) or not plan['qualification_only']:
        raise ValueError('Only completed qualification outputs are eligible')
    eligibility([confined(BASE)])
    records = plan['files']
    protected = {}
    for name, record in records.items():
        path = confined(ROOT / name)
        relative = path.relative_to(BASE)
        if 'build' not in relative.parts or not (
                path.name in NAMES or (path.suffix == '.dill' and 'test_cache' in relative.parts)):
            raise ValueError('Candidate is outside exact compiled qualification outputs')
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or path.is_symlink():
            raise ValueError('Candidate must be a regular single-link file')
        if path_evidence(path) != record['original_lstat']:
            raise ValueError('Qualification output changed since inventory')
    for path in [BASE, *BASE.rglob('*')]:
        name = str(path.relative_to(ROOT))
        if name not in records:
            protected[name] = path_evidence(path)
    output = ROOT / 'results/qualification-compiled-preservation'
    output.mkdir(exist_ok=True)
    confined(output)
    token = str(time.time_ns())
    archive = output / (token + '.tar.gz')
    before = {'status': 'preregistered_before_archive', 'files': records,
              'protected_path_evidence': protected, 'archive': str(archive),
              'registration_sha256': sha(MANIFEST), 'source_plan_sha256': sha(PLAN),
              'helper_sha256': sha(Path(__file__)), 'free_before': shutil.disk_usage(ROOT).free}
    before_path = output / (token + '-plan.json')
    write_new(before_path, before)
    with tarfile.open(archive, 'x:gz', compresslevel=1) as stream:
        for name in records:
            stream.add(ROOT / name, arcname=name, recursive=False)
    seen = set()
    with tempfile.TemporaryDirectory() as temporary, tarfile.open(archive, 'r|gz') as stream:
        for index, member in enumerate(stream):
            if member.name not in records or member.name in seen or not member.isfile():
                raise ValueError('Unexpected archive member')
            target = Path(temporary) / str(index)
            data = stream.extractfile(member)
            if data is None:
                raise ValueError('Missing archive member bytes')
            with data, target.open('xb') as restored:
                shutil.copyfileobj(data, restored)
            os.chmod(target, member.mode)
            record = records[member.name]
            if (sha(target), target.stat().st_size, stat.S_IMODE(target.stat().st_mode)) != (
                    record['sha256'], record['bytes'], record['mode']):
                raise ValueError('Restored archive byte/hash/mode mismatch')
            target.unlink()
            seen.add(member.name)
    if seen != set(records):
        raise ValueError('Archive membership incomplete')
    proof = {**before, 'status': 'full_restore_verified_before_relocation',
             'plan_sha256': sha(before_path), 'archive_sha256': sha(archive),
             'archive_bytes': archive.stat().st_size, 'members_verified': len(seen)}
    proof_path = output / (token + '-preservation.json')
    write_new(proof_path, proof)
    eligibility([confined(BASE)])
    for name, expected in protected.items():
        if path_evidence(ROOT / name) != expected:
            raise ValueError('Protected qualification evidence changed')
    for name, record in records.items():
        if path_evidence(confined(ROOT / name)) != record['original_lstat']:
            raise ValueError('Original qualification output changed before relocation')
    for name in records:
        (ROOT / name).unlink()
    for name, expected in protected.items():
        if path_evidence(ROOT / name) != expected:
            raise ValueError('Protected qualification evidence changed after relocation')
    result = {'status': 'complete', 'archive': str(archive),
              'preservation_path': str(proof_path), 'preservation_sha256': sha(proof_path),
              'members_relocated': len(records), 'original_bytes': sum(x['bytes'] for x in records.values()),
              'archive_bytes': archive.stat().st_size, 'protected_paths_unchanged': len(protected),
              'selected_actor_grader_release_native_scores_touched': False,
              'free_after': shutil.disk_usage(ROOT).free}
    write_new(output / (token + '-complete.json'), result)
    return result


if __name__ == '__main__':
    print(json.dumps(archive_completed()))
