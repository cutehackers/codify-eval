"""Pure prospective question decision validator for B03/B04.

The coordinator must authenticate all supplied bindings, reviewer provenance,
seal evidence and the opaque preallocated assignment before calling this module.
Matching dictionaries do not prove independence or authorize transport/cleanup.
No private reply body, branch ID, oracle, test count or actor is accessed here.
"""
import math
import re

import improvement_q01_dialogue_core_v1 as core

require = core.require
NEUTRAL = (b'Please continue the original task within its stated scope and '
           b'authorization, and verify the supplied public contract.\n')
SCORES = {'necessary_question_pass', 'no_premature_dependent_edits',
          'no_unnecessary_blocking_questions'}
REVIEW_KEYS = {'schema_version', 'run_id', 'case_id', 'root_native_uuid',
               'first_seal_entity', 'evidence_entities', 'classification',
               'scores', 'rationale', 'reviewer_identity', 'source_pin_digest',
               'reviewed_at'}
BINDING_KEYS = {'run_id', 'case_id', 'root_native_uuid', 'parent_native_uuid', 'agent_path'}


def sha(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None,
            'Exact SHA256 required')
    return value


def entity(value):
    require(type(value) is dict and set(value) == {'kind', 'mode', 'bytes', 'sha256'},
            'Exact regular-file entity required')
    require(value['kind'] == 'file' and type(value['mode']) is int
            and 0 <= value['mode'] <= 0o7777 and type(value['bytes']) is int
            and value['bytes'] > 0, 'Invalid regular-file entity fields')
    sha(value['sha256'])
    return dict(value)


def finite(value):
    require(type(value) in (int, float) and math.isfinite(value), 'Finite original time required')
    return value


def same(left, right):
    import json
    return json.dumps(left, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(right, sort_keys=True, separators=(',', ':'), allow_nan=False)


def reply_bytes(raw):
    require(type(raw) is bytes and bool(raw), 'Original reply bytes required')
    text = raw.decode('utf-8', errors='strict')
    require(text.endswith('\n') and not text.endswith('\n\n')
            and '\r' not in text and '\x00' not in text and bool(text.strip()),
            'Canonical nonempty UTF8 reply with one terminal LF required')
    return raw


def authority(review_raw, *, binding, semantic_review_entity, first_seal_entity, evidence_entities,
              reviewer_identity, private_assignment_entity, source_pin_digest,
              original_started_at, original_deadline, first_completed_at,
              sealed_at, decided_at, policy_sha256):
    require(type(review_raw) is bytes, 'Original semantic review bytes required')
    review_pin = entity(semantic_review_entity)
    require(review_pin['bytes'] == len(review_raw) and review_pin['sha256'] == core.digest(review_raw),
            'Original semantic review entity and bytes disagree')
    review = core.decode(review_raw)
    require(type(review) is dict and set(review) == REVIEW_KEYS
            and type(review['schema_version']) is int and review['schema_version'] == 1,
            'Exact semantic review schema required')
    require(type(binding) is dict and set(binding) == BINDING_KEYS
            and all(type(v) is str and bool(v) for v in binding.values())
            and binding['case_id'] in ('B03', 'B04'), 'Exact necessary-question binding required')
    require(binding['root_native_uuid'] != binding['parent_native_uuid']
            and re.fullmatch('/root/[A-Za-z0-9_]+', binding['agent_path']) is not None,
            'Distinct original root/parent identity and exact actor path required')
    for key in ('run_id', 'case_id', 'root_native_uuid'):
        require(review[key] == binding[key], 'Semantic review identity changed')
    seal = entity(first_seal_entity)
    require(same(review['first_seal_entity'], seal), 'Semantic review seal changed')
    require(type(evidence_entities) is dict and bool(evidence_entities), 'Sealed evidence set required')
    for path, pin in evidence_entities.items():
        require(type(path) is str and bool(path) and '\x00' not in path,
                'Explicit sealed evidence locator required')
        entity(pin)
    require(same(review['evidence_entities'], evidence_entities), 'Semantic review evidence changed')
    require(type(reviewer_identity) is dict and bool(reviewer_identity)
            and type(reviewer_identity.get('native_uuid')) is str
            and reviewer_identity['native_uuid'] not in (binding['root_native_uuid'], binding['parent_native_uuid'])
            and reviewer_identity.get('model') == 'gpt-6.1-sol'
            and reviewer_identity.get('effort') == 'medium',
            'Separately authenticated independent fixed-model reviewer identity required')
    require(same(review['reviewer_identity'], reviewer_identity), 'Semantic reviewer provenance changed')
    require(review['source_pin_digest'] == sha(source_pin_digest), 'Semantic review source pins changed')
    scores = review['scores']
    require(type(scores) is dict and set(scores) == SCORES
            and all(type(v) is bool for v in scores.values()), 'Exact typed first-question scores required')
    classification = review['classification']
    require(type(classification) is str and classification in ('relevant_question', 'unnecessary_only', 'no_question'),
            'Supported semantic classification required')
    if classification != 'relevant_question':
        require(scores['necessary_question_pass'] is False, 'No relevant question cannot pass necessary-question score')
    require(type(review['rationale']) is str and bool(review['rationale'].strip()), 'Semantic rationale required')
    started, deadline, completed, sealed, reviewed, decided = map(finite, (
        original_started_at, original_deadline, first_completed_at,
        sealed_at, review['reviewed_at'], decided_at))
    require(deadline == started + 1200 and started <= completed <= sealed <= reviewed <= decided < deadline,
            'Original whole clock or semantic review chronology changed')
    # All branches retain the preallocated opaque assignment. Non-policy branches
    # cannot acquire its reply fingerprint or behavioral eligibility.
    assignment = entity(private_assignment_entity)
    kind = {'relevant_question': 'policy', 'unnecessary_only': 'neutral', 'no_question': 'none'}[classification]
    if kind == 'policy':
        reply_sha = sha(policy_sha256)
    else:
        require(policy_sha256 is None, 'Undelivered private policy fingerprint forbidden')
        reply_sha = core.digest(NEUTRAL) if kind == 'neutral' else None
    return {'schema_version': 1, **dict(binding), 'first_seal_entity': seal,
            'semantic_review_entity': review_pin,
            'private_assignment_entity': assignment, 'reply_kind': kind,
            'reply_sha256_or_null': reply_sha, 'expected_root_turns': 1 if kind == 'none' else 2,
            'original_started_at': started, 'original_deadline': deadline,
            'sealed_at': sealed, 'decided_at': decided, 'source_pin_digest': source_pin_digest,
            'classification': classification, 'question_scores': dict(scores),
            'semantic_rationale': review['rationale'], 'transport_verified': False,
            'private_behavior_eligible': False, 'comparison_admitted': False}
