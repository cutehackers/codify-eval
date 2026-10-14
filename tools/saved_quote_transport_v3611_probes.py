"""Boundary and same-native regression checks, with no JavaScript execution."""
import copy
import json
from pathlib import Path
import saved_quote_transport_v3611 as s

ROOT = s.ROOT


def run():
    checks = []
    def check(name, condition):
        checks.append({'name': name, 'pass': bool(condition)})
        if not condition:
            raise AssertionError(name)
    run_id = 'synthetic-saved-quote'
    prefix = f'python3 {ROOT}/tools/agent_io.py --run {run_id} --cmd '
    code = ('const cmd = `printf hello`;\nconst q = "\'" + cmd.replace(/\'/g, "\'\\\\\'\'") + "\'";\n'
            'text(await tools.exec_command({cmd:' + json.dumps(prefix) + '+q,max_output_tokens:6000,yield_time_ms:1000}));')
    check('saved exact quote accepted', s.inline_view(code, str(ROOT), run_id) is not None)
    negatives = {
        'wrong run': code.replace(run_id, 'another-run'),
        'wrong script': code.replace('agent_io.py', 'other.py'),
        'additional shell prefix': code.replace('python3 ', 'echo unsafe; python3 '),
        'wrong quote': code.replace('"\'" + cmd', '"" + cmd'),
        'wrong escape': code.replace('"\'\\\\\'\'"', '"\'"'),
        'wrong suffix': code.replace('+ "\'";', '+ "";'),
        'wrong method': code.replace('.replace(', '.replaceAll('),
        'extra statement': code + '\ntext(await tools.web__run({}));',
        'extra initializer': code.replace('const q =', 'text(await tools.web__run({}));const q ='),
        'extra option': code.replace('max_output_tokens:6000', 'workdir:"/tmp",max_output_tokens:6000'),
        'template interpolation': code.replace('printf hello', '${globalThis.x}'),
        'quote reassignment': code.replace('text(await', 'q = "bad";text(await'),
        'different quoted variable': code.replace('+q,max', '+another,max'),
        'same variable declaration': code.replace('const q =', 'const cmd =').replace('+q,max', '+cmd,max'),
        'invalid identifier': code.replace('const cmd', 'const 123').replace('cmd.replace', '123.replace'),
    }
    for name, value in negatives.items():
        check(name, s.inline_view(value, str(ROOT), run_id) is None)
    def event(kind, cid, **data):
        return {'type':'response_item','payload':{'type':kind,'call_id':cid,**data}}
    def output(cid, value):
        return event('custom_tool_call_output', cid, output=[{'type':'input_text','text':json.dumps(value)}])
    poll = 'text(await tools.write_stdin({session_id:123,max_output_tokens:6000}));'
    events = [event('custom_tool_call','origin',name='exec',input=code),
              output('origin',{'session_id':123,'output':'','wall_time_seconds':1}),
              event('custom_tool_call','poll',name='exec',input=poll),
              output('poll',{'exit_code':0,'output':'done','wall_time_seconds':1})]
    meta={'run_id':run_id,'bootstrap_code':'unrelated'}
    before=copy.deepcopy(events);violations,polls=s.audit(events,meta,str(ROOT))
    check('owned no-input poll',not violations and len(polls)==1)
    check('native evidence unchanged',events==before)
    for name, mutate in [
        ('foreign session',lambda e:e[2]['payload'].update(input=poll.replace('123','999'))),
        ('nonempty input',lambda e:e[2]['payload'].update(input=poll.replace('max_output_tokens:6000','chars:"x"'))),
        ('extra poll tool',lambda e:e[2]['payload'].update(input=poll+'text(await tools.web__run({}));')),
        ('completed origin',lambda e:e[1]['payload'].update(output=[{'type':'input_text','text':json.dumps({'exit_code':0,'output':'','wall_time_seconds':1})}])),
        ('different poll return',lambda e:e[3]['payload'].update(output=[{'type':'input_text','text':json.dumps({'session_id':999,'output':'','wall_time_seconds':1})}])),
    ]:
        modified=copy.deepcopy(events);mutate(modified)
        check(name,bool(s.audit(modified,meta,str(ROOT))[0]))
    stale=copy.deepcopy(events)+[event('custom_tool_call','stale',name='exec',input=poll)]
    check('completed session cannot be polled again',bool(s.audit(stale,meta,str(ROOT))[0]))
    message=copy.deepcopy(events)+[event('function_call','message',name='collaboration.send_message',arguments='{}')]
    check('actual messaging violation retained',len(s.audit(message,meta,str(ROOT))[0])==1)
    selected=json.loads((ROOT/'results/schedule-C0-scope-v3.6.5.json').read_text())['runs']
    comparisons=[]
    for row in selected:
        if (ROOT/'results'/row['run_id']/'native-tools.jsonl').exists():
            comparisons.append(s.compare(row['run_id']))
    changed=[x for x in comparisons if x['before']!=x['after']]
    check('only observed saved quote polls change', [x['run_id'] for x in changed]==['heldout-H03-A-2'])
    actual=changed[0]
    check('actual two polls resolved',len(actual['before'][0])==2 and not actual['after'][0] and len(actual['after'][1])==2)
    boundary=next(x for x in comparisons if x['run_id']=='software-W01-C0-3')
    check('actual W boundary violations retained',boundary['before']==boundary['after'] and len(boundary['after'][0])==2)
    return {'status':'pass','checks':checks,'count':len(checks),'selected_native_records_checked':len(comparisons),
            'changed':changed,'unchanged_run_ids':[x['run_id'] for x in comparisons if x['before']==x['after']],
            'helpers_sha256':{name:s.sha(ROOT/name) for name in ['tools/saved_quote_transport_v3611.py','tools/saved_quote_transport_v3611_probes.py']},
            'actor_reexecuted':False,'original_artifacts_modified':False}


if __name__=='__main__':
    result=run();path=ROOT/'results/saved-quote-transport-qualification-v3.6.11.json'
    with path.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({'path':str(path),'checks':result['count'],'records':result['selected_native_records_checked'],'status':result['status']}))
