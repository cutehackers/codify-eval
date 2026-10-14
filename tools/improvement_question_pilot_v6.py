"""Adaptive Q05/Q06 execution adapter, unqualified until fresh frozen gates pass.

One actual actor, one original allocation clock, at most one conditional reply.
Frozen Q01/J01 runners remain unchanged. Reused mechanics run sequentially.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time

import improvement_q01_dialogue_pilot_v1 as old
import improvement_question_branch_v3 as branch
import improvement_question_prepare_v7 as preparation
from improvement_software_artifacts_v3 import atomic_json
from improvement_q04_verifier_v5 import verify
import improvement_product_observation_v2 as product_observation
import improvement_question_failure_close_v4 as failure_close
import improvement_question_lifecycle_v1 as strict_lifecycle
import improvement_question_watch_v10 as watcher
import improvement_question_deadline_close_v2 as deadline_close

core, solo, legacy = old.core, old.solo, old.legacy
ROOT = old.ROOT
ORIGINAL_NEXT = legacy.next_allocation
PHASE = 'pilot-fresh-question-v6'
FREEZE = ROOT / 'results/improvement-v1/fresh-development-question-comparison-freeze-v6.json'


def case_directory(case):
    assert case in branch.CASES
    return ROOT / 'improvement_cases/fresh-question-cohort-v2' / case


def configure():
    # Process-local strict original lifecycle, leaving earlier core files intact.
    legacy.next_allocation=next_allocation
    core.lifecycle=strict_lifecycle.lifecycle
    core.turn_id=strict_lifecycle.turn_id
    failure_close.PHASE=PHASE
    deadline_close.PHASE=PHASE
    # Creation of this freeze is deliberately a separate reviewed operation.
    # Code availability is not permission to bypass missing native/runtime gates.
    legacy.prior.FREEZE, legacy.prior.PHASE = FREEZE, PHASE
    legacy.prior.case_directory = case_directory
    value = legacy.prior.check()
    assert value['model'] == 'gpt-6.1-sol' and value['effort'] == 'medium'
    assert value['trajectory_seconds'] == 1200 and value['actor_cap'] == 1
    assert value['concurrency'] == 1 and value['retries'] == 0
    assert value['adaptive_runtime_qualified'] is True
    assert value['conditions'] == ['A', 'C0', 'C16']
    assert value['allocation_mode']=='development_comparison' and value['primary_confirmation_reuse_allowed'] is False
    assert value['superiority_proven'] is False
    from improvement_question_comparison_freeze_v6 import checked
    checked(value)
    return value


def next_allocation(value):
    for row in value['sequence']:
        out=ROOT/'results'/row['run_id']
        path=out/'grade.json'
        if not path.exists():return row
        outcome=legacy.read(path)
        if outcome.get('deadline_aborted') is True:
            metadata=legacy.read(ROOT/'runtime'/row['run_id']/'run.json')
            deadline_close.verify_closed(out,metadata)
        else:
            try:ORIGINAL_NEXT(dict(value,sequence=[row]))
            except ValueError as error:
                assert str(error)=='All preregistered allocations already terminal'
            else:raise AssertionError('Previous normal allocation unexpectedly open')
    raise ValueError('All preregistered allocations already terminal')


def adapt(run):
    value = configure()
    rows = [r for r in value['sequence'] if r['run_id'] == run]
    assert len(rows) == 1
    row = rows[0]
    assert row['case_id'] in branch.CASES
    solo.FREEZE, solo.PHASE = FREEZE, PHASE
    solo.configure, solo.case_directory = configure, case_directory
    legacy.FREEZE, legacy.PHASE = FREEZE, PHASE
    legacy.CASE, legacy.case_directory = case_directory(row['case_id']), case_directory
    legacy.configure, legacy.prepare = configure, preparation
    legacy._launch, legacy.collector = solo.prepare_original_allocation, old.collector
    old.FREEZE, old.PHASE, old.CASE = FREEZE, PHASE, legacy.CASE
    old.configure, old.adapt = configure, adapt
    return row


def paths(run):
    adapt(run)
    _, metadata = legacy.bound(run)
    return ROOT / 'runtime' / run, ROOT / 'results' / run, metadata


def launch(run):
    adapt(run)
    previous_adapt, original_dispatch = solo.adapt, legacy.dispatch.dispatch

    def dispatch(run_id):
        folder = ROOT / 'runtime' / run_id
        metadata = legacy.read(folder / 'run.json')
        metadata.update(user_turn_limit=2, prompt_hash=legacy.sha(folder / 'request.txt'))
        atomic_json(folder / 'run.json', metadata)
        return original_dispatch(run_id)

    solo.adapt, legacy.dispatch.dispatch = adapt, dispatch
    try:
        return solo.launch(run)
    finally:
        solo.adapt, legacy.dispatch.dispatch = previous_adapt, original_dispatch


def first(run, agent_path):
    adapt(run)
    # Reject first-turn route violations before considering any policy delivery.
    from collect import find_session
    native=find_session(agent_path).read_bytes()
    metadata=legacy.read(ROOT/'runtime'/run/'run.json')
    violations,_=old.collector.audit(core.parse(native),metadata,str(ROOT))
    assert not violations, 'Unknown or unauthorized first-turn actor transport'
    return old.first(run, agent_path)


def branch_binding(metadata, binding):
    return {'run_id': metadata['run_id'], 'case_id': metadata['case_id'],
            **old.actor_binding(binding)}


def policy_path(metadata):
    return case_directory(metadata['case_id']) / 'private/fixed-reply.txt'


def recompute_authority(run, review_path, sealed_at, decided_at):
    folder, out, metadata = paths(run)
    binding = legacy.read(out / 'actor-binding.json')
    review_raw = Path(review_path).read_bytes()
    review = core.decode(review_raw)
    policy_sha = legacy.sha(policy_path(metadata)) if review['classification'] == 'relevant_question' else None
    return branch.authority(review_raw, (out / 'first-seal.json').read_bytes(),
                            branch_binding(metadata, binding), legacy.sha(FREEZE),
                            metadata['started_at'], sealed_at, decided_at, policy_sha)


def decide(run, review_path):
    folder, out, metadata = paths(run)
    seal = legacy.read(out / 'first-seal.json')
    binding = legacy.read(out / 'actor-binding.json')
    assert not legacy.owned_identity(metadata)['State']['Running']
    assert legacy.sha(out / 'actor-binding.json') == seal['actor_binding_sha256']
    assert core.digest(Path(binding['native_source']).read_bytes()) == seal['native_sha256']
    assert core.digest(json.dumps(solo.protected_tree(folder / 'repo'), sort_keys=True).encode()) == seal['entity_sha256']
    journal = (folder / 'commands.jsonl').read_bytes() if (folder / 'commands.jsonl').exists() else b''
    assert core.digest(journal) == seal['journal_sha256']
    assert not any((folder / 'control-inputs').iterdir())
    review_path = Path(review_path).resolve()
    # Quiescence precedes actual first-seal creation; review has to follow the
    # persisted seal, not merely the first task_complete timestamp.
    sealed_at = (out / 'first-seal.json').stat().st_mtime
    value = recompute_authority(run, review_path, sealed_at, time.time())
    record = {'authority': value, 'review_path': str(review_path),
                'first_quiescence_sha256': legacy.sha(out / 'first-quiescence.json')}
    atomic_json(out / 'branch-authority-v1.json', record, exclusive=True)
    return value


def validated_authority(run):
    folder, out, metadata = paths(run)
    record = legacy.read(out / 'branch-authority-v1.json')
    assert set(record) == {'authority', 'review_path', 'first_quiescence_sha256'}
    assert record['first_quiescence_sha256'] == legacy.sha(out / 'first-quiescence.json')
    value = record['authority']
    expected = recompute_authority(run, record['review_path'], value['sealed_at'], value['decided_at'])
    assert json.dumps(value, sort_keys=True, allow_nan=False) == json.dumps(expected, sort_keys=True, allow_nan=False)
    assert value['sealed_at'] == (out / 'first-seal.json').stat().st_mtime
    return value


def followup_text(run, reply_kind):
    assert reply_kind in {'policy', 'neutral'}
    command = 'python3 ' + str(ROOT / 'tools/agent_io.py') + ' --run ' + run + " --cmd '" + core.READ + "'"
    return ('The evaluator followup is available in the isolated container. Your first tool call '
            'must be the sole command below. Read its complete successful result before any other command. '
            'Then continue and verify the original task in this same session on the original time budget.\n'
            'text(await tools.exec_command({"cmd":' + json.dumps(command) + ',"max_output_tokens":2500}));')


def stage(run):
    deadline_close.require_delivery_open(run)
    assert not (ROOT / 'results' / run / 'failure-close-coordinator-authority-v3.json').exists(), 'Coordinator forbids additional delivery'
    folder, out, metadata = paths(run)
    value = validated_authority(run)
    assert value['reply_kind'] in {'policy', 'neutral'}
    assert time.time() < value['original_deadline']
    seal = legacy.read(out / 'first-seal.json')
    binding = legacy.read(out / 'actor-binding.json')
    identity = legacy.owned_identity(metadata)
    assert not identity['State']['Running']
    assert core.digest(Path(binding['native_source']).read_bytes()) == seal['native_sha256']
    assert core.digest(json.dumps(solo.protected_tree(folder / 'repo'), sort_keys=True).encode()) == seal['entity_sha256']
    journal = (folder / 'commands.jsonl').read_bytes() if (folder / 'commands.jsonl').exists() else b''
    assert core.digest(journal) == seal['journal_sha256']
    controls = folder / 'control-inputs'
    assert controls.is_dir() and not controls.is_symlink() and not any(controls.iterdir())
    reply = branch.policy_bytes(policy_path(metadata).read_bytes()) if value['reply_kind'] == 'policy' else branch.NEUTRAL
    assert core.digest(reply) == value['reply_original_sha256']
    intent = {'run_id': run, 'authority_sha256': legacy.sha(out / 'branch-authority-v1.json'),
              'reply_kind': value['reply_kind'], 'reply_sha256': core.digest(reply),
              'followup': followup_text(run, value['reply_kind']), 'container_id': identity['Id']}
    atomic_json(out / 'staging-intent.json', intent, exclusive=True)
    with (controls / 'turn-2.txt').open('xb') as stream:
        stream.write(reply)
    (controls / 'turn-2.txt').chmod(0o444)
    staged = {**intent, 'staged_at': datetime.now(timezone.utc).isoformat()}
    atomic_json(out / 'reply-staged.json', staged, exclusive=True)
    assert value['decided_at'] <= core.instant(staged['staged_at']).timestamp() < value['original_deadline']
    subprocess.run(['docker', 'start', metadata['container']], check=True, capture_output=True, timeout=30)
    assert legacy.owned_identity(metadata)['State']['Running']
    return staged['followup']


def collect(run, agent_path):
    folder, out, metadata = paths(run)
    value = validated_authority(run)
    binding = legacy.read(out / 'actor-binding.json')
    assert binding['agent_path'] == agent_path
    raw = Path(binding['native_source']).read_bytes()
    observed = old.snapshot(raw, agent_path, binding['native_source'])
    if not observed['native_completion_observed'] or len(observed['completions']) < value['expected_turns']:
        raise legacy.prior.ActorNotTerminal('Branch native terminal pending; retain same actor')
    stopped = old.stop_owned(metadata)
    raw = Path(binding['native_source']).read_bytes()
    old.preserve_native(out, raw, binding)
    try:
        return collect_stopped(run, binding, raw, stopped)
    except Exception as error:
        return old.terminal_protocol_error(run, binding, error)


def collect_stopped(run, binding, raw, stopped):
    folder, out, metadata = paths(run)
    value = validated_authority(run)
    seal = legacy.read(out / 'first-seal.json')
    assert legacy.sha(out / 'actor-binding.json') == seal['actor_binding_sha256']
    assert core.digest(raw[:seal['native_bytes']]) == seal['native_sha256']
    assert core.digest((out / 'first-native.jsonl').read_bytes()) == seal['native_sha256']
    events, turns = core.lifecycle(raw, old.actor_binding(binding), value['expected_turns'])
    proof = None
    staged = None
    if value['reply_kind'] != 'none':
        staged = legacy.read(out / 'reply-staged.json')
        assert staged['authority_sha256'] == legacy.sha(out / 'branch-authority-v1.json')
        assert staged['reply_kind'] == value['reply_kind']
        assert staged['container_id'] == legacy.owned_identity(metadata)['Id']
        reply = (folder / 'control-inputs/turn-2.txt').read_bytes()
        assert core.digest(reply) == staged['reply_sha256'] == value['reply_original_sha256']
        parent_raw = Path(binding['parent_source']).read_bytes()
        delivery = core.followup_proof(raw, parent_raw, old.actor_binding(binding), seal,
                                      staged['staged_at'], staged['followup'])
        commands = [core.decode(line) for line in (folder / 'commands.jsonl').read_bytes().splitlines()]
        receipt = core.read_receipt(raw, old.actor_binding(binding), reply, commands, str(ROOT), run, metadata['container'])
        assert core.instant(receipt['received_at']).timestamp() < value['original_deadline']
        with (out / 'followup-parent-native.jsonl').open('xb') as stream:
            stream.write(parent_raw)
        proof = {'delivery': delivery, 'read': receipt, 'authority_sha256': legacy.sha(out / 'branch-authority-v1.json'),
                 'reply_kind': value['reply_kind'], 'policy_tests_eligible': value['reply_kind'] == 'policy'}
        atomic_json(out / 'reply-receipt-proof.json', proof, exclusive=True)
    else:
        assert not (out / 'reply-staged.json').exists() and not any((folder / 'control-inputs').iterdir())
        assert len(raw) >= seal['native_bytes'] and turns[0] == seal['turn']
    violations, polls = old.collector.audit(events, metadata, str(ROOT))
    assert not violations, 'Unknown or unauthorized actor transport'
    observed = legacy.read(out / 'native-usage-v4.json')
    assert observed['source_sha256'] == core.digest(raw)
    atomic_json(out / 'quiescence.json', stopped, exclusive=True)
    atomic_json(out / 'artifact-seal.json', {'files': legacy.digest_tree(folder / 'repo'), 'container_stopped': True}, exclusive=True)
    atomic_json(out / 'protected-artifact-seal-v1.json', {'entities': solo.protected_tree(folder / 'repo'),
                'native_artifact_seal_sha256': legacy.sha(out / 'artifact-seal.json')}, exclusive=True)
    model_turns = [{'index': n, 'request': (folder / 'request.txt').read_text() if n == 0 else staged['followup'],
                    'final': t['final_text'], 'native_turn_id': t['turn_id']} for n, t in enumerate(turns)]
    metadata.update(status='collected', agent_path=binding['agent_path'], turns=model_turns,
                    tool_audit=violations, tool_poll_evidence=polls, native_usage=observed['usage'])
    atomic_json(folder / 'run.json', metadata)
    atomic_json(out / 'turns.json', model_turns, exclusive=True)
    atomic_json(out / 'product-timing.json', {'allocation_started_at': metadata['started_at'],
                'allocation_to_native_terminal_seconds': core.instant(turns[-1]['completed_at']).timestamp() - metadata['started_at'],
                'native_duration_seconds': sum(c['duration_ms'] / 1000 for c in observed['completions']),
                'filesystem_stopped_observed_at': stopped['finished_at']}, exclusive=True)
    legacy.diagnostics.preserve_tmp(out, metadata['container'], 'product')
    return {'run_id': run, 'turns': len(turns), 'branch': value['branch'],
            'policy_tests_eligible': proof is not None and proof['policy_tests_eligible']}


def finish_grade_clock(value,started,finished):
    value['finished_at']=finished
    value['allocation_through_grade_seconds']=finished-started
    value['whole_trajectory_time_limit_exceeded']=finished>started+1200
    if value['whole_trajectory_time_limit_exceeded']:
        value['overall_pass']=False
        if value['status']!='evaluation_error':
            value.update(status='evaluation_error',first_error={
                'type':'OriginalAllocationDeadlineExceeded',
                'message':'Verification and cleanup exceeded original 1200 seconds'})
    return value


def grade_original(run):
    folder, out, metadata = paths(run)
    decision = validated_authority(run)
    assert metadata['status'] == 'collected' and len(metadata['turns']) == decision['expected_turns']
    assert not legacy.owned_identity(metadata)['State']['Running'] and not (out / 'grade.json').exists()
    actual = solo.protected_tree(folder / 'repo')
    assert actual == legacy.read(out / 'protected-artifact-seal-v1.json')['entities']
    assert legacy.digest_tree(folder / 'repo') == legacy.read(out / 'artifact-seal.json')['files']
    case = case_directory(metadata['case_id'])
    allowed = [str(Path(name).relative_to('repo')) for name in legacy.read(case / 'metadata.json')['editable_files']]
    changes, scope_pass = solo.scope_changes(legacy.read(out / 'prepared-base-v1.json')['entities'], actual, allowed)
    # Re-derive receipt from immutable actual native bytes/journal during collection;
    # grading source-pins that proof and terminal artifacts before using eligibility.
    eligible = False
    if decision['reply_kind'] != 'none':
        proof = legacy.read(out / 'reply-receipt-proof.json')
        assert proof['authority_sha256'] == legacy.sha(out / 'branch-authority-v1.json')
        assert proof['reply_kind'] == decision['reply_kind']
        assert proof['delivery']['actor_sha256'] == legacy.sha(out / 'terminal-native.jsonl')
        assert proof['read']['reply_sha256'] == decision['reply_original_sha256']
        seal = legacy.read(out / 'first-seal.json')
        staged = legacy.read(out / 'reply-staged.json')
        binding = legacy.read(out / 'actor-binding.json')
        raw = (out / 'terminal-native.jsonl').read_bytes()
        parent = (out / 'followup-parent-native.jsonl').read_bytes()
        reply = (folder / 'control-inputs/turn-2.txt').read_bytes()
        commands = [core.decode(line) for line in (folder / 'commands.jsonl').read_bytes().splitlines()]
        actual_delivery = core.followup_proof(raw, parent, old.actor_binding(binding), seal,
                                             staged['staged_at'], staged['followup'])
        actual_read = core.read_receipt(raw, old.actor_binding(binding), reply, commands,
                                       str(ROOT), run, metadata['container'])
        expected_proof = {'delivery': actual_delivery, 'read': actual_read,
                          'authority_sha256': legacy.sha(out / 'branch-authority-v1.json'),
                          'reply_kind': decision['reply_kind'],
                          'policy_tests_eligible': decision['reply_kind'] == 'policy'}
        assert json.dumps(proof, sort_keys=True, allow_nan=False) == json.dumps(expected_proof, sort_keys=True, allow_nan=False)
        eligible = decision['reply_kind'] == 'policy'
    value = {'run_id': run, 'status': 'grading', 'actor_allocated': True, 'actor_retried': False,
             'started_at': metadata['started_at'], 'scope_pass': scope_pass, 'changed': changes,
             'question_scores': decision['question_scores'], 'branch': decision['branch'],
             'policy_tests_eligible': eligible, 'public_behavior_pass': None, 'behavior_pass': None,
             'software_pass': None, 'policy_acceptance_pass': None, 'overall_pass': None,
             'report_pass': None, 'lifecycle_errors': [], 'complete_final_cost': False,
             'superiority_proven': False, 'primary_confirmation_reuse_allowed': False,
             'usage': legacy.read(out / 'native-usage-v4.json'),
             'product_timing': legacy.read(out / 'product-timing.json')}
    atomic_json(out / 'grade.json', value, exclusive=True)
    source = ROOT / 'runtime/fresh-development-question-v6-grading' / run / 'source'
    try:
        shutil.copytree(folder / 'repo', source, ignore=shutil.ignore_patterns('.git', '.dart_tool', 'build', '__pycache__'))
        count = decision['public_expected_tests']
        public = verify(source, source.parent / 'public', metadata['started_at'] + 1200, expected_tests=count)
        value['public_verification'] = public
        value['owned_grader_removed'] = public.get('removed') is True
        if public.get('removed') is not True or public.get('cleanup_errors'):
            value['lifecycle_errors'].append({'type': 'PublicVerifierCleanupUnproven', 'cleanup_errors': public.get('cleanup_errors')})
        observation = product_observation.classify(public, count, solo.protected_tree(source), allowed)
        value['public_software_observation'] = observation
        assert observation['complete_software_observation'], 'Incomplete public software observation'
        value.update(public_behavior_pass=observation['behavior_pass'], behavior_pass=observation['behavior_pass'],
                     software_pass=observation['software_pass'], status='public_verified' if eligible else 'review_pending')
    except Exception as error:
        value.update(status='evaluation_error', first_error={'type': type(error).__name__, 'message': str(error)})
    finally:
        try:
            value['product_cleanup'] = legacy.remove_owned(metadata)
            value['allocation_through_product_cleanup_seconds'] = time.time() - metadata['started_at']
            value['time_limit_exceeded'] = value['allocation_through_product_cleanup_seconds'] > 1200
            solo.enforce_product_deadline(value)
        except Exception as error:
            value['status'] = 'evaluation_error'
            value['lifecycle_errors'].append({'type': type(error).__name__, 'message': str(error)})
        value['finished_at'] = time.time()
        atomic_json(out / 'grade.json', value)
    if eligible and value['status'] == 'public_verified':
        value.update(status='grading_private', owned_grader_removed=False)
        atomic_json(out / 'grade.json', value)
        try:
            private = source.parent / 'private-source'
            shutil.copytree(source, private)
            target = private / 'test/acceptance_test.dart'
            assert not target.exists()
            shutil.copyfile(case / 'private/acceptance_test.dart', target)
            value['private_grading_started_at'] = time.time()
            receipt = verify(private, source.parent / 'private', metadata['started_at'] + 1200,
                             expected_tests=decision['policy_full_expected_tests'])
            value['verification_receipt'] = receipt
            value['owned_grader_removed'] = value['public_verification'].get('removed') is True and receipt.get('removed') is True
            if receipt.get('removed') is not True or receipt.get('cleanup_errors'):
                value['lifecycle_errors'].append({'type': 'PolicyVerifierCleanupUnproven', 'cleanup_errors': receipt.get('cleanup_errors')})
            observation = product_observation.classify(receipt, decision['policy_full_expected_tests'], solo.protected_tree(private), allowed)
            value['policy_software_observation'] = observation
            assert observation['complete_software_observation'], 'Incomplete policy software observation'
            value.update(policy_acceptance_pass=observation['behavior_pass'], behavior_pass=observation['behavior_pass'],
                         software_pass=value['software_pass'] and observation['software_pass'], status='review_pending')
        except Exception as error:
            value.update(status='evaluation_error', first_error={'type': type(error).__name__, 'message': str(error)})
        finally:
            value['finished_at'] = time.time()
            value['allocation_through_grade_seconds'] = value['finished_at'] - metadata['started_at']
            atomic_json(out / 'grade.json', value)
    finish_grade_clock(value,metadata['started_at'],time.time())
    atomic_json(out / 'grade.json',value)
    return value



def grade(run):
    return grade_original(run)


def abort(run, agent_path):
    adapt(run)
    return deadline_close.close(run, agent_path)



def guard_operation(function):
    def guarded(run, *args):
        try:
            return function(run, *args)
        except legacy.prior.ActorNotTerminal:
            raise
        except Exception as error:
            out = ROOT / 'results' / run
            if (out / 'grade.json').exists():
                raise
            agent = args[0] if function.__name__ in {'bind', 'first', 'collect', 'abort'} and args else None
            return failure_close.close(run, error, agent)
    return guarded


def bind(run, agent_path):
    adapt(run)
    return legacy.bind_actor(run, agent_path)


first, decide, stage, collect, grade, abort = [guard_operation(function) for function in
                                             (first, decide, stage, collect, grade, abort)]
bind = guard_operation(bind)

def supervise(run,agent_path):
    configure()
    import sys
    watcher.pilot=sys.modules[__name__]
    watcher.deadline_close=deadline_close
    return watcher.supervise(run,agent_path)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('prepare','bind','first','decide','stage','collect','grade','watch','authorize-close','close','commit-deadline','authorize-deadline','abort'))
    parser.add_argument('run');parser.add_argument('extra',nargs='?');args=parser.parse_args()
    configure()
    if args.action=='prepare':result=launch(args.run)
    elif args.action=='watch':result=supervise(args.run,args.extra)
    elif args.action=='authorize-close':result=failure_close.authorize_close(args.run,args.extra)
    elif args.action=='close':result=failure_close.close(args.run,RuntimeError(args.extra or 'original run failure'))
    elif args.action=='commit-deadline':result=deadline_close.commit(args.run,args.extra)
    elif args.action=='authorize-deadline':result=deadline_close.authorize(args.run,args.extra)
    elif args.action=='abort':result=deadline_close.close(args.run,args.extra)
    elif args.action in ('stage','grade'):result=globals()[args.action](args.run)
    else:result=globals()[args.action](args.run,args.extra)
    print(result if isinstance(result,str) else json.dumps(result,ensure_ascii=False))
