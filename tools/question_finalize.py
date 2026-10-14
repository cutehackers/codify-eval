"""Qualify an independent dialogue review without changing implementation grades."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from collect import find_session
from question_bundle import digest


def finalize(bundle: Path, review: Path, agent: str, output: Path) -> dict:
    if output.exists():
        raise ValueError('Preserve existing review proof; use a fresh output path')
    evidence = json.loads(bundle.read_text())
    result = json.loads(review.read_text())
    source_map = bundle.parent / 'source-map.json'
    mapping = json.loads(source_map.read_text())
    recorded = next(row for row in mapping['bundles'] if row['path'] == str(bundle))
    if digest(bundle.read_bytes()) != recorded['sha256']:
        raise ValueError('Bundle changed after export')
    expected = {row['alias'] for row in evidence['records']}
    aliases = [row['alias'] for row in result['records']]
    if len(aliases) != len(set(aliases)) or set(aliases) != expected:
        raise ValueError('Review must cover every bundle alias exactly once')
    keys = ('required_policy_questions', 'other_necessary_questions',
            'unnecessary_questions', 'duplicate_approval_requests')
    for row in result['records']:
        if not all(type(row.get(key)) is int and row[key] >= 0 for key in keys):
            raise ValueError('Question counts must be nonnegative integers')
        if not isinstance(row.get('evidence'), list) or not row['evidence']:
            raise ValueError('Missing semantic evidence')
        if not isinstance(row.get('uncertainties'), list):
            raise ValueError('Missing uncertainty declaration')
    source = find_session(agent)
    events = [json.loads(line) for line in source.read_text().splitlines()]
    models = [{'model': e['payload'].get('model'), 'effort': e['payload'].get('effort')}
              for e in events if e['type'] == 'turn_context']
    terminal = any(e['type'] == 'event_msg' and e['payload'].get('type') == 'task_complete'
                   for e in events)
    if not terminal or not models or any(m != {'model': 'gpt-6.1-sol', 'effort': 'medium'}
                                         for m in models):
        raise ValueError('Reviewer is not terminal or has unqualified model metadata')
    totals = {key: sum(row[key] for row in result['records']) for key in keys}
    proof = {'status': 'partial_independent_semantic_review_complete',
             'records': len(aliases), 'totals': totals,
             'bundle': str(bundle), 'bundle_sha256': digest(bundle.read_bytes()),
             'review': str(review), 'review_sha256': digest(review.read_bytes()),
             'source_map': str(source_map), 'source_map_sha256': digest(source_map.read_bytes()),
             'reviewer': {'agent_path': agent, 'source': str(source),
                          'source_sha256': digest(source.read_bytes()),
                          'models': models, 'terminal': terminal},
             'checked_at_utc': datetime.now(timezone.utc).isoformat(),
             'limitations': ['Only the selected comparisons are reviewed.',
                            'Visible-dialogue observations are not implementation scores.',
                            'Masking names does not prove complete semantic blindness.']}
    output.write_text(json.dumps(proof, ensure_ascii=False, indent=2))
    return {'proof': str(output), 'records': len(aliases), 'totals': totals,
            'models': models, 'terminal': terminal}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    parser.add_argument('review', type=Path)
    parser.add_argument('reviewer')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(finalize(args.bundle.resolve(), args.review.resolve(),
                              args.reviewer, args.output.resolve()), indent=2))
