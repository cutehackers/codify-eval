"""Versioned native message normalization, preserving frozen evaluation inputs.

No actor execution, input changes or threshold changes. Original native records are
read unchanged. The normalized view only exposes a token already present in a native
content block to the frozen attester's legacy message-field reader.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import dialogue_control
import grade
from prepare import ROOT

VERSION = 'native-content-v1'
MANIFEST = ROOT / 'results/frozen-native-schema-v3.6.1.json'
REQUIRED_PINS = {'tools/dialogue_schema.py', 'tools/dialogue_control.py',
                 'tools/grade.py', 'tools/prepare.py', 'tools/collect.py',
                 'tools/finalize.py', 'docs/spec.md', 'results/frozen-core-v3.6.json'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(events):
    view = deepcopy(events)
    conversions = []
    for index, event in enumerate(view):
        payload = event.get('payload', {})
        if payload.get('type') != 'agent_message':
            continue
        content = payload.get('content')
        if content is None:
            if not isinstance(payload.get('message'), str):
                raise ValueError('Unrecognized native message representation')
            continue
        if not isinstance(content, list) or not content or any(not isinstance(b, dict) for b in content):
            raise ValueError('Unrecognized native content blocks')
        encrypted = [b['encrypted_content'] for b in content
                     if b.get('type') == 'encrypted_content' and isinstance(b.get('encrypted_content'), str)]
        if len(encrypted) == 1:
            token = encrypted[0]
            if (not token.startswith('gAAAAA') or len(content) not in {1, 2}
                    or sum(b.get('type') == 'encrypted_content' for b in content) != 1
                    or any(b.get('type') not in {'input_text', 'encrypted_content'} for b in content)
                    or any(b.get('type') == 'input_text' and not isinstance(b.get('text'), str) for b in content)):
                raise ValueError('Unqualified encrypted native message')
            source = 'content.encrypted_content'
        elif not encrypted and len(content) == 1 and content[0].get('type') == 'input_text' and isinstance(content[0].get('text'), str):
            token, source = content[0]['text'], 'content.input_text'
        else:
            raise ValueError('Ambiguous native message token blocks')
        if 'message' in payload and payload['message'] != token:
            raise ValueError('Conflicting native message representations')
        original = events[index]['payload']
        conversions.append({'event_index': index, 'source_field': source,
                            'original_payload_sha256': hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest(),
                            'token_sha256': hashlib.sha256(token.encode()).hexdigest(),
                            'plaintext_decrypted': False})
        payload['message'] = token
    return view, conversions


def qualified_grade(run_id):
    registration = json.loads(MANIFEST.read_text())
    if (registration.get('version') != VERSION or registration.get('status') != 'frozen'
            or set(registration.get('source_sha256', {})) != REQUIRED_PINS):
        raise ValueError('Native schema adapter is not preregistered')
    for name, expected in registration['source_sha256'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Registered native schema/grading source changed: ' + name)
    core = json.loads((ROOT / 'results/frozen-core-v3.6.json').read_text())
    if core.get('core_version') != 'v3.6' or core.get('freeze_revision') != 2:
        raise ValueError('Native schema adapter requires its unchanged registered core')
    for name, expected in core['grader_hashes'].items():
        if digest(ROOT / name) != expected:
            raise ValueError('Frozen evaluation source changed: ' + name)
    original_evidence, original_attest = dialogue_control.followup_evidence, dialogue_control.attest
    conversions = []

    def evidence(events, prefix, run, staging):
        view, mapped = normalize(events)
        conversions.extend(mapped)
        return original_evidence(view, prefix, run, staging)

    def attest(identifier):
        proof = {'version': VERSION, 'adapter_sha256': digest(Path(__file__)),
                 'registration_sha256': digest(MANIFEST),
                 'normalized_fields': conversions,
                 'original_native_records_mutated': False,
                 'actor_reexecuted': False, 'input_or_behavior_criteria_changed': False}
        try:
            audit = original_attest(identifier)
        except dialogue_control.ControlFault as error:
            error.audit['native_schema_adapter'] = proof
            raise
        audit['native_schema_adapter'] = proof
        return audit

    # A single process owns one qualification. Restoration also occurs on failure.
    dialogue_control.followup_evidence, dialogue_control.attest = evidence, attest
    try:
        return grade.grade(run_id)
    finally:
        dialogue_control.followup_evidence, dialogue_control.attest = original_evidence, original_attest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    args = parser.parse_args()
    result = qualified_grade(args.run_id)
    print(json.dumps({key: result.get(key) for key in ('run_id', 'status', 'case_id', 'behavior_pass', 'overall_pass')}, indent=2))
