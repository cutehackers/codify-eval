"""Actor-free draft qualification copies. Not a product allocator or grader.

Private overlays are restricted to isolated qualification sources. Callers must
retain failed copies and provide a complete, unchanged case inventory. SDK and
live-question admission, independent case review and model freezes are separate.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / 'improvement_cases/independent-baseline-pilot-drafts-v2'
OUTPUT = ROOT / 'runtime/independent-baseline-pilot-fixture-qualification-v2'
CASES = ('B01', 'B02', 'B03', 'B04')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode()


def canonical(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts
            and path.resolve(strict=True) == path, 'Canonical existing path required')
    return path


def relative(value):
    require(isinstance(value, str) and bool(value) and '\\' not in value,
            'Literal relative source path required')
    path = Path(value)
    require(not path.is_absolute() and path.as_posix() == value
            and all(part not in ('', '.', '..') for part in value.split('/')),
            'Canonical relative source path required')
    return path


def inventory(directory):
    directory = canonical(directory)
    require(stat.S_ISDIR(directory.lstat().st_mode), 'Real source directory required')
    pins = {}; total = 0
    for path in [directory] + sorted(directory.rglob('*')):
        info = path.lstat()
        require(not path.is_symlink(), 'Source symlinks are forbidden')
        key = path.relative_to(directory).as_posix()
        if stat.S_ISDIR(info.st_mode):
            pins[key] = {'kind': 'directory', 'mode': stat.S_IMODE(info.st_mode)}
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                    'Single-link regular source file required')
            require(info.st_size <= 2 * 1024**2, 'Individual fixture source is too large')
            raw = path.read_bytes(); after = path.lstat()
            require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                    == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
                    'Source changed during capture')
            total += len(raw)
            require(total <= 50 * 1024**2, 'Bounded fixture inventory required')
            pins[key] = {'kind': 'file', 'mode': stat.S_IMODE(info.st_mode),
                         'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    return pins


def capture(case):
    require(case in CASES, 'Registered pilot draft case required')
    directory = canonical(COHORT / case)
    require(directory.parent == canonical(COHORT), 'Exact pilot case ownership required')
    return inventory(directory)


def copy_module(source, destination):
    canonical(source)
    require(stat.S_ISREG(source.lstat().st_mode) and source.stat().st_nlink == 1,
            'Regular private module required')
    require(destination.is_file() and not destination.is_symlink(),
            'Overlay must replace an existing public module')
    require(stat.S_IMODE(source.stat().st_mode) == stat.S_IMODE(destination.stat().st_mode),
            'Overlay must preserve public source mode')
    shutil.copyfile(source, destination)


def materialize(case, label, original_inventory, *, reference=False,
                branch=None, acceptance=False):
    """Create one copy for fixture qualification only, without running commands.

    Branch identifiers and private contents belong to the independent fixture
    qualifier. Returning these source paths never grants product-agent access.
    """
    require(case in CASES and isinstance(label, str)
            and re.fullmatch('[a-z][a-z0-9_-]{0,63}', label), 'Exact new variant name required')
    require(type(reference) is bool and type(acceptance) is bool,
            'Typed qualification flags required')
    require(branch is None or (reference and isinstance(branch, str)
            and re.fullmatch('[A-Za-z][A-Za-z0-9_-]{0,63}', branch)),
            'A branch overlay requires a reference and a literal branch identifier')
    require(isinstance(original_inventory, dict) and bool(original_inventory)
            and encoded(capture(case)) == encoded(original_inventory),
            'Complete original draft inventory changed')
    directory = canonical(COHORT / case)
    metadata = json.loads((directory / 'metadata.json').read_bytes())
    edits = metadata['editable_paths']
    require(isinstance(edits, list) and len(edits) >= 3 and len(edits) == len(set(edits)),
            'Exact declared editable module set required')
    for value in edits:
        path = relative(value)
        require(path.parts[0] == 'lib' and value.endswith('.dart')
                and (directory / 'public' / path).is_file(),
                'Declared authored public module required')
    require(canonical(ROOT / 'runtime') == ROOT / 'runtime', 'Real runtime parent required')
    require(not OUTPUT.is_symlink(), 'Qualification parent cannot be a symlink')
    OUTPUT.mkdir(exist_ok=True)
    require(canonical(OUTPUT) == OUTPUT, 'Canonical qualification-only parent required')
    variant = OUTPUT / (case.lower() + '-' + label)
    require(not variant.exists() and not variant.is_symlink(), 'No overwritten qualification variant')
    variant.mkdir()
    record = {'case_id': case, 'label': label, 'reference': reference,
              'branch': branch, 'branch_overlay_present': branch is not None,
              'acceptance': acceptance,
              'original_inventory': original_inventory,
              'model_allocation_admitted': False, 'comparison_admitted': False,
              'software_qualified': False, 'live_question_qualified': False}
    with (variant / 'materialization-intent.json').open('xb') as stream:
        stream.write(encoded(record))
    source = variant / 'source'
    shutil.copytree(directory / 'public', source)
    if reference:
        modules = inventory(directory / 'private/reference/lib')
        names = {'lib/' + name for name, pin in modules.items() if pin['kind'] == 'file'}
        require(names == set(edits), 'Reference may replace only the exact declared modules')
        for name in sorted(edits):
            copy_module(directory / 'private/reference' / name, source / name)
    if branch is not None:
        overlay = canonical(directory / 'private/reference/branches' / branch / 'lib')
        pins = inventory(overlay)
        names = {'lib/' + name for name, pin in pins.items() if pin['kind'] == 'file'}
        require(bool(names) and names <= set(edits), 'Branch may only replace declared modules')
        for name in sorted(names):
            copy_module(overlay / Path(name).relative_to('lib'), source / name)
    if acceptance:
        private = canonical(directory / 'private/test/acceptance_test.dart')
        target = source / 'test/pilot_acceptance_test.dart'
        require(not target.exists() and not target.is_symlink(), 'Private-test destination collision')
        shutil.copy2(private, target)
    require(encoded(capture(case)) == encoded(original_inventory),
            'Original draft changed while copying')
    record['source_inventory'] = inventory(source)
    with (variant / 'materialization-outcome.json').open('xb') as stream:
        stream.write(encoded(record))
    return {'source': source, 'variant': variant, 'record': record}
