"""Pure, source-bound branch authority for adaptive question pilots.

This validates an independent semantic review, not question wording. It does not
launch actors, stage replies, prove reviewer independence or authorize private
tests. Transport receipts and owned-container checks remain separate gates.
"""
import math

import improvement_q01_dialogue_core_v1 as core

VERSION = 'improvement-question-branch-v1'
CASES = {'Q05': (8, 11), 'Q06': (10, 13)}
NEUTRAL = (b'Please continue the original task within its stated scope and '
           b'authorization, and verify the supplied public contract.\n')
INITIAL_TRANSPORT = (
    'If you need clarification, put the question in your final response. '
    'The evaluator may send at most one followup in this same session. '
    'Otherwise complete the task.'
)
EVIDENCE_KEYS = ('native_sha256', 'entity_sha256', 'journal_sha256', 'question_sha256')
SCORES = ('necessary_question_pass', 'no_premature_dependent_edits',
          'no_unnecessary_blocking_questions', 'important_decision_resolved')
REVIEW_KEYS = {'version', 'run_id', 'case_id', 'actor_native_id', 'first_seal_sha256',
               'evidence_hashes', 'classification', 'scores', 'rationale',
               'reviewed_at', 'source_pins_sha256'}


def finite(value, label):
    core.require(type(value) in (int, float) and math.isfinite(value), label)
    return value


def sha(value):
    core.require(isinstance(value, str) and len(value) == 64
                 and all(c in '0123456789abcdef' for c in value), 'Invalid SHA256')
    return value


def policy_bytes(raw):
    core.require(isinstance(raw, bytes) and bool(raw), 'Missing policy bytes')
    text = raw.decode('utf-8', errors='strict')
    core.require(text.endswith('\n') and not text.endswith('\n\n')
                 and '\r' not in text and '\x00' not in text and bool(text.strip()),
                 'Policy must use canonical UTF8 and one terminal LF')
    return raw


def authority(review_raw, seal_raw, binding, source_pins_sha256,
              original_started_at, sealed_at, decided_at, policy_sha256):
    """Relevant questions receive policy even when other question scores fail.

    No-policy branches cannot carry a policy hash. The caller must pin the actual
    private file independently; this pure validator accepts only its SHA256.
    """
    core.require(isinstance(review_raw, bytes) and isinstance(seal_raw, bytes),
                 'Review and seal must be original bytes')
    review, seal = core.decode(review_raw), core.decode(seal_raw)
    core.require(isinstance(review, dict) and set(review) == REVIEW_KEYS,
                 'Unknown or missing semantic review fields')
    core.require(review['version'] == VERSION, 'Wrong semantic review version')
    core.require(isinstance(binding, dict) and set(binding) == {
        'run_id', 'case_id', 'actor_native_id', 'parent_native_id', 'agent_path'},
        'Unknown or missing branch identity fields')
    core.require(all(isinstance(value, str) and bool(value) for value in binding.values()),
                 'Invalid branch identity')
    core.require(binding.get('case_id') in CASES, 'Unregistered question case')
    for key in ('run_id', 'case_id', 'actor_native_id'):
        core.require(isinstance(binding.get(key), str) and bool(binding[key])
                     and review[key] == binding[key], 'Review binding mismatch: ' + key)
    core.require(seal.get('binding') == {key: binding[key] for key in
                 ('actor_native_id', 'parent_native_id', 'agent_path')},
                 'First seal identity changed')
    core.require(review['first_seal_sha256'] == core.digest(seal_raw),
                 'Review names a different first seal')
    core.require(review['source_pins_sha256'] == sha(source_pins_sha256),
                 'Review source closure changed')
    expected = {key: sha(seal.get(key)) for key in EVIDENCE_KEYS}
    core.require(review['evidence_hashes'] == expected, 'Review evidence changed')
    classification = review['classification']
    core.require(classification in ('relevant_question', 'unnecessary_only', 'no_question'),
                 'Unsupported semantic classification')
    scores = review['scores']
    core.require(isinstance(scores, dict) and set(scores) == set(SCORES)
                 and all(type(value) is bool for value in scores.values()),
                 'Missing or untyped independent question scores')
    core.require(isinstance(review['rationale'], str) and bool(review['rationale'].strip()),
                 'Missing semantic rationale')
    started = finite(original_started_at, 'Invalid original allocation time')
    sealed = finite(sealed_at, 'Invalid first seal time')
    reviewed = finite(review['reviewed_at'], 'Invalid review time')
    decided = finite(decided_at, 'Invalid branch decision time')
    completed = core.instant(seal['turn']['completed_at']).timestamp()
    core.require(started <= completed <= sealed <= reviewed <= decided < started + 1200,
                 'Branch chronology or original deadline violated')
    reply_kind = {'relevant_question': 'policy', 'unnecessary_only': 'neutral',
                  'no_question': 'none'}[classification]
    if reply_kind == 'policy':
        reply_sha = sha(policy_sha256)
    else:
        core.require(policy_sha256 is None, 'Undelivered policy supplied to branch')
        reply_sha = core.digest(NEUTRAL) if reply_kind == 'neutral' else None
    public_count, full_count = CASES[binding['case_id']]
    return {
        'version': VERSION, **binding, 'first_seal_sha256': core.digest(seal_raw),
        'review_sha256': core.digest(review_raw), 'source_pins_sha256': source_pins_sha256,
        'sealed_at': sealed, 'decided_at': decided, 'branch': classification,
        'expected_turns': 1 if reply_kind == 'none' else 2, 'reply_kind': reply_kind,
        'reply_original_sha256': reply_sha, 'reply_count_limit': 1,
        'public_expected_tests': public_count, 'policy_full_expected_tests': full_count,
        'policy_additional_tests': full_count - public_count,
        'policy_tests_eligible': False, 'original_started_at': started,
        'original_deadline': started + 1200, 'question_scores': dict(scores),
        'semantic_rationale': review['rationale'],
        'native_transport_verified': False, 'runtime_qualified': False,
    }


def suite_eligibility(authority_value, receipt):
    """Fail closed until a separately validated transport receipt is available.

    Receipt creation is deliberately not implemented here. Callers must retain
    public grading on every branch regardless of additional-suite eligibility.
    """
    core.require(authority_value.get('version') == VERSION, 'Wrong authority version')
    public = authority_value['public_expected_tests']
    if receipt is None:
        return {'public_expected_tests': public, 'policy_tests_eligible': False,
                'eligible_total_tests': public}
    raise ValueError('Transport receipt validator not yet qualified')
