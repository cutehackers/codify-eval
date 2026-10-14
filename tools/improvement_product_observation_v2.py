"""Separate proven source compilation defects from incomplete infrastructure.

No incomplete test run is called a behavioral observation. A source compiler
defect can still prove software failure, using both compiler and analyzer evidence
bound to the sealed input. This does not loosen fixture negative qualification.
"""
import json
import re

from improvement_q04_verifier_v5 import COMMANDS, IMAGE, machine
from improvement_fresh_solo_pilot_v1 import complete_observation



def canonical_json(value):
    """Compare the JSON representation used by immutable saved receipts.

    Native machine IDs are integer object keys in memory and string keys after
    JSON serialization. Preserve typed values and reject colliding object keys.
    """
    def unique_pairs(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError('Duplicate serialized object key')
            result[key] = item
        return result
    decoded = json.loads(json.dumps(value, allow_nan=False), object_pairs_hook=unique_pairs)
    return json.dumps(decoded, sort_keys=True, allow_nan=False)

def classify(receipt, expected_tests, sealed_entities, editable_paths):
    unknown = {'complete_software_observation': False, 'behavior_observed': False,
               'behavior_pass': None, 'software_pass': None,
               'classification': 'incomplete_or_infrastructure', 'compiler_defects': []}
    if not isinstance(receipt, dict) or receipt.get('image_id') != IMAGE:
        return unknown
    if (receipt.get('status') != 'completed' or receipt.get('removed') is not True
            or receipt.get('source_unchanged') is not True or receipt.get('cleanup_errors')
            or receipt.get('artifact_errors')
            or canonical_json(receipt.get('source_before'))
            != canonical_json(sealed_entities)):
        return unknown
    checks = receipt.get('checks', [])
    if len(checks) != 3:
        return unknown
    actual_machine = machine(checks[1]['stdout'], expected_tests)
    actual_pass = all(type(check.get('exit_code')) is int and check['exit_code'] == 0
                      for check in checks) and actual_machine['pass']
    if (canonical_json(receipt.get('machine'))
            != canonical_json(actual_machine)
            or type(receipt.get('pass')) is not bool or receipt['pass'] is not actual_pass):
        return unknown
    if complete_observation(receipt, expected_tests):
        return {'complete_software_observation': True, 'behavior_observed': True,
                'behavior_pass': receipt['machine']['pass'], 'software_pass': receipt['pass'],
                'classification': 'completed_tests', 'compiler_defects': []}
    if (len(checks) != 3 or any(check.get('inner_argv') != command
                              or type(check.get('exit_code')) is not int
                              or check['exit_code'] in {124, 137, 143}
                              for check, command in zip(checks, COMMANDS))
            or checks[0]['exit_code'] != 0 or checks[1]['exit_code'] != 1
            or checks[2]['exit_code'] != 1):
        return unknown
    # Complete failed loading lifecycle, with zero user assertions. This excludes
    # truncation, malformed machine records and arbitrary missing test counts.
    loading = machine(checks[1]['stdout'], 0)
    if (not loading['well_formed'] or loading['protocol_errors']
            or loading['missing_end_ids'] or not loading['test_errors']
            or not any('Compilation failed' in error for error in loading['test_errors'])):
        return unknown
    compiler = '\n'.join(loading['test_errors']) + '\n' + checks[1]['stderr']
    analyzer = checks[2]['stdout']
    defects = []
    for path in editable_paths:
        entity = sealed_entities.get(path)
        if not isinstance(entity, dict) or entity.get('kind') != 'file':
            continue
        compiler_pattern = re.compile(r'(?m)(?:^|[ :])' + re.escape(path) + r':([1-9]\d*):([1-9]\d*): Error:')
        analyzer_pattern = re.compile(r'(?m)^\s*error\s+•[^\n]+•\s*' + re.escape(path)
                                      + r':([1-9]\d*):([1-9]\d*)\s+•')
        compiler_positions = {tuple(map(int, m.groups())) for m in compiler_pattern.finditer(compiler)}
        analyzer_positions = {tuple(map(int, m.groups())) for m in analyzer_pattern.finditer(analyzer)}
        overlap = sorted(compiler_positions & analyzer_positions)
        if overlap:
            defects.append({'path': path, 'source_sha256': entity['sha256'],
                            'positions': [list(position) for position in overlap]})
    if not defects:
        return unknown
    return {'complete_software_observation': True, 'behavior_observed': False,
            'behavior_pass': None, 'software_pass': False,
            'classification': 'sealed_source_compilation_failure', 'compiler_defects': defects}
