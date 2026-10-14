"""Preserve completed evaluation files at identical paths using APFS COW clones."""
import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time

from prepare import ROOT
from compact_completed_intermediates_v366 import confined, independent_reviewer, sha, write_new

REVIEW = ROOT / 'results/evaluation-storage-cow-review-v3.6.6.json'
ALLOWED_NAMES = {'libflutter_linux_gtk.so', 'libapp.so', 'app.so', 'kernel_blob.bin',
                 'MaterialIcons-Regular.otf'}
ARCHIVED_RUNS = ['software-W02-B-1', 'software-W02-C0-2', 'software-W02-A-3']
libc = ctypes.CDLL(None, use_errno=True)
libc.clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
libc.clonefile.restype = ctypes.c_int
libc.listxattr.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
libc.listxattr.restype = ctypes.c_ssize_t
libc.getxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p,
                          ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
libc.getxattr.restype = ctypes.c_ssize_t
libc.setxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p,
                          ctypes.c_size_t, ctypes.c_uint32, ctypes.c_int]
libc.setxattr.restype = ctypes.c_int
libc.removexattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
libc.removexattr.restype = ctypes.c_int


def checked(value):
    if value < 0:
        raise OSError(ctypes.get_errno(), 'Native clone/xattr operation failed')
    return value


def attributes(path):
    raw = os.fsencode(path)
    size = checked(libc.listxattr(raw, None, 0, 0))
    names = ctypes.create_string_buffer(size)
    actual = checked(libc.listxattr(raw, names, size, 0))
    result = {}
    for name in names.raw[:actual].split(b'\0'):
        if not name:
            continue
        length = checked(libc.getxattr(raw, name, None, 0, 0, 0))
        value = ctypes.create_string_buffer(length)
        got = checked(libc.getxattr(raw, name, value, length, 0, 0))
        result[os.fsdecode(name)] = base64.b64encode(value.raw[:got]).decode()
    return result


def metadata(path):
    confined(path)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_flags:
        raise ValueError('Only regular unflagged single-link files are eligible')
    listing = subprocess.check_output(['/bin/ls', '-lde', str(path)], text=True)
    if len(listing.splitlines()) != 1 or '+' in listing.split()[0]:
        raise ValueError('ACL-bearing or ambiguous paths are excluded')
    return {'sha256': sha(path), 'bytes': info.st_size, 'mode': stat.S_IMODE(info.st_mode),
            'uid': info.st_uid, 'gid': info.st_gid, 'mtime_ns': info.st_mtime_ns,
            'type': stat.S_IFMT(info.st_mode), 'links': info.st_nlink, 'flags': info.st_flags,
            'xattrs': attributes(path), 'acl': 'none'}


def preserve_metadata(original, clone, expected):
    os.chown(clone, expected['uid'], expected['gid'])
    os.chmod(clone, expected['mode'])
    current = attributes(clone)
    for name in set(current) - set(expected['xattrs']):
        checked(libc.removexattr(os.fsencode(clone), os.fsencode(name), 0))
    for name, encoded in expected['xattrs'].items():
        value = base64.b64decode(encoded)
        checked(libc.setxattr(os.fsencode(clone), os.fsencode(name), value, len(value), 0, 0))
    os.utime(clone, ns=(original.stat().st_atime_ns, expected['mtime_ns']))
    # macOS may add provenance during attribute writes. Restore the original
    # target's exact attribute set after every metadata write has finished.
    for name in set(attributes(clone)) - set(expected['xattrs']):
        checked(libc.removexattr(os.fsencode(clone), os.fsencode(name), 0))


def eligibility(bases):
    for run_id in ARCHIVED_RUNS:
        runtime = ROOT / 'runtime/revisions/w02-public-scope-v3.6.4' / run_id
        result = ROOT / 'results/revisions/w02-public-scope-v3.6.4' / run_id
        run = json.loads(confined(runtime / 'run.json').read_text())
        grade = json.loads(confined(result / 'grade.json').read_text())
        if grade.get('status') not in {'pass', 'fail'}:
            raise ValueError('Archived owner is not finalized')
        independent_reviewer(grade, result)
        owner = json.loads(subprocess.check_output(['docker', 'inspect', run['container']]))[0]
        if owner['State']['Running']:
            raise ValueError('Archived owner remains active')
    # Qualification jobs are finished and no currently running container may
    # access any eligible tree. Other owners' metadata is never retained/output.
    ids = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
    for identity in ids:
        owner = json.loads(subprocess.check_output(['docker', 'inspect', identity]))[0]
        for mount in owner.get('Mounts', []):
            source = Path(mount.get('Source', '/')).resolve()
            if any(source == base or source.is_relative_to(base) or base.is_relative_to(source)
                   for base in bases):
                raise ValueError('An eligible completed tree has an active container mount')


