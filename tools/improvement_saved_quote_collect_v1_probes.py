"""Pure origin/ownership probes over preserved actual native evidence."""
import copy
import hashlib
import json
from unittest.mock import patch

import improvement_saved_quote_collect_v1 as adapter
import saved_quote_transport_v3611 as saved
import transport
from prepare import ROOT

RUN = 'control-probe-candidate-C9-P01-v1-P01-C9-1'


def run():
    saved.verify_registration()
    source = ROOT / 'results' / RUN / 'native-tools.jsonl'
    raw = source.read_bytes()
    events = [json.loads(line) for line in raw.splitlines()]
    meta = json.loads((ROOT / 'runtime' / RUN / 'run.json').read_bytes())
    originals = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in [source, ROOT / 'runtime' / RUN / 'run.json',
                              ROOT / 'results' / RUN / 'grade.json', ROOT / 'results' / RUN / 'turns.json']}
    native = copy.deepcopy(events)
    initial_origin = transport.wrapper_origin
    initial_context = adapter.schema.patched_origin
    checks = []

    def check(name, condition):
        assert condition, name
        checks.append(name)

    before = saved.baseline(events, meta, str(ROOT))
    after = adapter.audit(events, meta, str(ROOT))
    check('actual original false positive preserved', len(before[0]) == 1)
    check('actual alias and owned terminal poll qualify', not after[0] and len(after[1]) == 1)
    check('existing qualified classifier agrees', after == saved.audit(events, meta, str(ROOT)))
    origin = next(event['payload'] for event in events
                  if saved.inline_view(str(event.get('payload', {}).get('input', '')), str(ROOT), RUN))
    code = origin['input']
    mutations = {
        'appended tool': code + 'text(await tools.exec_command({cmd:"true"}));',
        'dynamic payload': code.replace('const cmd = `', 'const cmd = `${outside}'),
        'wrong run': code.replace('--run ' + RUN, '--run another'),
        'host command appended to prefix': code.replace('--cmd ', '--cmd ; touch /tmp/outside '),
        'alias reassignment': code.replace('text(await', 'quoted = "unsafe";text(await'),
        'other alias': code.replace('+ quoted', '+ other').replace('+quoted', '+other'),
        'quote operation altered': code.replace(".replace(/'/g,", ".replace(/x/g,"),
        'extra property': code.replace('max_output_tokens:', 'workdir:"/tmp",max_output_tokens:'),
    }
    for name, changed in mutations.items():
        check(name, changed != code and saved.inline_view(changed, str(ROOT), RUN) is None)
    origin_id = origin['call_id']
    yielded = next(event for event in events if event.get('payload', {}).get('call_id') == origin_id
                   and event['payload']['type'] in {'custom_tool_call_output', 'function_call_output'})
    sid = list(transport.result_objects(yielded['payload']))[0]['session_id']
    polled = next(event for event in events if event.get('payload', {}).get('type') in {'custom_tool_call', 'function_call'}
                  and transport.poll_options(str(event['payload'].get('input', '')))
                  and transport.poll_options(event['payload']['input'])['session_id'] == sid)
    for name, change in [('foreign poll', lambda code: code.replace(str(sid), str(sid + 1))),
                         ('nonempty stdin', lambda code: code.replace('chars:""', 'chars:"x"'))]:
        altered = copy.deepcopy(events)
        item = next(event for event in altered if event['payload'].get('call_id') == polled['payload']['call_id']
                    and event['payload']['type'] == polled['payload']['type'])
        previous = item['payload']['input']
        item['payload']['input'] = change(previous)
        check(name, item['payload']['input'] != previous and bool(adapter.audit(altered, meta, str(ROOT))[0]))
    def fake_collect(*args, **kwargs):
        with adapter.schema.patched_origin():
            assert transport.wrapper_origin is saved.wrapper_origin
            assert not adapter.schema.collect.audit_transport(events, meta, str(ROOT))[0]
        raise RuntimeError('forced collection error')
    with patch.object(adapter, 'verify', return_value={}), patch.object(adapter, 'BASE_COLLECT', fake_collect):
        try:
            adapter.qualified_collect('prospective-pure-probe-no-run', '/root/nonexistent')
        except RuntimeError as error:
            check('collector exception retained', str(error) == 'forced collection error')
        else:
            raise AssertionError('Exception suppressed')
    check('all global classifier functions restored', transport.wrapper_origin is initial_origin and adapter.schema.patched_origin is initial_context)
    check('native inputs unchanged', events == native and source.read_bytes() == raw)
    check('historical evidence hashes unchanged', all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha for name, sha in originals.items()))
    return {'status': 'pass', 'checks': checks, 'count': len(checks), 'historical_source_hashes': originals,
            'source_hashes': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                             for name in ['tools/improvement_saved_quote_collect_v1.py', 'tools/improvement_saved_quote_collect_v1_probes.py']},
            'actual_model_reexecuted': False, 'historical_grade_promoted': False,
            'qualification': 'pure prospective adapter plus existing actual receipt audit; no forward collection yet'}


if __name__ == '__main__':
    value = run()
    destination = ROOT / 'results/improvement-v1/saved-quote-collector-probes-v1.json'
    with destination.open('x') as stream:
        json.dump(value, stream, indent=2)
    print(json.dumps({'status': value['status'], 'checks': value['count'], 'path': str(destination)}))
