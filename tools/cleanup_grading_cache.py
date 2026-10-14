"""Remove derived Flutter caches only from finalized external grading copies."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

from prepare import ROOT
from report import recorded_status


def sources(directory):
    return {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*'))
            if p.is_file() and not p.is_symlink()
            and p.relative_to(directory).parts[0] not in {'build', '.dart_tool'}}


def cleanup(apply=False):
    records = []
    grading = ROOT / 'runtime' / 'grading'
    if not grading.exists():
        return records
    for directory in sorted(grading.iterdir()):
        if not directory.is_dir() or directory.is_symlink():
            continue
        grade_file = ROOT / 'results' / directory.name / 'grade.json'
        if not grade_file.exists():
            continue
        grade = json.loads(grade_file.read_text())
        if recorded_status(grade) not in {'pass', 'fail'}:
            continue
        caches = [directory / name for name in ('build', '.dart_tool')
                  if (directory / name).is_dir() and not (directory / name).is_symlink()]
        if not caches:
            continue
        before = sources(directory)
        record = {'run_id': directory.name, 'paths': [str(p) for p in caches],
                  'logical_bytes': sum(p.stat().st_size for cache in caches
                                       for p in cache.rglob('*')
                                       if p.is_file() and not p.is_symlink()),
                  'source_sha256': before, 'removed': False}
        if apply:
            for cache in caches:
                shutil.rmtree(cache)
            if sources(directory) != before:
                raise RuntimeError(f'Grading input changed: {directory}')
            record.update(removed=True, sources_unchanged=True)
        records.append(record)
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Default is read-only planning')
    args = parser.parse_args()
    records = cleanup(args.apply)
    result = {'apply': args.apply, 'records': records,
              'free_bytes': shutil.disk_usage(ROOT).free,
              'recorded_at': datetime.now(timezone.utc).isoformat()}
    if args.apply:
        folder = ROOT / 'results' / 'grading-cache-cleanup'
        folder.mkdir(exist_ok=True)
        target = folder / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
        target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        result['evidence'] = str(target)
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}, indent=2))
    print(json.dumps({'eligible_runs': len(records),
                      'logical_bytes': sum(r['logical_bytes'] for r in records)}, indent=2))
