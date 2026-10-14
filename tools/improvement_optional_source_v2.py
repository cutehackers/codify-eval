"""Bounded full safe inventory and source-only projection for O01/O02.

Caller must hold job/registry fences and prove actors cannot write during export.
No universal filesystem firewall or native/container authority is established.
Only exact top-level .dart_tool/build are mutable generated regions; .git is
separately protected and never exported to acceptance verifiers.
"""
import hashlib
import math
import os
from pathlib import Path
import stat
import time

from improvement_optional_registry_v2 import require, validate_tree

GENERATED={'.dart_tool','build'}
MAX_BYTES=512*1024*1024
MAX_ENTITIES=20000


def clock(deadline):
    if deadline is not None:
        require(type(deadline) in (int,float) and math.isfinite(deadline) and time.time()<deadline,
                'Original deadline exhausted')


def read_file(path, expected=None, deadline=None):
    clock(deadline)
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode),'Regular file required')
        if expected is not None:
            require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==expected,
                    'File changed before read')
        digest=hashlib.sha256();read_bytes=0
        with os.fdopen(descriptor,'rb',closefd=False) as stream:
            while True:
                clock(deadline);chunk=stream.read(1024*1024)
                if not chunk:break
                read_bytes+=len(chunk)
                require(read_bytes<=before.st_size,'File grew beyond bounded initial size')
                digest.update(chunk)
        after=os.fstat(descriptor)
        require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),
                'File changed during read')
        return digest.hexdigest()
    finally:os.close(descriptor)


def inventory(repo, deadline=None, max_bytes=MAX_BYTES, max_entities=MAX_ENTITIES):
    repo=Path(repo)
    require(type(max_bytes) is int and max_bytes>0 and type(max_entities) is int and max_entities>0,
            'Invalid inventory bounds')
    clock(deadline);root=repo.lstat()
    require(stat.S_ISDIR(root.st_mode),'Real repository directory required')
    entities={'.':{'kind':'directory','mode':stat.S_IMODE(root.st_mode)}};total=0
    stack=[repo]
    while stack:
        directory=stack.pop();clock(deadline)
        entries=[]
        with os.scandir(directory) as children:
            for entry in children:
                clock(deadline)
                require(len(entities)+len(entries)<max_entities,
                        'Directory enumeration exceeds remaining entity budget')
                entries.append(entry)
        clock(deadline);entries.sort(key=lambda p:p.name);clock(deadline)
        for entry in entries:
            clock(deadline);s=entry.stat(follow_symlinks=False);name=Path(entry.path).relative_to(repo).as_posix()
            require(len(entities)<max_entities,'Entity inventory bound exceeded')
            if stat.S_ISDIR(s.st_mode):
                entities[name]={'kind':'directory','mode':stat.S_IMODE(s.st_mode)};stack.append(Path(entry.path))
            elif stat.S_ISREG(s.st_mode):
                total+=s.st_size;require(total<=max_bytes,'Inventory byte bound exceeded before read')
                digest=read_file(entry.path,(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns),deadline)
                entities[name]={'kind':'file','mode':stat.S_IMODE(s.st_mode),'sha256':digest}
            else:raise ValueError('Symlink/special entity denied including generated/Git descendants: '+name)
    validate_tree(entities)
    for name in GENERATED|{'.git'}:
        require(name not in entities or entities[name]['kind']=='directory','Generated/Git root must be directory')
    source={name:value for name,value in entities.items() if name.split('/')[0] not in GENERATED|{'.git'}}
    git={name:value for name,value in entities.items() if name.split('/')[0]=='.git'}
    clock(deadline)
    return {'all_entities':entities,'source_entities':source,'git_entities':git,
            'total_regular_bytes':total,'generated_roots':sorted(GENERATED),
            'native_qualified':False,'comparison_eligible':False}


def check_changes(before, after, editable_paths):
    require(before['generated_roots']==after['generated_roots']==sorted(GENERATED),'Generated policy changed')
    require(before['git_entities']==after['git_entities'],'Git administrative tree changed')
    original=before['source_entities'];current=after['source_entities']
    require(set(original)==set(current),'Protected source additions/removals')
    require(isinstance(editable_paths,list) and len(set(editable_paths))==len(editable_paths)
            and all(name in original and original[name]['kind']=='file' for name in editable_paths),
            'Invalid exact editable path allowlist')
    for name,entity in original.items():
        if name in editable_paths:
            require(current[name]['kind']==entity['kind'] and current[name]['mode']==entity['mode'],
                    'Editable kind/mode changed')
        else:require(current[name]==entity,'Protected source changed: '+name)
    return True


def export(repo, snapshot, destination, deadline=None):
    """Exact canonical public source copy, after complete safe inventory."""
    repo=Path(repo);destination=Path(destination)
    require(repo.resolve()!=destination.resolve() and repo.resolve() not in destination.resolve().parents,
            'Export must be outside checkout')
    require(inventory(repo,deadline)==snapshot,'Snapshot/projection changed before export')
    source=snapshot['source_entities'];validate_tree(source)
    destination.mkdir()
    for name,entity in sorted(source.items(),key=lambda pair:(len(Path(pair[0]).parts),pair[0])):
        if name=='.':continue
        target=destination/name
        if entity['kind']=='directory':target.mkdir()
        else:
            clock(deadline);path=repo/name
            require(path.lstat().st_size<=1024*1024,'Protected source export file exceeds artifact limit')
            descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            try:
                require(stat.S_ISREG(os.fstat(descriptor).st_mode),'Source ceased to be regular file')
                with os.fdopen(descriptor,'rb',closefd=False) as stream:raw=stream.read(1024*1024+1)
            finally:os.close(descriptor)
            require(len(raw)<=1024*1024 and hashlib.sha256(raw).hexdigest()==entity['sha256'],
                    'Source changed during export')
            with target.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            os.chmod(target,entity['mode'])
    for name,entity in sorted(source.items(),key=lambda pair:len(Path(pair[0]).parts),reverse=True):
        if entity['kind']=='directory':os.chmod(destination if name=='.' else destination/name,entity['mode'])
    require(inventory(destination,deadline)['all_entities']==source,'Export tree differs from exact source')
    require(inventory(repo,deadline)['all_entities']==snapshot['all_entities'],'Checkout changed during export')
    return destination
