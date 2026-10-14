"""Report independently observed questions without imputing unreviewed dialogues."""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from prepare import ROOT
from question_bundle import digest, reviewed_sources
from report import recorded_status


def aggregate(proofs: list[Path], candidate: str) -> dict:
    mappings = reviewed_sources(proofs)
    observations = {}
    keys = ('required_policy_questions', 'other_necessary_questions',
            'unnecessary_questions', 'duplicate_approval_requests')
    for proof_path in proofs:
        proof = json.loads(proof_path.read_text())
        review = json.loads(Path(proof['review']).read_text())
        for row in review['records']:
            alias = row['alias']
            if not all(type(row.get(k)) is int and row[k] >= 0 for k in keys):
                raise ValueError('Unqualified semantic counts')
            if alias in observations and any(observations[alias][k] != row[k] for k in keys):
                raise ValueError(f'Conflicting independent question counts: {alias}')
            observations[alias] = row
    schedule_path = ROOT / 'results' / f'schedule-{candidate}.json'
    schedule = json.loads(schedule_path.read_text())
    by_run = {row['run_id']: alias for alias, row in mappings.items()}
    schedule_ids = {row['run_id'] for row in schedule['runs']}
    if set(by_run) - schedule_ids:
        raise ValueError('Reviewed comparisons outside the requested schedule')
    groups, records = defaultdict(list), []
    for task in schedule['runs']:
        run_id = task['run_id']
        row = {**task, 'question_review': 'unavailable'}
        if run_id in by_run:
            alias = by_run[run_id]
            source = mappings[alias]
            folder = ROOT / 'results' / run_id
            for filename, key in [('grade.json', 'grade_sha256'),
                                  ('turns.json', 'turns_sha256'),
                                  ('manifest.json', 'manifest_sha256')]:
                if digest((folder / filename).read_bytes()) != source[key]:
                    raise ValueError(f'Changed reviewed comparison: {run_id}')
            grade = json.loads((folder / 'grade.json').read_text())
            state = recorded_status(grade)
            if state not in {'pass', 'fail'}:
                raise ValueError('Independent dialogue observation needs finalized comparison')
            row.update(question_review='observed', implementation_status=state,
                       alias=alias, **{k: observations[alias][k] for k in keys},
                       evidence=observations[alias]['evidence'],
                       uncertainties=observations[alias]['uncertainties'])
        groups[(task['phase'], task['condition'])].append(row)
        records.append(row)
    summaries = []
    for (phase, condition), items in groups.items():
        known = [row for row in items if row['question_review'] == 'observed']
        success = [row for row in known if row['implementation_status'] == 'pass']
        summaries.append({'phase': phase, 'condition': condition, 'planned': len(items),
                          'observed_count': len(known), 'unavailable_count': len(items) - len(known),
                          'totals_all_observed': {k: sum(row[k] for row in known) for k in keys},
                          'success_only': {'observed_count': len(success),
                                           'totals': {k: sum(row[k] for row in success) for k in keys}}})
    return {'candidate': candidate, 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
            'planned': len(records), 'observed': len(by_run),
            'complete': len(by_run) == len(records), 'groups': summaries, 'runs': records,
            'review_proofs': [{'path': str(p), 'sha256': digest(p.read_bytes())} for p in proofs],
            'schedule_sha256': digest(schedule_path.read_bytes()),
            'notes': ['Missing dialogue review is unavailable, never zero questions.',
                      'Question efficiency is separate from implementation scores.',
                      'Totals count requests, not punctuation or options.',
                      'Success-only counts exclude failed comparisons and are not overall performance.',
                      'Semantic wording may suggest a workflow despite name masking.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', default='C0')
    parser.add_argument('--proof', type=Path, action='append', required=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    report = aggregate([p.resolve() for p in args.proof], args.candidate)
    if args.write:
        (ROOT / 'results' / f'question-analysis-{args.candidate}.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: report[k] for k in ('candidate', 'planned', 'observed', 'complete')}, indent=2))
