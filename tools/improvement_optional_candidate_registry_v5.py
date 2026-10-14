"""Prospective create-only C22 extension. No allocation admission.

Replay, reservations, leases, integration and native proofs remain with the
qualified registry. This helper never relabels a C22 configuration as C16.
"""
from contextlib import contextmanager
import math
from pathlib import Path
import re
import time

import improvement_optional_registry_v4 as registry
import improvement_optional_runtime_v10 as runtime


def create(folder, run_id, case_id, condition, started_at, initial_tree, editable_paths):
    registry.require(isinstance(run_id, str) and re.fullmatch('[A-Za-z0-9_-]+', run_id),
                     'Invalid run id')
    registry.require(case_id in ('O01', 'O02') and condition in ('A', 'C0', 'C22'),
                     'Invalid prospective allocation')
    registry.require(type(started_at) in (int, float) and math.isfinite(started_at)
                     and 0 < started_at <= time.time(), 'Invalid original start')
    registry.validate_tree(initial_tree)
    registry.require(isinstance(editable_paths, list) and len(editable_paths) == 3
                     and len(set(editable_paths)) == 3,
                     'Exactly three public editable files required')
    for name in editable_paths:
        registry.path_name(name)
        registry.require(name in initial_tree and initial_tree[name]['kind'] == 'file',
                         'Unknown editable file')
    folder = Path(folder)
    folder.mkdir()
    (folder / 'events').mkdir()
    config = dict(run_id=run_id, case_id=case_id, condition=condition,
                  model='gpt-6.1-sol', effort='medium', started_at=started_at,
                  deadline=started_at + 1200, worker_cap=2, retries=0,
                  initial_tree=initial_tree, editable_paths=sorted(editable_paths),
                  native_qualified=False, comparison_eligible=False, superiority_proven=False)
    registry.atomic_json(folder / 'configuration.json', config, exclusive=True)
    return registry.read(folder)


@contextmanager
def creation_hook():
    """Use only around prospective runtime.create; restore on every exit."""
    original = runtime.registry.create
    runtime.registry.create = create
    try:
        yield
    finally:
        runtime.registry.create = original
