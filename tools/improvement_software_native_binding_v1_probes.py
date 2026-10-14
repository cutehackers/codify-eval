"""Actual native join plus single-field tamper probes; no actor execution."""
import copy
import hashlib
import json
from pathlib import Path
from improvement_software_native_binding_v1 import binding, parse

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'results/improvement-v1/software-native-binding-v1-observed-probe.json'
OUT = ROOT / 'results/improvement-v1/software-native-binding-v1-negative-probes.json'

def encode(events):
    return b''.join(json.dumps(e).encode() + b'\n' for e in events)

def main():
    assert not OUT.exists()
    report = json.loads(REPORT.read_text())
    assert report['status'] == 'observed_parent_child_binding'
    assert hashlib.sha256((ROOT / 'tools/improvement_software_native_binding_v1.py').read_bytes()).hexdigest() == report['module_sha256']
    raw = {}
    for role in ('parent', 'child'):
        prefix = report[role + '_prefix']
        raw[role] = Path(report['source_paths'][role]).read_bytes()[:prefix['bytes']]
        assert hashlib.sha256(raw[role]).hexdigest() == prefix['sha256']
    ps, _ = parse(raw['parent']); cs, _ = parse(raw['child'])
    call_id = report['spawn_call_id']
    results = []
    for name in ('wrong_parent_uuid', 'wrong_model', 'wrong_request_token', 'missing_spawn_receipt', 'reused_context', 'request_before_context', 'partial_native_prefix'):
        p, c = copy.deepcopy(ps), copy.deepcopy(cs)
        if name == 'wrong_parent_uuid': c[0]['payload']['parent_thread_id'] = 'another-parent'
        if name == 'wrong_model':
            next(e for e in c if e['type'] == 'turn_context')['payload']['model'] = 'gpt-6-sol'
        if name == 'wrong_request_token':
            req = next(e['payload'] for e in c if e.get('payload', {}).get('type') == 'agent_message' and e['payload'].get('author') == '/root')
            next(b for b in req['content'] if b['type'] == 'encrypted_content')['encrypted_content'] = 'gAAAAAincorrect'
        if name == 'missing_spawn_receipt':
            p = [e for e in p if not (e.get('payload', {}).get('call_id') == call_id and e['payload'].get('type') == 'function_call_output')]
        if name == 'reused_context':
            event = next(e for e in p if e.get('payload', {}).get('call_id') == call_id and e['payload'].get('type') == 'function_call')
            args = json.loads(event['payload']['arguments']); args['fork_turns'] = 'all'; event['payload']['arguments'] = json.dumps(args)
        if name == 'request_before_context':
            index = next(i for i,e in enumerate(c) if e.get('payload', {}).get('type') == 'agent_message' and e['payload'].get('author') == '/root')
            e = c.pop(index); c.insert(1, e)
        a, b = encode(p), encode(c)
        if name == 'partial_native_prefix': b = b[:-1]
        try:
            binding(a, b, '/root', '/root/improvement_d01_c9_1')
        except ValueError as error:
            results.append({'case': name, 'rejected': True, 'reason': str(error)})
        else: results.append({'case': name, 'rejected': False})
    result = {'status': 'pass' if all(r['rejected'] for r in results) else 'fail',
        'actual_positive_probe': str(REPORT.relative_to(ROOT)), 'tamper_probes': results,
        'actor_reexecuted': False, 'source_records_mutated': False, 'runtime_qualified': False,
        'complete_final_cost': False, 'superiority_proven': False,
        'source_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (REPORT, Path(__file__), ROOT / 'tools/improvement_software_native_binding_v1.py', ROOT / 'tools/dialogue_schema.py')}}
    with OUT.open('x') as f: json.dump(result, f, indent=2)
    print(json.dumps(result))

if __name__ == '__main__': main()
