"""Prospective original observer with qualified adjacent 1ms delivery decoding.

No restart, actor control, changed clock or filtered source records.
"""
import argparse
from contextlib import contextmanager
import improvement_optional_native_watch_v4 as original
import improvement_optional_lifecycle_v5 as replacement

@contextmanager
def lifecycle_decoder():
    saved = original.lifecycle.lifecycle
    original.lifecycle.lifecycle = replacement.lifecycle
    try:
        yield
    finally:
        original.lifecycle.lifecycle = saved

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run'); parser.add_argument('root_path'); parser.add_argument('parent_id')
    args = parser.parse_args()
    with lifecycle_decoder():
        original.supervise(original.ROOT / 'runtime' / args.run, args.root_path, args.parent_id)
