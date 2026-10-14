"""Supplementary unchanged-code grading; original comparison stays immutable.

Only output-size requests are warnings. Native authority, capability, scope,
integration and source fences remain mandatory. No product actors or retries.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import shutil
import time

import improvement_optional_comparison_observer_amendment_v1 as amendment
import improvement_optional_result_classification_v1 as classifier

original = amendment.original.normal_close.original
routes = original.audit.routes
require = original.require


@contextmanager
def output_warnings(warnings):
    literal_before, poll_before = routes.literal_command, routes.poll

    def literal(code):
        require(isinstance(code, str) and len(code) <= 1048576, 'Bounded literal code required')
        pattern = r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*("(?:\\.|[^"\\])*")(.*?)\}\s*\)\s*\)\s*;?'
        match = re.fullmatch(pattern, code.strip(), re.S)
        require(match is not None, 'Sole literal broker wrapper required')
        command = routes.strict.decoded(match.group(1))
        rest, seen = match.group(2).strip(), set()
        while rest and rest != ',':
            option = re.match(r',\s*("?(?:yield_time_ms|max_output_tokens)"?)\s*:\s*(0|[1-9][0-9]*)(?=\s*(?:,|$))', rest)
            require(option is not None, 'Unsupported infrastructure option')
            key, value = option.group(1).strip('"'), int(option.group(2))
            require(key not in seen, 'Duplicate infrastructure option')
            if key == 'yield_time_ms':
                require(value <= 30000, 'Infrastructure option out of range')
            elif value > 20000:
                warnings.append({'kind': 'exec_output_request', 'requested': value,
                                 'code_sha256': hashlib.sha256(code.encode()).hexdigest()})
            seen.add(key)
            rest = rest[option.end():].strip()
        return command

    def poll(code):
        match = re.fullmatch(r'text\s*\(\s*await\s+tools\.write_stdin\s*\(\s*(\{[^{}]*\})\s*\)\s*\)\s*;?', code.strip(), re.S)
        if match is None:
            return None
        body = re.sub(r'(?<!["\w])([A-Za-z_]\w*)\s*:', r'"\1":', match.group(1))
        body = re.sub(r',\s*\}', '}', body.replace("''", '""'))
        options = routes.strict.decoded(body)
        require(isinstance(options, dict) and set(options) <= {'session_id', 'chars', 'yield_time_ms', 'max_output_tokens'}
                and type(options.get('session_id')) is int and options['session_id'] > 0
                and options.get('chars', '') == '', 'Empty owned poll required')
        for key in ('yield_time_ms', 'max_output_tokens'):
            if key in options:
                value = options[key]
                require(type(value) is int and value >= 0, 'Poll infrastructure option out of range')
                if key == 'yield_time_ms':
                    require(value <= 300000, 'Poll infrastructure option out of range')
                elif value > 20000:
                    warnings.append({'kind': 'poll_output_request', 'requested': value,
                                     'code_sha256': hashlib.sha256(code.encode()).hexdigest()})
        return options

    routes.literal_command, routes.poll = literal, poll
    try:
        yield
    finally:
        routes.literal_command, routes.poll = literal_before, poll_before


def assess(row, supplemental_seconds=300):
    amendment.admission(row)
    review_path = amendment.original.BASE / 'output-limit-quality-assessment-prelaunch-review-v1.json'
    review = json.loads(review_path.read_bytes())
    require(review['verdict'] == 'pass' and review['issues'] == [], 'Independent supplementary grader review required')
    require(str(Path(__file__).resolve().relative_to(original.ROOT)) in review['source_entities'],
            'Exact supplementary helper must be reviewed')
    for category in ('source_entities', 'evidence_entities'):
        for name, pin in review[category].items():
            amendment.original.control.reviewed_entity(original.ROOT / name, pin)
    require(type(supplemental_seconds) is int and 1 <= supplemental_seconds <= 300,
            'Separate bounded supplemental grading budget required')
    folder = original.ROOT / 'runtime' / row['run_id']
    old_path = folder / 'completed-failure-close-v2/outcome.json'
    old_raw = old_path.read_bytes()
    old = json.loads(old_raw)
    require(old['row'] == row and old['status'] == 'preserved_completed_failure'
            and old['owned_cleanup_verified'] is True
            and old['first_error'] == {'type': 'ValueError', 'message': 'Infrastructure option out of range'},
            'Only originally completed output-limit failures with owned cleanup are eligible')
    preserved = folder / 'completed-failure-close-v2'
    terminal = json.loads((preserved / 'terminal-proof.json').read_bytes())
    commitment = terminal['original_no_more_delivery_commitment']
    coordinator_source = preserved / 'coordinator.jsonl'
    parent_raw = coordinator_source.read_bytes()
    require(len(parent_raw) == commitment['parent_bytes']
            and hashlib.sha256(parent_raw).hexdigest() == commitment['parent_sha256'],
            'Original authenticated terminal coordinator prefix required')
    inventory_call_id = commitment['inventory_call_id']
    output = folder / 'supplemental-quality-v1'
    output.mkdir()
    started = time.time()
    result = {'row': row, 'original_outcome_sha256': hashlib.sha256(old_raw).hexdigest(),
              'original_protocol_error': old['first_error'], 'original_usage': old['usage'],
              'original_whole_observed_seconds': old['whole_observed_seconds'],
              'supplemental_started_at': started, 'supplemental_budget_seconds': supplemental_seconds,
              'software_pass': None, 'classification': 'evaluation_error', 'warnings': [],
              'original_comparison_unchanged': True, 'comparison_admitted': False,
              'superiority_proven': False, 'product_model_allocations': 0, 'first_error': None}
    original.atomic_json(output / 'intent.json', result, exclusive=True)
    try:
        with amendment.observer.lifecycle_decoder(), output_warnings(result['warnings']):
            data = original.evidence(folder, coordinator_source, inventory_call_id, output)
        # The same original call can be audited again for integration ordering.
        result['warnings'] = list({json.dumps(warning, sort_keys=True): warning
                                   for warning in result['warnings']}.values())
        original.atomic_json(output / 'audit.json', data['proof'], exclusive=True)
        require(bool(result['warnings']), 'Actual output request warning required')

        def fence():
            require(old_path.read_bytes() == old_raw, 'Original outcome changed')
            require(all(original.capture(data['locators'][path], 256 * 1024 * 1024) == raw
                        for path, raw in data['raws'].items()), 'Original member source changed')
            require(original.runtime.registry.read(folder / 'registry') == json.loads(
                (output / 'dispatch-inputs.json').read_bytes())['state'], 'Registry changed')
            require(original.verifier.tree(export) == export_before, 'Stopped source changed')

        events = [original.audit.inventory.decoded(p.read_bytes())
                  for p in sorted((folder / 'events').glob('*.json'))]
        snapshots = [e for e in events if e.get('op') == 'stopped_snapshot' and e.get('job') == 'root']
        require(snapshots and snapshots[-1]['scope_error'] is None, 'Stopped source scope guard required')
        export_path = Path(snapshots[-1]['export'])
        require(not export_path.is_symlink(), 'Real stopped source required')
        export = export_path.resolve()
        require(export.is_relative_to(folder / 'snapshots'), 'Owned stopped source required')
        export_before = original.verifier.tree(export)
        require(export_before == snapshots[-1]['inventory']['source_entities'],
                'Exact original stopped inventory, including entity kinds and modes, required')
        fence()
        source = output / 'combined-source'
        shutil.copytree(export, source)
        require(original.verifier.tree(source) == export_before, 'Exact stopped source copy required')
        acceptance = amendment.original.inputs.case_directory(row) / 'private/acceptance_test.dart'
        require(acceptance.is_file() and not acceptance.is_symlink(), 'Original frozen private acceptance required')
        target = source / 'test/author_acceptance_test.dart'
        require(not target.exists(), 'Private grader destination collision')
        shutil.copyfile(acceptance, target)
        result['stopped_source_tree'] = export_before
        result['acceptance_sha256'] = hashlib.sha256(acceptance.read_bytes()).hexdigest()
        receipt = original.verifier.verify(source, output / 'combined-verifier',
                                           started + supplemental_seconds, expected_tests=24)
        result['verification'] = receipt
        result.update(classifier.classify(json.loads(json.dumps(receipt)), 24))
        fence()
        require(receipt.get('removed') is True, 'Supplemental grader cleanup incomplete')
        result['owned_cleanup_verified'] = True
    except BaseException as error:
        result['first_error'] = {'type': type(error).__name__, 'message': str(error)}
        result['software_pass'] = None
        result['classification'] = 'evaluation_error'
    result['supplemental_finished_at'] = time.time()
    result['supplemental_wall_seconds'] = result['supplemental_finished_at'] - started
    original.atomic_json(output / 'outcome.json', result, exclusive=True)
    return result
