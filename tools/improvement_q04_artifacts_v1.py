"""Fixed Q04 module scopes over the unchanged reviewed artifact core.

Draft adapter. Native identity, runtime acceptance and behavior qualification
remain external prerequisites.
"""
from improvement_software_artifacts_v3 import (
    LIMIT, digest, encoded, path_name, tree, atomic_json, seal_worker,
    locked, contributions, staging_paths, apply_files, integrate, recover,
)


def freeze_base(repo, scopes):
    assert scopes == {'pricing': 'lib/pricing.dart', 'reservations': 'lib/reservations.dart'}, 'Fixed Q04 ownership only'
    files = tree(repo)
    for name in scopes.values():
        path_name(name)
        assert name in files and files[name]['kind'] == 'file'
    return {'files': files, 'scopes': dict(scopes), 'tree_sha256': digest(encoded(files))}
