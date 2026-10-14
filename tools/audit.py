"""Read-only evidence audit. Dataset coverage and evidence integrity are separate."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from collect import find_session
from prepare import ROOT, case_directory, tree_hash
from report import recorded_status


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(candidate='C0', manifest_name='frozen-core-v3.5.json'):
    frozen = read(ROOT / 'results' / manifest_name)
    schedule = read(ROOT / 'results' / f'schedule-{candidate}.json')
    global_issues = []
    for name, expected in frozen['grader_hashes'].items():
        if sha(ROOT / name) != expected:
            global_issues.append(f'Evaluator hash mismatch: {name}')
    if sha(ROOT / 'docs/spec.md') != frozen['spec_hash']:
        global_issues.append('Specification hash mismatch')
    for case, expected in frozen['cases'].items():
        if tree_hash(case_directory(case)) != expected:
            global_issues.append(f'Case hash mismatch: {case}')
    for condition, expected in frozen['skills'].items():
        if tree_hash(ROOT / 'snapshots' / condition) != expected:
            global_issues.append(f'Skill snapshot hash mismatch: {condition}')

    sessions = {}

    def session_evidence(agent_path):
        if agent_path not in sessions:
            source = find_session(agent_path)
            models, completed = [], False
            for line in source.read_text().splitlines():
                item = json.loads(line)
                payload = item.get('payload', {})
                if item.get('type') == 'turn_context':
                    models.append({'model': payload.get('model'), 'effort': payload.get('effort')})
                if item.get('type') == 'event_msg' and payload.get('type') == 'task_complete':
                    completed = True
            sessions[agent_path] = {'path': str(source), 'models': models,
                                    'completed': completed, 'sha256': sha(source)}
        return sessions[agent_path]

    records = []
    for task in schedule['runs']:
        run_id = task['run_id']
        output = ROOT / 'results' / run_id
        grade_path = output / 'grade.json'
        if not grade_path.exists():
            records.append({'run_id': run_id, 'status': 'not_evaluated', 'integrity': 'not_checked'})
            continue
        grade = read(grade_path)
        status = recorded_status(grade)
        if status not in {'pass', 'fail'}:
            records.append({'run_id': run_id, 'status': status, 'integrity': 'not_checked'})
            continue
        issues = []

        def require(value, message):
            if not value:
                issues.append(message)

        try:
            runtime = ROOT / 'runtime' / run_id
            run = read(runtime / 'run.json')
            require(run['case_id'] == task['case'] and run['condition'] == task['condition']
                    and run['repeat'] == task['repeat'] and run['phase'] == task['phase'],
                    'Run identity differs from schedule')
            require(run['model'] == 'gpt-6.1-sol' and run['effort'] == 'medium', 'Actor settings mismatch')
            require(run['image_id'] == frozen['image_id'], 'Runtime image mismatch')
            require(run['case_hash'] == frozen['cases'][task['case']], 'Actor case hash mismatch')
            require(run['condition'] == 'A' or run['skill_hash'] == frozen['skills'][run['condition']],
                    'Actor skill hash mismatch')
            require(sha(runtime / 'request.txt') == run['prompt_hash'], 'Prompt file changed')
            require(not run['tool_audit'], 'Recorded transport violation')
            require(bool(run['completion_evidence']), 'Missing actor terminal evidence')
            actor = session_evidence(run['agent_path'])
            require(actor['completed'] and actor['models'] and
                    all(m == {'model': 'gpt-6.1-sol', 'effort': 'medium'} for m in actor['models']),
                    'Actor original session is not qualified')
            turns = read(output / 'turns.json')
            require(bool(turns) and turns == run['turns'], 'Exported turn records differ from runtime')
            require(len(turns) <= run.get('user_turn_limit', 4), 'User turn limit exceeded')
            for name, expected in turns[-1]['file_hashes'].items():
                file = runtime / 'repo' / name
                require(file.exists() and sha(file) == expected, f'Final actor file changed: {name}')
            mapping = read(output / 'review-bundle-map.json')
            bundle = ROOT / 'runtime' / 'blind-reviews' / mapping['alias']
            require(sha(output / 'grade-before-report.json') == mapping['source_grade_sha256'],
                    'Reviewed external grade is not preserved')
            require(sha(output / 'turns.json') == mapping['source_turns_sha256'], 'Reviewed turns changed')
            require(sha(bundle / 'evidence.json') == mapping['bundle_sha256'], 'Masked review bundle changed')
            require(sha(bundle / 'review.json') == grade['reviewer']['review_sha256'], 'Reviewer output changed')
            require(read(bundle / 'review.json') == read(output / 'report-review.json'),
                    'Stored report review differs from reviewer output')
            reviewer = session_evidence(grade['reviewer']['agent_path'])
            require(reviewer['completed'] and reviewer['models'] and
                    all(m == {'model': 'gpt-6.1-sol', 'effort': 'medium'} for m in reviewer['models']),
                    'Reviewer original session is not qualified')
            require(type(grade.get('overall_pass')) is bool and
                    grade['overall_pass'] == (grade['status'] == 'pass'), 'Terminal verdict is inconsistent')
            if task['phase'] == 'software':
                require(type(grade.get('verification_pass')) is bool and
                        not grade.get('verification_evidence_unavailable'), 'Software verification unresolved')
        except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
            issues.append(f'Missing or malformed required evidence: {error}')
        records.append({'run_id': run_id, 'status': grade['status'],
                        'integrity': 'pass' if not issues else 'error', 'issues': issues})
    finished = all(r['status'] in {'pass', 'fail'} for r in records)
    integrity_ok = not global_issues and all(r['integrity'] != 'error' for r in records)
    return {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
            'manifest': manifest_name, 'auditor_sha256': sha(Path(__file__)),
            'planned': len(records), 'checked_final': sum(r['integrity'] != 'not_checked' for r in records),
            'all_comparisons_final': finished, 'recorded_final_integrity_pass': integrity_ok,
            'dataset_evidence_complete': finished and integrity_ok,
            'global_issues': global_issues, 'records': records,
            'limits': ['Does not prove overall goal completion, skill benefit, or provider internal routing.',
                       'Transport findings rely on preserved collector audit and independent command review.',
                       'Pilots, representative GUI checks, installed skill validation and final synthesis require separate completion evidence.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', default='C0')
    parser.add_argument('--manifest', default='frozen-core-v3.5.json')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    result = audit(args.candidate, args.manifest)
    if args.write:
        (ROOT / 'results' / f'evidence-audit-{args.candidate}.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in {'records', 'limits'}}, indent=2))
    for row in result['records']:
        if row['integrity'] == 'error':
            print(json.dumps(row, ensure_ascii=False))
