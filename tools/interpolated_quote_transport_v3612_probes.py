"""Uniform same-native and closed-grammar checks; no JavaScript execution."""
import copy
import hashlib
import json
import shlex
from pathlib import Path
import interpolated_quote_transport_v3612 as s


def run():
    checks=[]
    def check(n,v):
        checks.append({'name':n,'pass':bool(v)})
        if not v:raise AssertionError(n)
    root=str(s.ROOT);rid='synthetic-interpolated'
    code=('const source = `one`;const tests = `two`;'
          'const command = `printf ${JSON.stringify(source)} ${JSON.stringify(tests)}`;'
          'const quote = s => "\'" + s.replaceAll("\'", "\'\\\\\'\'") + "\'";'
          'text(await tools.exec_command({cmd:'+json.dumps(f'python3 {root}/tools/agent_io.py --run {rid} --cmd ')+'+quote(command),max_output_tokens:6000,yield_time_ms:1000}));')
    v=s.resolved_command(code,root,rid);check('constant string substitutions resolved',v and v['command']=='printf "one" "two"')
    negatives={
        'arbitrary interpolation':code.replace('JSON.stringify(source)','globalThis.x'),
        'unknown string value':code.replace('JSON.stringify(source)','JSON.stringify(unknown)'),
        'nested side effect':code.replace('JSON.stringify(source)','JSON.stringify(tools.web__run({}))'),
        'plain variable substitution':code.replace('JSON.stringify(source)','source'),
        'missing substitution':code.replace('${JSON.stringify(tests)}',''),
        'duplicate substitution':code.replace('JSON.stringify(tests)','JSON.stringify(source)'),
        'data template interpolation':code.replace('`one`','`${globalThis.x}`'),
        'computed source':code.replace('`one`','load("one")'),
        'extra statement':code+'text(await tools.web__run({}));',
        'extra tool initializer':code.replace('const quote','text(await tools.web__run({}));const quote'),
        'wrong script':code.replace('agent_io.py','other.py'),
        'wrong run':code.replace(rid,'foreign'),
        'extra shell prefix':code.replace('python3 ','echo unsafe; python3 '),
        'extra exec option':code.replace('max_output_tokens:6000','workdir:"/tmp",max_output_tokens:6000'),
        'wrong quote function argument':code.replace('s.replaceAll','other.replaceAll'),
        'wrong quote replacement':code.replace('"\'\\\\\'\'"','"\'"'),
        'wrong function invoked':code.replace('+quote(command)','+other(command)'),
        'reassigned command':code.replace('const quote','command="unsafe";const quote'),
        'shadow JSON':code.replace('source','JSON'),
        'shadow tools':code.replace('source','tools'),
        'shadow text':code.replace('source','text'),
        'duplicate binding':code.replace('const tests','const source'),
        'reserved identifier':code.replace('source','await'),
        'wrong method':code.replace('replaceAll','replace'),
    }
    for n,c in negatives.items():check(n,s.resolved_command(c,root,rid) is None)
    check('cooked supported escapes',s.cooked('a\\n\\t\\u0041\\x42\\\\\\`\\$')=='a\n\tAB\\`$')
    for n,b in [('unresolved cook','${x}'),('unknown escape','\\q'),('invalid unicode','\\uZZZZ'),('surrogate','\\uD800'),('numeric escape','\\07')]:
        try:s.cooked(b);ok=False
        except ValueError:ok=True
        check(n,ok)
    def event(t,c,**k):return {'type':'response_item','payload':{'type':t,'call_id':c,**k}}
    def out(c,v):return event('custom_tool_call_output',c,output=[{'type':'input_text','text':json.dumps(v)}])
    poll='text(await tools.write_stdin({session_id:123,chars:"",max_output_tokens:6000}));'
    events=[event('custom_tool_call','origin',name='exec',input=code),out('origin',{'session_id':123,'output':'','wall_time_seconds':1}),event('custom_tool_call','poll',name='exec',input=poll),out('poll',{'exit_code':0,'output':'done','wall_time_seconds':1})];meta={'run_id':rid,'bootstrap_code':'unrelated'};original=copy.deepcopy(events)
    flags,polls=s.audit(events,meta,root);check('owned empty-input poll accepted',not flags and len(polls)==1);check('native unchanged',events==original)
    for n,mutate in [('foreign SID',lambda e:e[2]['payload'].update(input=poll.replace('123','999'))),('nonempty stdin',lambda e:e[2]['payload'].update(input=poll.replace('chars:""','chars:"x"'))),('extra poll tool',lambda e:e[2]['payload'].update(input=poll+'text(await tools.web__run({}));')),('completed origin',lambda e:e[1].update(payload=out('origin',{'exit_code':0,'output':'done','wall_time_seconds':1})['payload'])),('foreign returned SID',lambda e:e[3].update(payload=out('poll',{'session_id':999,'output':'','wall_time_seconds':1})['payload']))]:
        e=copy.deepcopy(events);mutate(e);check(n,bool(s.audit(e,meta,root)[0]))
    e=copy.deepcopy(events)+[event('custom_tool_call','stale',name='exec',input=poll)];check('retired session rejected',bool(s.audit(e,meta,root)[0]))
    e=copy.deepcopy(events)+[event('function_call','message',name='collaboration.send_message',arguments='{}')];check('messaging violation retained',len(s.audit(e,meta,root)[0])==1)
    rows=json.loads((s.ROOT/'results/schedule-C0-scope-v3.6.5.json').read_text())['runs'];comparisons=[s.compare(x['run_id']) for x in rows if (s.ROOT/'results'/x['run_id']/'native-tools.jsonl').exists()];changed=[x for x in comparisons if x['before']!=x['after']]
    check('all 186 selected natives compared',len(comparisons)==186);check('only observed H04 presentation changes',[x['run_id'] for x in changed]==['heldout-H04-A-2']);check('one flag becomes owned poll',len(changed[0]['before'][0])==1 and not changed[0]['after'][0] and len(changed[0]['after'][1])==len(changed[0]['before'][1])+1)
    boundary=next(x for x in comparisons if x['run_id']=='software-W01-C0-3');check('two actual boundary violations unchanged',boundary['before']==boundary['after'] and len(boundary['after'][0])==2)
    actual=s.ROOT/'results/heldout-H04-A-2/native-tools.jsonl';records=[json.loads(x) for x in actual.read_text().splitlines()];origin=next(x['payload'] for x in records if x.get('payload',{}).get('call_id')=='call_927b850e79b04428a1db3b6da1c71bb7' and x['payload']['type']=='custom_tool_call');resolved=s.resolved_command(origin['input'],root,'heldout-H04-A-2')
    review=json.loads((s.ROOT/'results/heldout-H04-A-2-interpolated-origin-classification-review-2026-10-11.json').read_text());native=Path(review['native_source']);raw=[json.loads(x) for x in native.read_text().splitlines()];items=[x['payload']['item'] for x in raw if x['type']=='event_msg' and x['payload'].get('type')=='item_completed' and x['payload'].get('item',{}).get('type')=='CommandExecution' and x['payload']['item'].get('process_id')=='29285'];check('exact one authoritative process event',len(items)==1)
    argv=items[0]['command'];check('actual shell command equals reconstruction',argv==['/bin/zsh','-lc',resolved['host']]);check('exact six scoped host argv',shlex.split(resolved['host'])==['python3',root+'/tools/agent_io.py','--run','heldout-H04-A-2','--cmd',resolved['command']])
    return {'status':'pass','checks':checks,'count':len(checks),'selected_native_records_checked':len(comparisons),'changed':changed,'unchanged_run_ids':[x['run_id'] for x in comparisons if x['before']==x['after']],'helpers_sha256':{n:s.sha(s.ROOT/n) for n in ['tools/interpolated_quote_transport_v3612.py','tools/interpolated_quote_transport_v3612_probes.py']},'actor_reexecuted':False,'original_artifacts_modified':False,'javascript_executed':False}


if __name__=='__main__':
    v=run();p=s.ROOT/'results/interpolated-quote-transport-qualification-v3.6.12.json'
    with p.open('x') as f:json.dump(v,f,indent=2)
    print(json.dumps({'path':str(p),'checks':v['count'],'records':v['selected_native_records_checked'],'status':v['status']}))
