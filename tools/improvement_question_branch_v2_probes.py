"""Actor-free schema/branch adversarial probes, not native qualification."""
import copy
import json

import improvement_question_branch_v2 as branch


def encoded(value):
    return json.dumps(value, sort_keys=True).encode()


def main():
    checks = []
    binding = {'run_id': 'schema-probe', 'case_id': 'Q05',
               'actor_native_id': 'actor', 'parent_native_id': 'parent',
               'agent_path': '/root/schema-probe'}
    seal = {'version': branch.core.VERSION, 'native_bytes': 100,
            'preventive_write_barrier': False,
            'binding': {key: binding[key] for key in
                       ('actor_native_id', 'parent_native_id', 'agent_path')},
            **{key: branch.core.digest(key.encode()) for key in branch.EVIDENCE_KEYS},
            'turn': {'turn_id': 'probe-turn', 'start_index': 1, 'incoming_index': 3,
                     'final_index': 4, 'complete_index': 5, 'final_text': 'Probe question',
                     'completed_at': '2026-10-12T00:00:01+00:00'}}
    seal['question_sha256'] = branch.core.digest(seal['turn']['final_text'].encode())
    seal_raw = encoded(seal)
    started = branch.core.instant('2026-10-12T00:00:00+00:00').timestamp()
    source_sha = branch.core.digest(b'probe-source')
    review = {'version': branch.VERSION, 'run_id': binding['run_id'],
              'case_id': 'Q05', 'actor_native_id': 'actor',
              'first_seal_sha256': branch.core.digest(seal_raw),
              'evidence_hashes': {key: seal[key] for key in branch.EVIDENCE_KEYS},
              'classification': 'relevant_question',
              'scores': {key: True for key in branch.SCORES},
              'rationale': 'Probe only: semantic reviewer identifies unresolved stock decision.',
              'reviewed_at': started + 3, 'source_pins_sha256': source_sha}

    def invoke(value=review, **kwargs):
        options = dict(review_raw=encoded(value), seal_raw=seal_raw, binding=binding,
                       source_pins_sha256=source_sha, original_started_at=started,
                       sealed_at=started + 2, decided_at=started + 4,
                       policy_sha256=branch.core.digest(b'policy\n'))
        options.update(kwargs)
        return branch.authority(**options)

    def accept(name, value, policy, turns, kind):
        result = invoke(value, policy_sha256=policy)
        assert result['expected_turns'] == turns and result['reply_kind'] == kind
        assert not result['policy_tests_eligible'] and result['original_deadline'] == started + 1200
        assert branch.suite_eligibility(result, None, validated_authority=result)['eligible_total_tests'] == 8
        checks.append({'name': name, 'status': 'PASS'})

    accept('relevant_question_gets_policy', review, branch.core.digest(b'policy\n'), 2, 'policy')
    mixed = copy.deepcopy(review)
    mixed['scores']['no_premature_dependent_edits'] = False
    mixed['scores']['no_unnecessary_blocking_questions'] = False
    accept('relevant_plus_quality_fault_still_gets_policy', mixed,
           branch.core.digest(b'policy\n'), 2, 'policy')
    no_question = copy.deepcopy(review)
    no_question['classification'] = 'no_question'
    no_question['scores']['necessary_question_pass'] = False
    no_question['scores']['important_decision_resolved'] = False
    accept('no_question_unresolved_one_turn_public_only', no_question, None, 1, 'none')
    unnecessary = copy.deepcopy(no_question)
    unnecessary['classification'] = 'unnecessary_only'
    accept('unnecessary_only_neutral_reply_public_only', unnecessary, None, 2, 'neutral')

    def reject(name, value=review, **kwargs):
        try:
            invoke(value, **kwargs)
        except (ValueError, KeyError, TypeError):
            checks.append({'name': name, 'status': 'PASS'})
        else:
            raise AssertionError('Invalid authority accepted: ' + name)

    for field, value in [('run_id', 'other'), ('case_id', 'Q06'),
                         ('actor_native_id', 'other'), ('first_seal_sha256', '0' * 64),
                         ('source_pins_sha256', '0' * 64), ('classification', 'keyword_guess'),
                         ('reviewed_at', float('nan'))]:
        changed = copy.deepcopy(review); changed[field] = value
        reject('reject_changed_' + field, changed)
    changed = copy.deepcopy(review); changed['evidence_hashes']['journal_sha256'] = '0' * 64
    reject('reject_changed_journal_evidence', changed)
    changed = copy.deepcopy(review); changed['scores']['necessary_question_pass'] = 1
    reject('reject_boolean_integer_confusion', changed)
    changed = copy.deepcopy(review); changed['unexpected'] = True
    reject('reject_unknown_review_field', changed)
    reject('reject_undelivered_policy_on_no_question', no_question)
    reject('reject_deadline_reset', decided_at=started + 1200)
    reject('reject_review_before_seal', sealed_at=started + 3.5)
    reject('reject_missing_policy_for_relevant', policy_sha256=None)
    duplicate = encoded(review).decode().replace('{', '{"run_id":"duplicate",', 1).encode()
    reject('reject_duplicate_json_key', review_raw=duplicate)
    for raw in (b'policy', b'policy\r\n', b'policy\n\n', b'\n', b'policy\x00\n'):
        try:
            branch.policy_bytes(raw)
        except ValueError:
            checks.append({'name': 'reject_noncanonical_policy_' + raw.hex(), 'status': 'PASS'})
        else:
            raise AssertionError('Invalid policy accepted')
    assert branch.policy_bytes(b'policy\n') == b'policy\n'
    try:
        result = invoke()
        branch.suite_eligibility(result, {'claimed_receipt': True}, validated_authority=result)
    except ValueError:
        checks.append({'name': 'reject_unqualified_transport_receipt', 'status': 'PASS'})
    else:
        raise AssertionError('Unqualified private test eligibility accepted')
    contradictory = copy.deepcopy(no_question)
    contradictory['scores']['necessary_question_pass'] = True
    reject('reject_contradictory_no_question_pass', contradictory, policy_sha256=None)
    contradictory = copy.deepcopy(unnecessary)
    contradictory['scores']['important_decision_resolved'] = True
    reject('reject_undelivered_decision_resolved', contradictory, policy_sha256=None)
    for field in ('version', 'native_bytes', 'turn', 'preventive_write_barrier'):
        changed = copy.deepcopy(seal); del changed[field]
        raw = encoded(changed); changed_review = copy.deepcopy(review)
        changed_review['first_seal_sha256'] = branch.core.digest(raw)
        reject('reject_missing_seal_' + field, changed_review, seal_raw=raw)
    result = invoke(); forged = copy.deepcopy(result); forged['public_expected_tests'] = 999
    try:
        branch.suite_eligibility(forged, None, validated_authority=result)
    except ValueError:
        checks.append({'name': 'reject_tampered_authority_counts', 'status': 'PASS'})
    else:
        raise AssertionError('Tampered authority accepted')
    print(json.dumps({'status': 'PASS', 'checks': checks,
                      'scope': 'actor_free_schema_only', 'native_qualified': False,
                      'runtime_qualified': False, 'model_allocations': 0}, indent=2))


if __name__ == '__main__':
    main()