def clone_duplicates():
    review = json.loads(REVIEW.read_text())
    bases = [confined(ROOT / name) for name in review['scope']['bases']]
    expected_bases = [ROOT / 'runtime/software-validation']
    expected_bases += [ROOT / 'runtime/revisions/w02-public-scope-v3.6.4' / x for x in ARCHIVED_RUNS]
    expected_bases += [ROOT / 'runtime/revisions/w02-public-scope-v3.6.4/software-grading' / x
                       for x in ARCHIVED_RUNS]
    if set(bases) != set(expected_bases):
        raise ValueError('Inventory scope differs from completed approved trees')
    eligibility(bases)
    records = []
    protected = {}
    for group in review['duplicate_groups']:
        paths = [ROOT / name for name in group['paths']]
        if len(paths) < 2:
            continue
        for path in paths:
            if (path.name not in ALLOWED_NAMES or not any(path.is_relative_to(base) for base in bases)
                    or any('\n' in part for part in path.parts)):
                raise ValueError('Unapproved duplicate file family/path')
            actual = metadata(path)
            if (actual['sha256'], actual['bytes'], actual['mode']) != (
                    group['sha256'], group['bytes_each'], group['mode']):
                raise ValueError('Inventory changed before preregistration')
            protected[str(path.relative_to(ROOT))] = actual
        records.extend({'source': str(paths[0].relative_to(ROOT)),
                        'target': str(path.relative_to(ROOT)), 'original': protected[str(path.relative_to(ROOT))]}
                       for path in paths[1:])
    # Protect every retained file/symlink/directory in the completed eligible trees.
    from compact_completed_intermediates_v366 import path_evidence
    evidence = {str(p.relative_to(ROOT)): path_evidence(p)
                for base in bases for p in [base, *base.rglob('*')]}
    token = str(time.time_ns())
    output = ROOT / 'results/cow-preservation'
    output.mkdir(exist_ok=True)
    confined(output)
    plan = {'status': 'preregistered_before_any_clone', 'records': records,
            'retained_file_metadata': protected, 'protected_path_evidence': evidence,
            'helper_sha256': sha(Path(__file__)), 'inventory_sha256': sha(REVIEW),
            'free_before': shutil.disk_usage(ROOT).free,
            'inode_ctime_birthtime_changes_are_storage_only': True}
    plan_path = output / (token + '-plan.json')
    write_new(plan_path, plan)
    completed = []
    for index, record in enumerate(records):
        source, target = ROOT / record['source'], ROOT / record['target']
        expected = record['original']
        if metadata(source) != protected[record['source']] or metadata(target) != expected:
            raise ValueError('Planned twin/target changed before cloning')
        temporary = target.with_name('.cow-preserved-' + token + '-' + str(index))
        if temporary.exists() or temporary.is_symlink():
            raise ValueError('Clone destination exists')
        checked(libc.clonefile(os.fsencode(source), os.fsencode(temporary), 0))
        try:
            preserve_metadata(target, temporary, expected)
            if metadata(temporary) != expected:
                raise ValueError('Clone bytes/metadata differ from original target')
            if metadata(source) != protected[record['source']] or metadata(target) != expected:
                raise ValueError('Twin/target changed before atomic replacement')
            os.replace(temporary, target)
            if metadata(target) != expected:
                raise ValueError('Atomic replacement failed retained metadata check')
            completed.append(record['target'])
        finally:
            if temporary.exists():
                temporary.unlink()
    if any(metadata(ROOT / name) != value for name, value in protected.items()):
        raise ValueError('Retained duplicate metadata changed')
    if any(path_evidence(ROOT / name) != value for name, value in evidence.items()):
        raise ValueError('Protected completed evidence changed')
    result = {'status': 'complete', 'plan': str(plan_path), 'plan_sha256': sha(plan_path),
              'targets_cloned': len(completed), 'protected_paths_unchanged': len(evidence),
              'retained_metadata_unchanged': len(protected), 'free_after': shutil.disk_usage(ROOT).free,
              'all_original_paths_bytes_modes_ownership_mtime_xattrs_retained': True,
              'hard_links_created': False, 'source_native_scores_changed': False}
    write_new(output / (token + '-complete.json'), result)
    return result


if __name__ == '__main__':
    print(json.dumps(clone_duplicates()))
