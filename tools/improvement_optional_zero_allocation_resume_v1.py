"""Additive, once-only preparation recovery; never repeat an allocated actor.

The old comparison and failure files stay immutable. This amendment explicitly
changes the first actual runtime budget and reports the entire earlier episode.
"""
import hashlib
import json
from pathlib import Path
import shutil
import time

import improvement_optional_comparison_driver_v4 as d

ROOT, BASE = d.ROOT, d.BASE
require = d.require
COORDINATOR = '01a122a7-1f52-7810-8588-f0a7a8732fa1'
PROOF = BASE / 'C20-zero-allocation-original-preparation-failure-proof-v1.json'
SPEC = ROOT / 'docs/zero-allocation-preparation-resume-amendment-v1.md'
REVIEW = BASE / 'C20-zero-allocation-preparation-resume-review-v1.json'
FREEZE = BASE / 'C20-zero-allocation-preparation-resume-freeze-v1.json'
INTENT = BASE / 'optional-development-v4-O02-C0-1-resume-allocation-intent-v1.json'
PREPARATION = BASE / 'optional-development-v4-O02-C0-1-resume-preparation-v1.json'
ACCOUNTING = BASE / 'optional-development-v4-O02-C0-1-all-preparation-attempts-observation-v1.json'
SOURCE = Path(__file__).resolve()
INITIAL_CALL = 'call_bfe5c7df2f924557b827481fe6027832'
TERMINAL_POLL = 'call_8501680d577e499799bd81ede076dcad'


def exact_row(row):
    d.inputs.row_valid(row)
    require(d.runtime.encoded(row) == d.runtime.encoded(d.inputs.sequence()[4]),
            'Only the exact original zero-allocation O02/C0 row can resume')


def one_result(payload):
    values = []
    require(isinstance(payload.get('output'), list), 'Original native output blocks required')
    for block in payload['output']:
        require(isinstance(block, dict) and block.get('type') == 'input_text'
                and isinstance(block.get('text'), str), 'Original native text block required')
        try:
            value = json.loads(block['text'])
        except ValueError:
            continue
        if isinstance(value, dict):
            values.append(value)
    require(len(values) == 1, 'One original terminal command result required')
    return values[0]


def failure_values(row, intent, failure, proof):
    exact_row(row)
    require(proof['row'] == row and proof['coordinator_id'] == COORDINATOR,
            'Original row and coordinator identity required')
    require(intent['row'] == row and intent['coordinator_id'] == COORDINATOR,
            'Original allocation intent identity required')
    require(type(intent.get('model_actors_allocated')) is int
            and intent['model_actors_allocated'] == 0
            and type(failure.get('model_actors_allocated')) is int
            and failure['model_actors_allocated'] == 0,
            'Genuine zero actor counts required')
    require(failure['row'] == row and failure['status'] == 'preparation_failed'
            and failure['runtime_ownership_observed'] is False
            and failure['first_error'] == {'type': 'ValueError',
                                          'message': 'Insufficient allocation disk'},
            'Only the original pre-mkdir disk failure can resume')
    require(type(intent['intent_started_at']) in (int, float)
            and intent['intent_started_at'] > 0, 'Original episode start required')


