"""C19 namespace adapter over the unchanged append-safe deadline authority.

No native dispatch/interruption or new clock. Caller requires frozen admission.
"""
from contextlib import contextmanager
from pathlib import Path

import improvement_optional_comparison_inputs_v3 as inputs
import improvement_optional_deadline_close_v2 as original
import improvement_optional_native_watch_v5 as observer


@contextmanager
def namespace():
    before = original.previous.inputs
    current = original.inputs
    original.previous.inputs = inputs
    original.inputs = inputs
    try:
        with observer.lifecycle_decoder():
            yield
    finally:
        original.previous.inputs = before
        original.inputs = current


def valid(folder):
    folder = Path(folder).resolve()
    original.original.require(folder.parent == inputs.ROOT / 'runtime', 'Exact owned parent required')
    rows = [row for row in inputs.sequence() if row['run_id'] == folder.name]
    original.original.require(len(rows) == 1, 'Exact C19 comparison namespace required')
    return folder


def commit(folder, coordinator_source):
    folder = valid(folder)
    with namespace():
        return original.commit(folder, coordinator_source)


def close(folder, coordinator_source):
    folder = valid(folder)
    with namespace():
        return original.close(folder, coordinator_source)
