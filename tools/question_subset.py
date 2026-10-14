"""Derive an immutable question-review subset without rerunning semantic review.

Only retained comparisons require current-source qualification. Excluded historical
observations remain in their original evidence and never enter the derived proof.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from collect import find_session
from prepare import ROOT
from question_bundle import digest, reviewed_sources
from report import recorded_status

KEYS = ('required_policy_questions', 'other_necessary_questions',
        'unnecessary_questions', 'duplicate_approval_requests')


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def indexed(rows: list[dict], label: str) -> dict:
    aliases = [row['alias'] for row in rows]
    if len(aliases) != len(set(aliases)):
        raise ValueError(f'Duplicate aliases in {label}')
    return dict(zip(aliases, rows))


def qualify_source(source: dict, case: str) -> None:
    folder = ROOT / 'results' / source['run_id']
    if folder.resolve().parent != (ROOT / 'results').resolve():
        raise ValueError('Source run must be a direct results child')
    for filename, key in [('grade.json', 'grade_sha256'),
                          ('turns.json', 'turns_sha256'),
                          ('manifest.json', 'manifest_sha256')]:
        if digest((folder / filename).read_bytes()) != source[key]:
            raise ValueError(f'Changed retained source: {source["alias"]} {filename}')
    grade = read(folder / 'grade.json')
    if recorded_status(grade) not in {'pass', 'fail'}:
        raise ValueError('Retained comparison must have a final grade')
    if grade['case_id'] != case:
        raise ValueError('Retained bundle case does not match its grade')
    actor = find_session(read(folder / 'manifest.json')['agent_path'])
    if digest(actor.read_bytes()) != source['native_session_sha256']:
        raise ValueError(f'Changed retained native actor: {source["alias"]}')


def subset(old_proof: Path, new_proof: Path, exclude_case: str) -> dict:
    old_proof, new_proof = old_proof.resolve(), new_proof.resolve()
    folder = new_proof.parent / (new_proof.stem + '-evidence')
    if new_proof.exists() or folder.exists():
        raise ValueError('Preserve existing output; use a fresh proof and evidence path')
    if not exclude_case:
        raise ValueError('An excluded case is required')
    proof = read(old_proof)
    # Existing strict qualification checks all original artifact/reviewer hashes.
    prior = reviewed_sources([old_proof])
    bundle = read(Path(proof['bundle']))
    review = read(Path(proof['review']))
    mapping = read(Path(proof['source_map']))
    original_bundle = indexed(bundle['records'], 'original bundle')
    original_review = indexed(review['records'], 'original review')
    original_map = indexed(mapping['records'], 'original source map')
    if set(original_bundle) != set(original_review) or not set(original_bundle) <= set(original_map):
        raise ValueError('Original evidence coverage mismatch')
    recorded = [row for row in mapping['bundles'] if row['path'] == proof['bundle']]
    if len(recorded) != 1 or recorded[0]['sha256'] != proof['bundle_sha256'] or recorded[0]['records'] != len(original_bundle):
        raise ValueError('Original bundle registration mismatch')
    for row in original_review.values():
        if not all(type(row.get(key)) is int and row[key] >= 0 for key in KEYS):
            raise ValueError('Unqualified original semantic counts')
        if not isinstance(row.get('evidence'), list) or not row['evidence'] or not isinstance(row.get('uncertainties'), list):
            raise ValueError('Missing original semantic evidence or uncertainties')
    totals = {key: sum(row[key] for row in original_review.values()) for key in KEYS}
    if proof['records'] != len(original_bundle) or proof['totals'] != totals:
        raise ValueError('Original proof counts do not match the semantic review')
    # Verify metadata against the actual immutable reviewer source, not just claims.
    reviewer = proof['reviewer']
    events = [json.loads(line) for line in Path(reviewer['source']).read_text().splitlines()]
    models = [{'model': e['payload'].get('model'), 'effort': e['payload'].get('effort')}
              for e in events if e['type'] == 'turn_context']
    terminal = any(e['type'] == 'event_msg' and e['payload'].get('type') == 'task_complete' for e in events)
    if not terminal or not models or models != reviewer['models'] or any(
            m != {'model': 'gpt-6.1-sol', 'effort': 'medium'} for m in models):
        raise ValueError('Original reviewer native metadata is unqualified')
    selected = sorted(alias for alias, row in original_bundle.items() if row['case'] != exclude_case)
    excluded = sorted(set(original_bundle) - set(selected))
    if not selected:
        raise ValueError('Cannot derive an empty subset')
    run_ids = [prior[alias]['run_id'] for alias in selected]
    if len(run_ids) != len(set(run_ids)):
        raise ValueError('Duplicate retained runs')
    for alias in selected:
        qualify_source(prior[alias], original_bundle[alias]['case'])
    provenance = {
        'original_proof': str(old_proof), 'original_proof_sha256': digest(old_proof.read_bytes()),
        'original_artifacts': {key: {'path': proof[key], 'sha256': proof[key + '_sha256']}
                               for key in ('bundle', 'review', 'source_map')},
        'original_reviewer': reviewer,
        'helper_sha256': digest(Path(__file__).read_bytes()),
        'selection_rule': {'exclude_case': exclude_case, 'case_source': 'original bundle records'},
        'original_records': len(original_bundle), 'retained_records': len(selected),
        'excluded_records': len(excluded), 'retained_aliases': selected, 'excluded_aliases': excluded,
        'semantic_model_reexecuted': False,
        'note': 'Deterministic subset of the original independent semantic review. '
                'Retained dialogue, semantic counts, evidence and uncertainties are unchanged. '
                'The original reviewer did not perform a new review of this derived subset.',
    }
    bundle_path, review_path, map_path = [folder / name for name in ('bundle.json', 'review.json', 'source-map.json')]
    derived_bundle = {**bundle, 'records': [original_bundle[a] for a in selected]}
    derived_review = {**review, 'records': [original_review[a] for a in selected]}
    encode = lambda value: json.dumps(value, ensure_ascii=False, indent=2).encode()
    bundle_bytes, review_bytes = encode(derived_bundle), encode(derived_review)
    derived_map = {'records': [original_map[a] for a in selected],
                   'bundles': [{'path': str(bundle_path), 'sha256': digest(bundle_bytes), 'records': len(selected)}],
                   'subset_derivation': provenance}
    map_bytes = encode(derived_map)
    derived_proof = {**proof, 'status': 'derived_subset_of_independent_semantic_review',
                     'records': len(selected),
                     'totals': {key: sum(original_review[a][key] for a in selected) for key in KEYS},
                     'bundle': str(bundle_path), 'bundle_sha256': digest(bundle_bytes),
                     'review': str(review_path), 'review_sha256': digest(review_bytes),
                     'source_map': str(map_path), 'source_map_sha256': digest(map_bytes),
                     'semantic_model_reexecuted': False, 'subset_derivation': provenance,
                     'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'note': provenance['note']}
    # The original reviewer metadata is retained explicitly as historical attribution.
    folder.mkdir()
    for path, data in [(bundle_path, bundle_bytes), (review_path, review_bytes), (map_path, map_bytes),
                       (new_proof, encode(derived_proof))]:
        with path.open('xb') as stream:
            stream.write(data)
    if reviewed_sources([new_proof]) != {a: prior[a] for a in selected}:
        raise ValueError('Derived strict qualification mismatch')
    return {'proof': str(new_proof), 'records': len(selected), 'excluded_records': len(excluded),
            'totals': derived_proof['totals'], 'semantic_model_reexecuted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('old_proof', type=Path)
    parser.add_argument('new_proof', type=Path)
    parser.add_argument('--exclude-case', required=True)
    args = parser.parse_args()
    print(json.dumps(subset(args.old_proof, args.new_proof, args.exclude_case), indent=2))
