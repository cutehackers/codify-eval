"""Export condition-masked visible dialogue for semantic question-efficiency review.

This is an analysis helper, not a behavior grader. It never scores questions.
Only finalized comparisons enter the bundle. Original dialogue remains intact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from collect import SESSION_ROOT
from prepare import ROOT
from report import recorded_status


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mask(text: str) -> str:
    # Remove invocation prefixes equally, retain every actual question/approval.
    text = text.replace('$codify', '')
    for name in ('.agents/skills/codify', 'Codify', 'codify'):
        text = text.replace(name, '[skill]')
    return text.strip()


def session_index() -> dict[str, Path]:
    index = {}
    for path in SESSION_ROOT.glob('2026/10/*/*.jsonl'):
        try:
            with path.open() as stream:
                meta = json.loads(next(stream)).get('payload', {})
            source = meta.get('source', {})
            if not isinstance(source, dict):
                continue
            actor = source.get('subagent', {}).get('thread_spawn', {}).get('agent_path')
            if actor:
                if actor in index:
                    raise ValueError(f'Duplicate actor session: {actor}')
                index[actor] = path
        except (OSError, StopIteration, json.JSONDecodeError):
            continue
    return index


def reviewed_sources(proofs: list[Path]) -> dict:
    reviewed = {}
    for proof_path in proofs:
        proof = json.loads(proof_path.read_text())
        reviewer = proof['reviewer']
        if not reviewer['terminal'] or not reviewer['models'] or any(
                model != {'model': 'gpt-6.1-sol', 'effort': 'medium'}
                for model in reviewer['models']):
            raise ValueError('Unqualified question reviewer')
        for path_key, hash_key in [('bundle', 'bundle_sha256'), ('review', 'review_sha256'),
                                   ('source_map', 'source_map_sha256')]:
            if digest(Path(proof[path_key]).read_bytes()) != proof[hash_key]:
                raise ValueError(f'Changed review evidence: {proof_path}')
        if digest(Path(reviewer['source']).read_bytes()) != reviewer['source_sha256']:
            raise ValueError(f'Changed reviewer session: {proof_path}')
        review = json.loads(Path(proof['review']).read_text())
        bundle = json.loads(Path(proof['bundle']).read_text())
        aliases = [row['alias'] for row in review['records']]
        if len(aliases) != len(set(aliases)) or set(aliases) != {row['alias'] for row in bundle['records']}:
            raise ValueError('Question review coverage mismatch')
        mapping = {row['alias']: row for row in json.loads(Path(proof['source_map']).read_text())['records']}
        for alias in aliases:
            reviewed[alias] = mapping[alias]
    return reviewed


def build(phase: str, batch_size: int, exclude_reviewed: list[Path] | None = None) -> dict:
    if batch_size < 1:
        raise ValueError('batch_size must be positive')
    sessions = session_index()
    reviewed = reviewed_sources(exclude_reviewed or [])
    reused = []
    records, mappings = [], []
    for directory in sorted((ROOT / 'results').glob(f'{phase}-*')):
        grade_path = directory / 'grade.json'
        if not grade_path.is_file():
            continue
        grade = json.loads(grade_path.read_text())
        if recorded_status(grade) not in {'pass', 'fail'}:
            continue
        manifest_path, turns_path = directory / 'manifest.json', directory / 'turns.json'
        manifest = json.loads(manifest_path.read_text())
        turns = json.loads(turns_path.read_text())
        source = sessions[manifest['agent_path']]
        source_bytes = source.read_bytes()
        visible = []
        for line in source_bytes.decode().splitlines():
            item = json.loads(line)
            payload = item.get('payload', {})
            if item.get('type') != 'response_item' or payload.get('type') != 'message':
                continue
            if payload.get('role') != 'assistant':
                continue
            channel = payload.get('channel')
            message_phase = payload.get('phase')
            if channel == 'analysis':
                continue
            if channel not in {'commentary', 'final'} and message_phase not in {'commentary', 'final_answer'}:
                continue
            text = '\n'.join(c.get('text', '') for c in payload.get('content', [])
                             if c.get('type') in {'output_text', 'text'})
            kind = 'final' if channel == 'final' or message_phase == 'final_answer' else 'commentary'
            visible.append({'kind': kind, 'text': text})
        finals = [message['text'] for message in visible if message['kind'] == 'final']
        if finals != [turn['final'] for turn in turns]:
            raise ValueError(f'Native/exported final dialogue mismatch: {directory.name}')
        dialogue, cursor = [], 0
        for turn in turns:
            dialogue.append({'speaker': 'user', 'text': mask(turn['request'])})
            while cursor < len(visible):
                message = visible[cursor]
                cursor += 1
                dialogue.append({'speaker': 'assistant', 'kind': message['kind'], 'text': mask(message['text'])})
                if message['kind'] == 'final':
                    break
        if cursor != len(visible):
            raise ValueError(f'Unassigned visible messages: {directory.name}')
        alias = 'q-' + digest(directory.name.encode())[:12]
        mapping = {'alias': alias, 'run_id': directory.name,
                         'grade_sha256': digest(grade_path.read_bytes()),
                         'turns_sha256': digest(turns_path.read_bytes()),
                         'manifest_sha256': digest(manifest_path.read_bytes()),
                         'native_session_sha256': digest(source_bytes)}
        if alias in reviewed:
            if reviewed[alias] != mapping:
                raise ValueError(f'Reviewed dialogue evidence changed: {alias}')
            reused.append(mapping)
            continue
        records.append({'alias': alias, 'case': grade['case_id'], 'dialogue': dialogue})
        mappings.append(mapping)
    snapshot = digest(json.dumps({'records': records, 'mappings': mappings,
                                 'reused': reused,
                                 'proofs': [str(p) for p in exclude_reviewed or []],
                                 'batch_size': batch_size,
                                 'exporter_sha256': digest(Path(__file__).read_bytes())},
                                 ensure_ascii=False, sort_keys=True).encode())[:16]
    output = ROOT / 'runtime' / 'question-reviews' / phase / snapshot
    output.mkdir(parents=True, exist_ok=True)
    instructions = (
        'Review all user and visible assistant messages. Condition and skill names are masked. '
        'For each alias, identify actual requests for a human answer/approval and classify them as '
        'required policy questions, other necessary clarification, unnecessary questions, or duplicate '
        'approval requests after sufficient authorization. Count a repeated request once per occurrence, '
        'not each option or question mark. Do not count rhetorical statements, progress messages, or '
        'instructions to an end user as evaluation-user questions. Read the public task and subsequent '
        'reply before judging necessity. Do not infer a zero from turn count. Return records with alias, '
        'required_policy_questions, other_necessary_questions, unnecessary_questions, '
        'duplicate_approval_requests, evidence (quote messages or explain absence), and uncertainties. '
        'Do not grade implementation, inspect other paths, or use condition guesses. No delegation. '
        'Some semantic wording may still suggest a workflow, so masking does not prove total blindness.'
    )
    files = []
    for start in range(0, len(records), batch_size):
        path = output / f'bundle-{start // batch_size + 1:03d}.json'
        data = {'phase': phase, 'instructions': instructions, 'records': records[start:start + batch_size]}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        files.append({'path': str(path), 'sha256': digest(path.read_bytes()), 'records': len(data['records'])})
    mapping_path = output / 'source-map.json'
    mapping_path.write_text(json.dumps({'records': mappings, 'bundles': files,
                                     'snapshot': snapshot, 'batch_size': batch_size,
                                     'exporter_sha256': digest(Path(__file__).read_bytes()),
                                     'reused_reviewed_records': reused,
                                     'review_proofs': [str(p) for p in exclude_reviewed or []],
                                     'status': 'prepared_not_semantically_reviewed'}, indent=2))
    latest_path = ROOT / 'results' / f'question-review-{phase}-source-map.json'
    latest_path.write_text(json.dumps({'snapshot': snapshot, 'source_map': str(mapping_path),
                                     'source_map_sha256': digest(mapping_path.read_bytes()),
                                     'records': len(records), 'bundles': files,
                                     'reused_reviewed_records': len(reused),
                                     'status': 'prepared_not_semantically_reviewed'}, indent=2))
    return {'phase': phase, 'records': len(records), 'reused_reviewed_records': len(reused),
            'bundles': files, 'source_map': str(mapping_path)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', required=True, choices=['primary', 'auxiliary', 'software', 'heldout'])
    parser.add_argument('--batch-size', type=int, default=27)
    parser.add_argument('--exclude-reviewed', type=Path, action='append', default=[])
    args = parser.parse_args()
    print(json.dumps(build(args.phase, args.batch_size, args.exclude_reviewed), indent=2))