def original_failure():
    proof = json.loads(PROOF.read_bytes())
    row = proof['row']; exact_row(row)
    folder, failed, original_intent = d.paths(row)
    d.control.reviewed_entity(failed, proof['original_failure_entity'])
    d.control.reviewed_entity(original_intent, proof['original_intent_entity'])
    d.control.reviewed_entity(d.FREEZE, proof['original_comparison_freeze_entity'])
    intent, failure = json.loads(original_intent.read_bytes()), json.loads(failed.read_bytes())
    failure_values(row, intent, failure, proof)
    require(intent['driver_entity'] == d.control.entity(d.__file__), 'Original driver changed')
    prefix = ROOT / proof['coordinator_prefix']
    d.control.reviewed_entity(prefix, proof['coordinator_prefix_entity'])
    source = Path(proof['coordinator_source'])
    require(source == Path('/Users/junhyounglee/.codex/sessions/2026/10/10/'
                           'rollout-2026-10-10T06-52-20-' + COORDINATOR + '.jsonl')
            and source.is_file() and not source.is_symlink(), 'Actual original parent required')
    raw = prefix.read_bytes()
    with source.open('rb') as stream:
        require(hashlib.sha256(stream.read(len(raw))).hexdigest()
                == proof['coordinator_prefix_entity']['sha256'],
                'Saved original native prefix differs from actual parent')
    require(raw.endswith(b'\n') and json.loads(raw.splitlines()[0])['payload']['id'] == COORDINATOR,
            'Complete authenticated original native prefix required')
    core = d.normal_close.original.audit.inventory.core
    events = core.parse(raw)
    ordered = []
    expected = ((INITIAL_CALL, 'custom_tool_call', 'initial_failed_tool_call'),
                (INITIAL_CALL, 'custom_tool_call_output', 'initial_tool_result'),
                (TERMINAL_POLL, 'custom_tool_call', 'terminal_same_handle_poll'),
                (TERMINAL_POLL, 'custom_tool_call_output', 'terminal_tool_result'))
    for call_id, kind, key in expected:
        matches = [(i, e['payload']) for i, e in enumerate(events)
                   if e['payload'].get('call_id') == call_id
                   and e['payload'].get('type') == kind]
        require(len(matches) == 1 and matches[0][1] == proof[key],
                'Original failed native call/result identity changed')
        ordered.append(matches[0][0])
    require(ordered == sorted(ordered) and len(set(ordered)) == 4,
            'Original same-handle ordering required')
    initial = one_result(proof['initial_tool_result'])
    terminal = one_result(proof['terminal_tool_result'])
    require(type(initial.get('session_id')) is int and initial['session_id'] == 88092
            and 'exit_code' not in initial, 'Original live command handle required')
    require('session_id:88092' in proof['terminal_same_handle_poll']['input']
            and type(terminal.get('exit_code')) is int and terminal['exit_code'] == 1
            and 'session_id' not in terminal,
            'Genuine original same-handle terminal failure required')
    require('line 293, in create' in terminal['output']
            and terminal['output'].endswith('ValueError: Insufficient allocation disk\n'),
            'Original pre-ownership failure receipt required')
    return proof, intent, failure


def review_payload():
    d.admission()
    proof, intent, failure = original_failure()
    review = json.loads(REVIEW.read_bytes())
    require(review.get('verdict') == 'pass' and review.get('issues') == [],
            'Independent additive amendment review required')
    for category in ('source_entities', 'evidence_entities'):
        require(isinstance(review.get(category), dict) and bool(review[category]),
                'Typed amendment pins required')
        for path, pin in review[category].items():
            d.control.reviewed_entity(ROOT / path, pin)
    essential = {str(p.relative_to(ROOT)) for p in (SOURCE, SPEC, PROOF)}
    require(essential <= set(review['source_entities']), 'Amendment source closure incomplete')
    return {'row': proof['row'], 'coordinator_id': COORDINATOR,
            'sources': review['source_entities'], 'evidence': review['evidence_entities'],
            'review_entity': d.control.entity(REVIEW),
            'original_comparison_freeze_entity': d.control.entity(d.FREEZE),
            'first_episode_intent_started_at': intent['intent_started_at'],
            'original_failure_entity': proof['original_failure_entity'],
            'model': 'gpt-6.1-sol', 'effort': 'medium', 'model_retries': 0,
            'maximum_new_preparation_attempts': 1,
            'first_actual_runtime_budget_seconds': 1200,
            'original_runtime_clock_continuity': False,
            'earlier_runtime_local_start_unavailable': True,
            'all_preparation_failure_wait_and_repair_time_must_be_reported': True,
            'native_qualified': False, 'comparison_eligible': False,
            'superiority_proven': False}


def freeze():
    value = review_payload()
    d.control.atomic_json(FREEZE, value, exclusive=True)
    return value


