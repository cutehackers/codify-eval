"""Read-only prospective public case routing from qualified v2 fixture evidence.

This module allocates nothing and does not admit a live model or adapter. Private
inventory bytes are hashed for continuity; owner replies and test bodies are
never returned in public contracts.
"""
import json

import improvement_baseline_pilot_materialize_v2 as materializer
import improvement_optional_comparison_driver_v8 as historical

ROOT = materializer.ROOT
BASE = ROOT / 'results/improvement-v1'
REVIEW = BASE / 'baseline-pilot-sdk-v2-independent-outcome-review-v1.json'
VERIFICATION = BASE / 'baseline-pilot-sdk-v2-independent-outcome-root-verification-v1.json'
PLAN = BASE / 'baseline-pilot-sdk-qualification-v2-plan-private-v6.json'
SCOPES = {
    'B01': ('fully_specified_coding', ('lib/job_rules.dart', 'lib/outbox.dart', 'lib/labels.dart')),
    'B02': ('fully_specified_coding', ('lib/pass_parser.dart', 'lib/gate_service.dart', 'lib/labels.dart')),
    'B03': ('necessary_question', ('lib/codec.dart', 'lib/decision.dart', 'lib/sync_service.dart', 'lib/labels.dart')),
    'B04': ('necessary_question', ('lib/journey_codec.dart', 'lib/decision.dart', 'lib/journey_service.dart', 'lib/labels.dart')),
}
require = materializer.require
encoded = materializer.encoded


def read(path):
    materializer.canonical(path)
    return json.loads(path.read_bytes())


def qualified_public_contract(case_id):
    require(type(case_id) is str and case_id in SCOPES, 'Exact registered case required')
    verified = read(VERIFICATION)
    require(verified.get('verdict') == 'pass' and verified.get('all_current_pins_verified') is True
            and verified.get('model_pilot_admitted') is False,
            'Current independent fixture review and root verification required')
    historical.control.reviewed_entity(REVIEW, verified['review_entity'])
    review = read(REVIEW)
    require(review.get('verdict') == 'pass' and review.get('issues') == []
            and review.get('checkpoint_1_to_5_qualified') is True
            and review.get('checkpoint_6_qualified') is False,
            'Fixture qualification does not establish live adapter admission')
    key = str(PLAN.relative_to(ROOT))
    historical.control.reviewed_entity(PLAN, review['evidence_entities'][key])
    authority = read(PLAN)
    actual = materializer.inventory(materializer.COHORT)
    require(encoded(actual) == encoded(authority['cohort_inventory']),
            'Exact original qualified full cohort membership and bytes required')
    case = materializer.canonical(materializer.COHORT / case_id)
    metadata = read(case / 'metadata.json')
    family, scope = SCOPES[case_id]
    require(metadata.get('id') == case_id and metadata.get('task_kind') == family
            and type(metadata.get('editable_paths')) is list
            and all(type(x) is str for x in metadata['editable_paths'])
            and len(set(metadata['editable_paths'])) == len(scope)
            and set(metadata['editable_paths']) == set(scope)
            and metadata.get('public_root') == 'public', 'Exact public routing metadata required')
    public = materializer.canonical(case / 'public')
    inventory = materializer.inventory(public)
    require(all(name in inventory and inventory[name]['kind'] == 'file' for name in scope),
            'All exact editable public files must exist')
    return {'case_id': case_id, 'task_kind': family,
            'public_root': str(public.relative_to(ROOT)),
            'editable_paths': list(scope), 'public_inventory': inventory,
            'fixture_review_entity': historical.control.entity(REVIEW),
            'fixture_root_verification_entity': historical.control.entity(VERIFICATION),
            'live_adapter_qualified': False, 'model_allocation_admitted': False}


def declared_execution(case_id, condition, worker_cap):
    require(type(condition) is str and condition in ('A', 'C0', 'C23'),
            'Exact prospective condition required')
    require(type(worker_cap) is int and worker_cap in (0, 2),
            'Solo cap zero or voluntary cap two must be declared explicitly')
    return {**qualified_public_contract(case_id), 'condition': condition,
            'worker_cap': worker_cap, 'cohort': 'solo' if worker_cap == 0 else 'voluntary',
            'model': 'gpt-6.1-sol', 'effort': 'medium', 'retries': 0}
