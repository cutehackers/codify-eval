import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

class ConflictError(ValueError):
    pass

class IntegrityError(ValueError):
    pass

def valid_paths(paths):
    for key in paths:
        if not isinstance(key,str) or not key or '\\' in key or '\x00' in key or any(part in ('','.','..') for part in key.split('/')) or key.split('/')[0]=='manifest.json':
            raise ValueError('invalid file path')
        parts=key.split('/')
        if any('/'.join(parts[:i]) in paths for i in range(1,len(parts))):
            raise ValueError('file and directory collision')

def inspect_existing(destination):
    try:
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError('invalid snapshot directory')
        found={}
        for parent, dirs, files in os.walk(destination, followlinks=False):
            for name in dirs+files:
                if (Path(parent)/name).is_symlink():
                    raise ValueError('symlink in snapshot')
            for name in files:
                path=Path(parent)/name;key=path.relative_to(destination).as_posix()
                if key != 'manifest.json':
                    found[key]=hashlib.sha256(path.read_bytes()).hexdigest()
        manifest=json.loads((destination/'manifest.json').read_text(encoding='utf-8'))
        if not isinstance(manifest,dict) or set(manifest)!={'files'} or not isinstance(manifest['files'],dict):
            raise ValueError('invalid manifest')
        expected=manifest['files'];valid_paths(expected)
        if any(not isinstance(value,str) or re.fullmatch('[0-9a-f]{64}',value) is None for value in expected.values()) or found!=expected:
            raise ValueError('snapshot contents do not match manifest')
        return expected
    except (OSError,ValueError,TypeError) as exc:
        raise IntegrityError('existing snapshot is corrupt') from exc

def publish_snapshot(root, snapshot_id, entries):
    if not isinstance(snapshot_id,str) or re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,63}',snapshot_id) is None or not isinstance(entries,dict):
        raise ValueError('invalid snapshot request')
    valid_paths(entries)
    if any(not isinstance(value,bytes) for value in entries.values()):
        raise ValueError('file content must be bytes')
    root=Path(root)
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError('root must be a directory, not a symlink')
    hashes={key:hashlib.sha256(value).hexdigest() for key,value in entries.items()}
    destination=root/snapshot_id
    if destination.exists() or destination.is_symlink():
        existing=inspect_existing(destination)
        if existing!=hashes:
            raise ConflictError('snapshot ID already contains different files')
        return destination
    root.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.stage-',dir=root))
    try:
        for key,value in entries.items():
            path=staging/key;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
        (staging/'manifest.json').write_text(json.dumps({'files':hashes},sort_keys=True),encoding='utf-8')
        os.replace(staging,destination)
        return destination
    finally:
        if staging.exists():
            shutil.rmtree(staging)