def admission():
    require(FREEZE.is_file() and not FREEZE.is_symlink(), 'Additive freeze required')
    value = json.loads(FREEZE.read_bytes())
    require(d.runtime.encoded(value) == d.runtime.encoded(review_payload()),
            'Additive amendment source, evidence or policy changed')
    return value


def no_prior_allocation(row, proof):
    folder, _, _ = d.paths(row)
    require(not folder.exists() and not folder.is_symlink(), 'First-ever runtime folder required')
    require(not any(p.exists() or p.is_symlink() for p in (INTENT, PREPARATION, ACCOUNTING)),
            'Only one additive preparation attempt is allowed')
    core = d.normal_close.original.audit.inventory.core
    source = Path(proof['coordinator_source'])
    events = core.parse(source.read_bytes())
    task_name = row['actor_path'].rsplit('/', 1)[1]
    api_calls = []
    for e in events:
        p = e['payload']
        if p.get('type') != 'function_call':
            continue
        if core.route(p, 'collaboration', 'spawn_agent'):
            arguments = json.loads(p['arguments'])
            require(arguments.get('task_name') != task_name, 'An actual actor can never be repeated')
        if core.route(p, 'collaboration', 'list_agents') and json.loads(p['arguments']) == {}:
            api_calls.append(p)
    require(bool(api_calls), 'Genuine unfiltered parent API required')
    matches = [e['payload'] for e in events
               if e['payload'].get('type') == 'function_call_output'
               and e['payload'].get('call_id') == api_calls[-1]['call_id']]
    require(len(matches) == 1, 'Latest genuine API result required')
    agents = json.loads(matches[0]['output'])['agents']
    require(isinstance(agents, list) and bool(agents), 'Actual parent agent inventory required')
    require(all(isinstance(a, dict) and isinstance(a.get('agent_name'), str)
                and a['agent_name'] != row['actor_path']
                and not a['agent_name'].startswith(row['actor_path'] + '/') for a in agents),
            'No original actor or descendant may exist')
    require(shutil.disk_usage(folder.parent).free >= 10 * 1024**3,
            'Ten GiB reserve required for this once-only amendment')


def prepare(row, coordinator_id):
    exact_row(row)
    require(coordinator_id == COORDINATOR, 'Original parent identity required')
    amendment = admission()
    d.previous_reviews(row)
    proof, old_intent, original_failure_record = original_failure()
    no_prior_allocation(row, proof)
    folder, _, _ = d.paths(row)
    case = d.inputs.case_directory(row)
    metadata = json.loads((case / 'metadata.json').read_bytes())
    task = d.inputs.public_task(row)
    d.control.atomic_json(INTENT, {'row': row, 'coordinator_id': coordinator_id,
                          'resume_intent_started_at': time.time(),
                          'first_episode_intent_started_at': old_intent['intent_started_at'],
                          'original_failed_attempt_preserved': proof['original_failure_entity'],
                          'amendment_entity': d.control.entity(FREEZE),
                          'model_actors_allocated': 0}, exclusive=True)
    ownership = []

    def own(created):
        require(Path(created).resolve() == folder.resolve(), 'Ownership callback path changed')
        ownership.append(folder)

    try:
        with d.registry_extension.creation_hook(), d.inputs.skill_export(row, folder):
            created = d.runtime.create(folder, case / 'repo', row['case_id'], row['condition'],
                                       task, metadata['editable_paths'], record_ownership=own)
        cap = created['root_capability']
        d.broker.register(folder, 'root', cap)
        dispatched = d.dispatch.create(folder, row['actor_path'], coordinator_id, cap)
        state = d.runtime.load(folder)
        require(state['deadline'] == state['started_at'] + 1200, 'Amended first runtime budget changed')
        value = {'row': row, 'folder': str(folder), 'actor_path': row['actor_path'],
                 'coordinator_id': coordinator_id, 'root_dispatch': dispatched,
                 'observer_argv': ['python3', str(Path(d.observer.__file__).resolve()),
                                   folder.name, row['actor_path'], coordinator_id],
                 'original_started_at': state['started_at'], 'deadline': state['deadline'],
                 'first_actual_runtime_started_at': state['started_at'],
                 'first_episode_intent_started_at': old_intent['intent_started_at'],
                 'earlier_preallocation_wait_and_repair_seconds':
                     state['started_at'] - old_intent['intent_started_at'],
                 'original_runtime_clock_continuity': False,
                 'earlier_runtime_local_start_unavailable': True,
                 'amendment_entity': d.control.entity(FREEZE),
                 'model': 'gpt-6.1-sol', 'effort': 'medium', 'model_actors_allocated': 0,
                 'native_qualified': False, 'comparison_eligible': False,
                 'superiority_proven': False}
        d.control.atomic_json(PREPARATION, value, exclusive=True)
        return value
    except BaseException as error:
        failure = {'row': row, 'status': 'resume_preparation_failed',
                   'first_error': {'type': type(error).__name__, 'message': str(error)},
                   'original_failed_attempt_preserved': proof['original_failure_entity'],
                   'first_episode_intent_started_at': old_intent['intent_started_at'],
                   'runtime_ownership_observed': bool(ownership), 'model_actors_allocated': 0,
                   'finished_at': time.time(), 'native_qualified': False,
                   'comparison_eligible': False, 'superiority_proven': False}
        if ownership:
            try:
                d.runtime.failure(folder, error)
            except BaseException as original:
                failure['preservation_error'] = {'type': type(original).__name__, 'message': str(original)}
            try:
                failure['owned_cleanup'] = d.runtime.cleanup(folder)
            except BaseException as original:
                failure['cleanup_error'] = {'type': type(original).__name__, 'message': str(original)}
        d.control.atomic_json(PREPARATION, failure, exclusive=True)
        raise


