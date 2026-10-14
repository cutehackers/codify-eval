"""Prospective collector adapter for an already qualified literal quote alias.

Historical grades and run metadata are never amended by this adapter.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path

import collect_schema_v366 as schema
import improvement_composed_quote_origin_v2 as saved
import transport
from prepare import ROOT

MANIFEST = ROOT / 'results/improvement-v1/composed-quote-collector-freeze-v2.json'
VERSION = 'improvement-composed-quote-collect-v2'
BASE_CONTEXT = schema.patched_origin
BASE_COLLECT = schema.qualified_collect


@contextmanager
def origin_context():
    """Keep original schema audit and extend only its literal origin recognizer."""
    with BASE_CONTEXT():
        before = transport.wrapper_origin
        transport.wrapper_origin = saved.wrapper_origin
        try:
            yield
        finally:
            transport.wrapper_origin = before


def audit(events, metadata, root):
    with origin_context():
        return schema.audit_transport(events, metadata, root)


def verify():
    saved.verify_registration()
    value = json.loads(MANIFEST.read_bytes())
    assert value['status'] == 'frozen' and value['historical_mutation_allowed'] is False
    required = {'tools/improvement_composed_quote_origin_v2.py',
                'tools/improvement_composed_quote_collect_v2.py',
                'tools/improvement_composed_quote_collect_v2_probes.py',
                'results/improvement-v1/composed-quote-collector-probes-v4.json',
                'results/improvement-v1/composed-quote-collector-review-v2.json'}
    assert required <= set(value['source_hashes'])
    for name, expected in value['source_hashes'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, name
    return value


def qualified_collect(run_id, agent_path, request=None, *, preservation=None):
    registration = verify()
    assert preservation is None, 'Prospective first collection only'
    folder = ROOT / 'results' / run_id
    assert not any((folder / name).exists() for name in ('grade.json', 'turns.json', 'manifest.json', 'native-tools.jsonl'))
    original = schema.patched_origin
    assert original is BASE_CONTEXT, 'Unexpected active collector context'
    schema.patched_origin = origin_context
    try:
        result = BASE_COLLECT(run_id, agent_path, request)
    finally:
        schema.patched_origin = original
    native = folder / 'native-tools.jsonl'
    events = [json.loads(line) for line in native.read_bytes().splitlines()]
    metadata = json.loads((ROOT / 'runtime' / run_id / 'run.json').read_bytes())
    violations, polls = audit(events, metadata, str(ROOT))
    assert metadata['tool_audit'] == violations and metadata['tool_poll_evidence'] == polls
    origins = []
    for event in events:
        payload = event.get('payload', {})
        if payload.get('type') in {'function_call', 'custom_tool_call'}:
            code = str(payload.get('arguments', payload.get('input', '')))
            if saved.inline_view(code, str(ROOT), run_id) is not None:
                origins.append(payload['call_id'])
    proof = {'version': VERSION, 'run_id': run_id, 'native_sha256': hashlib.sha256(native.read_bytes()).hexdigest(),
             'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'registration_sha256': hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
             'parent_composed_quote_registration_sha256': hashlib.sha256(saved.prior.MANIFEST.read_bytes()).hexdigest(),
             'source_hashes': registration['source_hashes'], 'recognized_alias_origin_ids': origins,
             'transport_violations': violations, 'owned_polls': polls, 'historical_mutation_allowed': False}
    with (folder / (VERSION + '.json')).open('x') as stream:
        json.dump(proof, stream, indent=2)
    return {**result, 'collector_version': VERSION}
