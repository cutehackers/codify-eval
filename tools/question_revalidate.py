"""Revalidate unchanged dialogue observations after the v3.5 report-mask repair.

This creates explicit provenance bridges, not new semantic model reviews.
Existing strict question-analysis validators remain unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from collect import SESSION_ROOT, find_session
from prepare import ROOT
from question_bundle import digest, reviewed_sources
from question_finalize import finalize
from report import recorded_status


REPORT_FIELDS = {
    'report_pass', 'report_review', 'reviewer', 'critical_violation',
    'overall_pass', 'status', 'verification_pass', 'verification_evidence',
    'verification_evidence_unavailable', 'error', 'error_category',
}


def read(path):
    return json.loads(path.read_text())


def same_behavior(old, new):
    if {k: v for k, v in old.items() if k not in REPORT_FIELDS} != {
            k: v for k, v in new.items() if k not in REPORT_FIELDS}:
        raise ValueError('Behavioral grading changed; this bridge cannot authorize reuse')


def write_identical_or_new(path, data):
    if path.exists() and path.read_bytes() != data:
        raise ValueError(f'Preserve existing derived evidence: {path}')
    if not path.exists():
        path.write_bytes(data)


def fresh_context(reviewer, run_ids, old_aliases):
    raw = reviewer.read_bytes()
    text = raw.decode()
    folded = text.casefold()
    if any(run_id.casefold() in folded for run_id in run_ids):
        raise ValueError('Fresh reviewer native context contains a condition identity')
    if any(alias in text for alias in old_aliases):
        raise ValueError('Fresh reviewer native context references exposed report evidence')
    meta = json.loads(text.splitlines()[0])['payload']
    spawn = meta['source']['subagent']['thread_spawn']
    parent_id = spawn['parent_thread_id']
    parents = list(SESSION_ROOT.rglob('*-' + parent_id + '.jsonl'))
    if len(parents) != 1:
        raise ValueError('Fresh reviewer parent source is ambiguous')
    parent_raw = parents[0].read_bytes()
    events = [json.loads(line) for line in parent_raw.decode().splitlines()]
    parent_path = events[0]['payload']['source']['subagent']['thread_spawn']['agent_path']
    calls, returns = {}, {}
    for event in events:
        payload = event.get('payload', {})
        if payload.get('type') == 'function_call' and payload.get('name', '').split('.')[-1] == 'spawn_agent':
            args = payload.get('arguments', {})
            args = json.loads(args) if isinstance(args, str) else args
            if parent_path + '/' + args.get('task_name', '') == spawn['agent_path']:
                calls[payload['call_id']] = args
        if payload.get('type') == 'function_call_output':
            try:
                returns[payload['call_id']] = json.loads(payload.get('output', ''))
            except (ValueError, TypeError):
                pass
    matched = [(call_id, args) for call_id, args in calls.items()
               if returns.get(call_id, {}).get('task_name') == spawn['agent_path']]
    if len(matched) != 1:
        raise ValueError('Successful reviewer spawn source is ambiguous')
    call_id, args = matched[0]
    if args.get('fork_turns') != 'none' or args.get('model') != 'gpt-6.1-sol' or args.get('reasoning_effort') != 'medium':
        raise ValueError('Fresh reviewer must have verified non-inherited context')
    return {'reviewer_source_sha256': digest(raw),
            'parent_source': str(parents[0]),
            'parent_source_prefix_bytes': len(parent_raw),
            'parent_source_prefix_sha256': digest(parent_raw),
            'successful_spawn_call_id': call_id, 'fork_turns': 'none',
            'native_condition_identities_found': 0,
            'old_report_aliases_found': 0}


def revalidate(old_proof, output):
    if output.exists():
        raise ValueError('Preserve existing revalidation proof')
    old_proof = old_proof.resolve()
    proof = read(old_proof)
    # Checks immutable old bundle/review/map and the actual original semantic reviewer.
    prior = reviewed_sources([old_proof])
    old_bundle = Path(proof['bundle'])
    aliases = [row['alias'] for row in read(old_bundle)['records']]
    exposed_reviewers = set()
    incident = read(ROOT / 'results' / 'condition-identity-qualification-archive-v3.5.json')
    run_ids = [record['run_id'] for record in incident['records']]
    old_aliases = []
    for record in incident['records']:
        old_map = ROOT / 'results' / record['run_id'] / 'revisions' / 'identity-mask-v3.4' / 'review-bundle-map.json'
        if old_map.exists():
            old_aliases.append(read(old_map)['alias'])
        if record['report_qualification_revoked']:
            original = read(ROOT / 'results' / record['run_id'] /
                            'revisions' / 'identity-mask-v3.4' / 'grade.json')
            exposed_reviewers.add(original['reviewer']['agent_path'])
    rows, bridges, contexts = [], [], {}
    for alias in aliases:
        source = prior[alias]
        directory = ROOT / 'results' / source['run_id']
        archive = directory / 'revisions' / 'identity-mask-v3.4'
        old_grade = archive / 'grade.json'
        current_grade = directory / 'grade.json'
        if digest(old_grade.read_bytes()) != source['grade_sha256']:
            raise ValueError('Preserved original grade does not match old observation')
        new = read(current_grade)
        if recorded_status(new) not in {'pass', 'fail'}:
            raise ValueError('Fresh report qualification is not available')
        same_behavior(read(old_grade), new)
        for filename, key in [('manifest.json', 'manifest_sha256'),
                              ('turns.json', 'turns_sha256')]:
            if digest((directory / filename).read_bytes()) != source[key]:
                raise ValueError(f'Original dialogue source changed: {filename}')
        manifest = read(directory / 'manifest.json')
        actor = find_session(manifest['agent_path'])
        if digest(actor.read_bytes()) != source['native_session_sha256']:
            raise ValueError('Original actor dialogue changed')
        mapping = read(directory / 'review-bundle-map.json')
        expected_alias = 'review-' + hashlib.sha256(
            (source['run_id'] + ':identity-mask-v3.5').encode()).hexdigest()[:12]
        if mapping['alias'] != expected_alias:
            raise ValueError('Fresh v3.5 report bundle is required')
        pregrade = directory / 'grade-before-report.json'
        if digest(pregrade.read_bytes()) != mapping['source_grade_sha256']:
            raise ValueError('Fresh report grade source linkage is invalid')
        if digest((directory / 'turns.json').read_bytes()) != mapping['source_turns_sha256']:
            raise ValueError('Fresh report dialogue source linkage is invalid')
        if pregrade.read_bytes() != (archive / 'grade-before-report.json').read_bytes():
            raise ValueError('External grade changed during report-only repair')
        review_dir = ROOT / 'runtime' / 'blind-reviews' / mapping['alias']
        evidence_text = (review_dir / 'evidence.json').read_text()
        if source['run_id'] in evidence_text or source['run_id'].lower() in evidence_text:
            raise ValueError('Condition identity remains in fresh report evidence')
        if new['report_review'] != mapping['alias']:
            raise ValueError('Fresh report identity mismatch')
        if digest((review_dir / 'evidence.json').read_bytes()) != mapping['bundle_sha256']:
            raise ValueError('Fresh report evidence changed')
        if digest((review_dir / 'review.json').read_bytes()) != new['reviewer']['review_sha256']:
            raise ValueError('Fresh report review changed')
        if new['reviewer']['agent_path'] in exposed_reviewers:
            raise ValueError('Exposed reviewer context cannot qualify the replacement')
        reviewer = find_session(new['reviewer']['agent_path'])
        if str(reviewer) not in contexts:
            contexts[str(reviewer)] = fresh_context(reviewer, run_ids, old_aliases)
        models, terminal = [], False
        for line in reviewer.read_text().splitlines():
            event = json.loads(line)
            payload = event.get('payload', {})
            if event['type'] == 'turn_context':
                models.append({'model': payload.get('model'), 'effort': payload.get('effort')})
            if event['type'] == 'event_msg' and payload.get('type') == 'task_complete':
                terminal = True
        if not terminal or not models or any(
                model != {'model': 'gpt-6.1-sol', 'effort': 'medium'} for model in models):
            raise ValueError('Fresh report reviewer is not qualified')
        updated = dict(source, grade_sha256=digest(current_grade.read_bytes()))
        rows.append(updated)
        bridges.append({
            'alias': alias, 'run_id': source['run_id'],
            'preserved_old_grade': str(old_grade),
            'old_grade_sha256': source['grade_sha256'],
            'new_grade_sha256': updated['grade_sha256'],
            'unchanged_actor_dialogue_sha256': source['native_session_sha256'],
            'unchanged_external_grade_sha256': mapping['source_grade_sha256'],
            'new_report_alias': mapping['alias'],
            'new_report_reviewer_source_sha256': digest(reviewer.read_bytes()),
            'fresh_native_context': contexts[str(reviewer)],
            'new_status': new['status'],
        })
    snapshot = digest(json.dumps({'bridges': bridges,
                                  'old_proof_sha256': digest(old_proof.read_bytes()),
                                  'helper_sha256': digest(Path(__file__).read_bytes())},
                                 sort_keys=True).encode())[:16]
    folder = ROOT / 'runtime' / 'question-reviews' / 'revalidated-v3.5' / snapshot
    folder.mkdir(parents=True, exist_ok=True)
    bundle = folder / 'bundle.json'
    write_identical_or_new(bundle, old_bundle.read_bytes())
    source_map = {
        'records': rows,
        'bundles': [{'path': str(bundle), 'sha256': digest(bundle.read_bytes()),
                     'records': len(rows)}],
        'revalidation': {
            'old_proof': str(old_proof), 'old_proof_sha256': digest(old_proof.read_bytes()),
            'old_source_map_sha256': proof['source_map_sha256'],
            'identical_dialogue_bundle_sha256': proof['bundle_sha256'],
            'helper_sha256': digest(Path(__file__).read_bytes()),
            'bridges': bridges,
        },
    }
    write_identical_or_new(folder / 'source-map.json',
                           json.dumps(source_map, indent=2).encode())
    result = finalize(bundle, Path(proof['review']), proof['reviewer']['agent_path'], output)
    current = read(output)
    current.update(status='revalidated_same_dialogue_semantic_review',
                   semantic_model_reexecuted=False,
                   provenance_bridge=source_map['revalidation'],
                   note='Original semantic review applies to byte-identical dialogue. '
                        'Success-only grouping must use the replacement final grades.')
    output.write_text(json.dumps(current, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('old_proof', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(revalidate(args.old_proof, args.output.resolve()), indent=2))