def account_normal_close():
    """Add observation after original close; never rewrite its local-clock result."""
    amendment = admission()
    prepared = json.loads(PREPARATION.read_bytes())
    row = amendment['row']; exact_row(row)
    require(prepared['row'] == row and prepared['amendment_entity'] == d.control.entity(FREEZE),
            'Exact first actual preparation required')
    folder, _, _ = d.paths(row)
    outcome_path = folder / 'native-close/outcome.json'
    outcome = json.loads(outcome_path.read_bytes())
    require(outcome['owned_cleanup_verified'] is True
            and outcome['original_started_at'] == prepared['first_actual_runtime_started_at'],
            'Closed first actual runtime and owned cleanup required')
    start = amendment['first_episode_intent_started_at']
    wait = prepared['first_actual_runtime_started_at'] - start
    whole = outcome['finished_at'] - start
    require(wait >= 0 and whole >= outcome['whole_observed_seconds']
            and abs(whole - wait - outcome['whole_observed_seconds']) < 0.000001,
            'All earlier preparation waiting and repair must remain counted')
    value = {'row': row, 'first_episode_intent_started_at': start,
             'earlier_preallocation_failure_wait_and_repair_seconds': wait,
             'first_actual_runtime_whole_seconds': outcome['whole_observed_seconds'],
             'all_preparation_attempts_whole_seconds': whole,
             'first_actual_runtime_budget_seconds': 1200,
             'original_runtime_clock_continuity': False,
             'earlier_runtime_local_start_unavailable': True,
             'original_failure_preserved': True,
             'outcome_entity': d.control.entity(outcome_path),
             'preparation_entity': d.control.entity(PREPARATION),
             'amendment_entity': d.control.entity(FREEZE),
             'usage': outcome['usage'],
             'cost_scope': 'Observed first actual product members only; zero actors in the '
                           'authenticated rejected preparation. External research cost and '
                           'backend billing are not thereby zero or fully known.',
             'paired_efficiency_claim_from_amended_row_permitted': False,
             'comparison_eligible': False, 'superiority_proven': False}
    d.control.atomic_json(ACCOUNTING, value, exclusive=True)
    return value


if __name__ == '__main__':
    print(json.dumps({'status': 'unadmitted_additive_preparation_amendment',
                      'model_actors_allocated': 0, 'superiority_proven': False}))
