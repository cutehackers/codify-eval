"""One prospective native interruption control, never a candidate comparison.

Freeze independently reviewed sources before preparation. The original root
coordinator starts observation, dispatches the encrypted original request, then
commits and interrupts the same actual member family at the original deadline.
"""
import json
import re
import time

import improvement_optional_native_control_v9 as shared
import improvement_optional_deadline_close_v1 as deadline

ROOT, BASE = shared.ROOT, shared.BASE
FREEZE = BASE / 'fresh-optional-deadline-control-freeze-v1.json'
REVIEWS = ('C17-optional-deadline-members-review-v1.json',
           'C17-optional-deadline-close-review-v1.json',
           'C17-optional-deadline-control-prelaunch-review-v1.json')
TASK = ('INFRASTRUCTURE INTERRUPTION CONTROL, NOT A SOFTWARE COMPARISON. '
        'Use the registered broker only. Read the public task and repository. '
        'Allocate exactly two cumulative read-only workers with empty scopes, '
        'named worker1 and worker2, through the broker and original native dispatch. '
        'Assign one to inspect the public API and one to inspect public tests. '
        'Every worker must use gpt-6.1-sol / medium, fork_turns none. '
        'Tell both workers this is a bounded interruption control: inspect their '
        'assigned files without modifying anything, then keep their original turn '
        'active through broker exec sleep 90 and same-handle polling until the '
        'coordinator interrupts them at the shared original 1200-second deadline. '
        'Keep your original root turn active in the same way. Do not allocate '
        'replacement actors, deliver followups, integrate, seal or finish early. '
        'Never read private acceptance or other runs. No software outcome is being '
        'graded. Native interruption and exact owned cleanup are performed by the '
        'original top-level coordinator, not by you or the watcher.\n\nPUBLIC TASK\n')


def payload():
    original = shared.checked_freeze()
    sources = dict(original['source_entities']); reviews = {}
    for name in REVIEWS:
        path = BASE / name; review = json.loads(path.read_bytes())
        shared.require(review['verdict'] == 'pass' and not review['issues'], 'Independent prelaunch PASS required')
        reviews[name] = shared.entity(path)
        for key, pin in review['source_entities'].items():
            source = ROOT / key
            actual = shared.reviewed_entity(source, pin)
            shared.require(key not in sources or sources[key] == actual, 'Conflicting reviewed source closure')
            sources[key] = actual
    essential = [__file__, deadline.__file__, deadline.aggregate.__file__]
    registered = {(ROOT / key).resolve() for key in sources}
    shared.require(all(shared.Path(path).resolve() in registered for path in essential),
                   'Current driver/deadline helpers must be independently pinned')
    return {'run_name': deadline.CONTROL, 'actor_path': deadline.CONTROL_ACTOR,
            'case_id': 'O01', 'condition': 'A', 'worker_count': 2,
            'model': 'gpt-6.1-sol', 'effort': 'medium', 'trajectory_seconds': 1200,
            'reviews': reviews, 'source_entities': sources,
            'shared_control_freeze': shared.entity(shared.FREEZE),
            'task': TASK + (shared.CASE / 'public/request.md').read_text(),
            'actual_native_control_qualified': False, 'comparison_admitted': False,
            'superiority_proven': False}


def freeze():
    value = payload(); shared.atomic_json(FREEZE, value, exclusive=True); return value


def checked():
    value = json.loads(FREEZE.read_bytes())
    shared.require(shared.runtime.encoded(value) == shared.runtime.encoded(payload()),
                   'Original native-control source/task/policy freeze changed')
    return value


def prepare(coordinator_id):
    shared.require(isinstance(coordinator_id, str) and re.fullmatch('[A-Za-z0-9_-]{1,100}', coordinator_id),
                   'Original coordinator identity required')
    value = checked()
    folder = ROOT / 'runtime' / value['run_name']
    output = BASE / 'fresh-optional-deadline-control-preparation-v1.json'
    intent = BASE / 'fresh-optional-deadline-control-allocation-intent-v1.json'
    shared.require(not folder.exists() and not output.exists(), 'No restarted native control')
    shared.atomic_json(intent, {'coordinator_id': coordinator_id, 'started_at': time.time(),
                       'model_actors_allocated': 0, 'driver_entity': shared.entity(__file__)}, exclusive=True)
    owned = []
    def own(created):
        shared.require(shared.Path(created).resolve() == folder.resolve(), 'Exact owned control folder required')
        owned.append(folder)
    try:
        metadata = json.loads((shared.CASE / 'metadata.json').read_bytes())
        created = shared.runtime.create(folder, shared.CASE / 'repo', 'O01', 'A', value['task'],
                                        metadata['editable_paths'], record_ownership=own)
        shared.broker.register(folder, 'root', created['root_capability'])
        request = shared.dispatch.create(folder, value['actor_path'], coordinator_id, created['root_capability'])
        state = shared.runtime.load(folder)
        result = {'folder': str(folder), 'actor_path': value['actor_path'], 'coordinator_id': coordinator_id,
                  'root_dispatch': request, 'original_started_at': state['started_at'], 'deadline': state['deadline'],
                  'observer_argv': ['python3', str(shared.Path(shared.observer.__file__).resolve()),
                                    folder.name, value['actor_path'], coordinator_id],
                  'model_actors_allocated': 0, 'comparison_admitted': False, 'superiority_proven': False}
        shared.atomic_json(output, result, exclusive=True); return result
    except BaseException as error:
        failure = {'first_error': {'type': type(error).__name__, 'message': str(error)},
                   'runtime_ownership_observed': bool(owned), 'model_actors_allocated': 0}
        if owned:
            try:
                shared.runtime.failure(folder, error)
            except BaseException as preservation:
                failure['preservation_error'] = {'type': type(preservation).__name__, 'message': str(preservation)}
            try:
                failure['owned_cleanup'] = shared.runtime.cleanup(folder)
            except BaseException as cleanup:
                failure['cleanup_error'] = {'type': type(cleanup).__name__, 'message': str(cleanup)}
        try:
            shared.atomic_json(output, failure, exclusive=True)
        except BaseException as report:
            print(json.dumps({'original_failure': failure, 'report_error': str(report)}))
        raise
