"""Synchronous prospective skill export with an immutable selected row.

Initial root export remains inside runtime.create's original clock.

The caller must supply a separately frozen full source inventory for the selected
skill. Current bytes cannot self-authorize admission. This context neither
allocates actors nor establishes fixture/candidate/comparison qualification.
The reviewed prospective driver must use one synchronous coordinator at a time.
"""
from contextlib import contextmanager
from pathlib import Path
import threading

import improvement_baseline_comparison_inputs_v1 as inputs
import improvement_baseline_runtime_v1 as runtime

_active = False
require = runtime.require


@contextmanager
def skill_export(row, folder, frozen_skill_inventory):
    global _active
    inputs.row_valid(row)
    # Freeze the entire selected route, not only its skill inventory.
    row = runtime.strict.decoded(runtime.encoded(row))
    require(threading.current_thread() is threading.main_thread() and not _active,
            'One synchronous main-thread skill export context required')
    folder = Path(folder)
    require(folder.is_absolute() and folder == folder.resolve()
            and not folder.exists() and not folder.is_symlink(),
            'New exact canonical runtime namespace required')
    public = inputs.ROOT / inputs.public_contract(row)['public_root']
    require(not public.is_symlink() and public == public.resolve(),
            'Exact qualified public starting source required')
    if row['condition'] == 'A':
        require(frozen_skill_inventory is None, 'No skill inventory for no-skill control')
    else:
        require(type(frozen_skill_inventory) is dict,
                'Separately frozen full selected skill inventory required')
        require(frozen_skill_inventory.get('source_entities', {}).get('SKILL.md', {}).get('kind') == 'file',
                'Frozen selected skill entrypoint required')
    # Snapshot the authority, including all nested JSON scalar types, so a caller
    # cannot change it while source export is in progress.
    frozen = None if frozen_skill_inventory is None else runtime.strict.decoded(runtime.encoded(frozen_skill_inventory))
    original = runtime.source.export
    exported_once = False

    def exported(starting, inventory, destination, deadline):
        nonlocal exported_once
        result = original(starting, inventory, destination, deadline)
        if Path(starting) == public and Path(destination) == folder / 'root/repo':
            require(not exported_once and deadline is not None,
                    'One initial root export on the original runtime clock required')
            exported_once = True
            if row['condition'] != 'A':
                skill = inputs.ROOT / 'snapshots' / row['condition']
                require(skill == skill.resolve() and not skill.is_symlink(),
                        'Exact selected frozen skill directory required')
                actual = runtime.source.inventory(skill, deadline)
                require(runtime.encoded(actual) == runtime.encoded(frozen),
                        'Selected skill differs from separately frozen inventory')
                target = Path(destination) / '.agents/skills/codify'
                require(not (Path(destination) / '.agents').exists(),
                        'Public starting source cannot collide with skill destination')
                target.parent.mkdir(parents=True)
                original(skill, actual, target, deadline)
                require(runtime.encoded(runtime.source.inventory(skill, deadline)) == runtime.encoded(frozen),
                        'Selected skill changed during protected root export')
        return result

    _active = True
    runtime.source.export = exported
    try:
        yield
    finally:
        runtime.source.export = original
        _active = False
