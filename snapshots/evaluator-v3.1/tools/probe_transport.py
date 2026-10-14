"""Replay recorded transport calls and mutate records without executing payloads."""
import copy
import json
from pathlib import Path

from prepare import ROOT
from transport import audit_transport, wrapper_origin


def events(run_id):
    metadata = json.loads((ROOT / 'runtime' / run_id / 'run.json').read_text())
    source = [json.loads(line) for line in
              (ROOT / 'results' / run_id / 'native-tools.jsonl').read_text().splitlines()]
    return metadata, source


def probe():
    positives = []
    for run_id, count in [('primary-E08-A-2', 1), ('primary-E03-A-2', 2)]:
        metadata, source = events(run_id)
        violations, polls = audit_transport(source, metadata, str(ROOT))
        assert not violations and len(polls) == count, (run_id, violations)
        positives.append({'run_id': run_id, 'polls': polls, 'violations': violations})
    metadata, source = events('primary-E08-A-2')
    origin = positives[0]['polls'][0]['origin_call_id']
    poll = positives[0]['polls'][0]['poll_call_id']
    negatives = []
    for name in ['unknown_session', 'nonempty_stdin', 'mixed_poll', 'closed_session_reuse',
                 'nested_spoof_origin', 'host_extra_origin', 'malformed_poll_output',
                 'template_host_substitution', 'contradictory_terminal_origin']:
        modified = copy.deepcopy(source)
        for item in modified:
            payload = item['payload']
            kind, call_id = payload.get('type'), payload.get('call_id')
            if kind == 'custom_tool_call' and call_id == poll:
                if name == 'unknown_session':
                    payload['input'] = payload['input'].replace('8588', '99999')
                elif name == 'nonempty_stdin':
                    payload['input'] = payload['input'].replace('chars:""', 'chars:"injected"')
                elif name == 'mixed_poll':
                    payload['input'] += 'text(await tools.exec_command({cmd:"pwd"}));'
            if kind == 'custom_tool_call' and call_id == origin:
                if name == 'host_extra_origin':
                    payload['input'] += 'text(await tools.exec_command({cmd:"pwd"}));'
                elif name == 'template_host_substitution':
                    payload['input'] = payload['input'].replace("--cmd '", '--cmd \\"$(host_command)\\"\'')
            if kind == 'custom_tool_call_output' and call_id == origin and name in {
                    'nested_spoof_origin', 'contradictory_terminal_origin'}:
                for part in payload['output']:
                    if part.get('text', '').startswith('{'):
                        value = json.loads(part['text'])
                        if name == 'nested_spoof_origin':
                            value.pop('session_id', None)
                            value['output'] = json.dumps({'session_id': 8588})
                        else:
                            value['exit_code'] = 0
                        part['text'] = json.dumps(value)
            if kind == 'custom_tool_call_output' and call_id == poll and name == 'malformed_poll_output':
                payload['output'] = [{'type': 'input_text', 'text': 'no provenance'}]
        if name == 'closed_session_reuse':
            item = copy.deepcopy(next(item for item in modified if
                                      item['payload'].get('call_id') == poll and
                                      item['payload']['type'] == 'custom_tool_call'))
            item['payload']['call_id'] = 'closed_again'
            modified.append(item)
        violations, _ = audit_transport(modified, metadata, str(ROOT))
        assert violations, name
        negatives.append({'case': name, 'rejected': True, 'violations': len(violations)})
    # Both ordinary ways of escaping a quote are literal shell arguments.
    prefix = f'python3 {ROOT}/tools/agent_io.py --run primary-E03-A-2 --cmd '
    for argument in ["'before'\\''after'", "'before'\"'\"'after'"]:
        code = 'text(await tools.exec_command({cmd:' + json.dumps(prefix + argument) + '}));'
        assert wrapper_origin(code, str(ROOT), 'primary-E03-A-2')
    for argument in ['"$(host_command)"', "'safe'; host_command", "'safe'$(host_command)"]:
        code = 'text(await tools.exec_command({cmd:' + json.dumps(prefix + argument) + '}));'
        assert not wrapper_origin(code, str(ROOT), 'primary-E03-A-2')
        negatives.append({'case': 'direct_host_expression:' + argument, 'rejected': True})
    return {'actual_positive_records': positives, 'synthetic_negative_controls': negatives,
            'note': 'No payload executed. Audit probes are not model performance.'}


if __name__ == '__main__':
    result = probe()
    destination = ROOT / 'results' / 'transport-poll-probes-v4.json'
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'actual_positive_runs': len(result['actual_positive_records']),
                      'negative_controls_rejected': len(result['synthetic_negative_controls'])}))
