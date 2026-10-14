"""Terminal output/session closure counterexamples for the v9 chronology fix."""
import copy
import json
from prepare import ROOT
from improvement_dialogue_native_v10 import audit


def run():
    code = 'text(await tools.exec_command({"cmd":"cat /approved/request.txt","max_output_tokens":6500}));'
    meta = {'run_id': 'probe', 'bootstrap_code': code}
    def event(kind, call_id, **data):
        return {'timestamp': '2026-10-11T00:00:01Z', 'type': 'response_item',
                'payload': {'type': kind, 'call_id': call_id, **data}}
    call = event('custom_tool_call', 'bootstrap', name='exec', input=code)
    def output(call_id, value):
        return event('custom_tool_call_output', call_id, output=json.dumps(value))
    def failed(events):
        return bool(audit(events, meta, str(ROOT), require_closed=True))
    terminal = output('bootstrap', {'exit_code': 0, 'output': 'request'})
    yielded = output('bootstrap', {'session_id': 77, 'output': ''})
    poll = event('custom_tool_call', 'poll', name='exec', input='text(await tools.write_stdin({session_id:77,chars:""}));')
    end = output('poll', {'exit_code': 0, 'output': 'request'})
    cases = [
        ('missing bootstrap result', failed([call])),
        ('unknown bootstrap result', failed([call, output('bootstrap', {'output': 'unknown'})])),
        ('untyped bootstrap exit', failed([call, output('bootstrap', {'exit_code': 'zero', 'output': 'request'})])),
        ('open bootstrap session', failed([call, yielded])),
        ('completed bootstrap accepted', not failed([call, terminal])),
        ('owned bootstrap poll closes', not failed([call, yielded, poll, end])),
        ('live observation stays permissible', not audit([call], meta, str(ROOT))),
        ('missing poll result', failed([call, yielded, poll])),
        ('duplicate terminal output', failed([call, terminal, copy.deepcopy(terminal)])),
    ]
    assert all(passed for _, passed in cases), cases
    return {'status': 'pass', 'count': len(cases), 'cases': cases,
            'scope': 'Pure terminal closure only; no actual v9 model execution or software qualification'}


if __name__ == '__main__':
    path = ROOT / 'results/improvement-v1/dialogue-native-v10-terminal-probes.json'
    value = run()
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
    print(json.dumps({'status': value['status'], 'count': value['count']}))
