"""Pure closed-grammar and preserved-native probes; no historical mutation."""
import copy
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import improvement_composed_quote_origin_v1 as origin
import improvement_composed_quote_collect_v1 as adapter
from prepare import ROOT

RUN='control-probe-P02-pilot-v2-P02-A-1'
CALL='call_ADK3o2aFAgFaAEcHFLdRztgS'
NODE=Path('/Users/junhyounglee/.hermes/node/bin/node')


def run():
    folder=ROOT/'results'/RUN;raw=(folder/'native-tools.jsonl').read_bytes()
    events=[json.loads(line) for line in raw.splitlines()]
    metadata=json.loads((ROOT/'runtime'/RUN/'run.json').read_bytes())
    code=next(e['payload']['input'] for e in events if e.get('payload',{}).get('type')=='custom_tool_call' and e['payload']['call_id']==CALL)
    checks=[]
    def check(name,passed):
        assert passed,name
        checks.append({'name':name,'pass':True})
    view=origin.project(code,str(ROOT),RUN)
    check('actual_constant_composition_recognized',view is not None and origin.wrapper_origin(code,str(ROOT),RUN))
    command_json=view.split('"cmd":',1)[1].split(',max_output_tokens:',1)[0]
    argv=shlex.split(json.loads(command_json));journal=[json.loads(l) for l in (ROOT/'runtime'/RUN/'commands.jsonl').read_bytes().splitlines()]
    check('actual_projected_command_exactly_one_journal_match',sum(row['command']==argv[-1] for row in journal)==1)
    check('actual_argv_exact_six_scoped_arguments',argv[:5]==['python3',str(ROOT/'tools/agent_io.py'),'--run',RUN,'--cmd'] and len(argv)==6)
    before=(folder/'native-tools.jsonl').read_bytes()
    violations,polls=adapter.audit(events,metadata,str(ROOT))
    check('actual_owned_poll_recognized',not violations and len(polls)==1 and polls[0]['session_id']==84386 and polls[0]['origin_call_id']==CALL)
    check('raw_native_unmodified',before==(folder/'native-tools.jsonl').read_bytes())
    for name,changed in [
        ('wrong_run',code.replace('--run '+RUN,'--run wrong')),
        ('wrong_script',code.replace('/tools/agent_io.py','/tools/other.py')),
        ('host_command_prefix',code.replace('python3 '+str(ROOT)+'/tools/agent_io.py','cat '+str(ROOT)+'/tools/agent_io.py')),
        ('unknown_stringify_binding',code.replace('JSON.stringify(codec)','JSON.stringify(unknown)')),
        ('arbitrary_json_method',code.replace('JSON.stringify(codec)','JSON.parse(codec)')),
        ('dynamic_template',code.replace('const codec = `','const codec = `${process.env.HOME}')),
        ('dynamic_quote_body',code.replace('s.replace(/\'/g,','process.env.HOME.replace(/\'/g,')),
        ('wrong_escape',code.replace('s.replace(/\'/g,','s.replace(/x/g,')),
        ('additional_tool',code+'\nawait tools.web__run({});'),
        ('mutable_binding',code.replace('const command=','let command=')),
        ('shadowed_global',code.replace('const codec =','const JSON =')),
        ('binding_redefinition',code.replace('const processor =','const codec =')),
        ('unapproved_exec_option',code.replace('max_output_tokens:6000','workdir:"/tmp",max_output_tokens:6000')),
    ]:
        check(name,changed!=code and origin.project(changed,str(ROOT),RUN) is None)
    check('unsupported_escape_closed',origin.template_value(r'\n') is None)
    check('surrogate_closed',origin.template_value(chr(0xd800)) is None)
    check('source_size_bounded',origin.project('x'*1048577,str(ROOT),RUN) is None)
    changed=copy.deepcopy(events)
    for event in changed:
        p=event['payload']
        if p.get('type')=='custom_tool_call' and 'tools.write_stdin' in p.get('input',''):
            p['input']=p['input'].replace('session_id:84386','session_id:84387')
    check('wrong_session_rejected',bool(adapter.audit(changed,metadata,str(ROOT))[0]))
    changed=copy.deepcopy(events)
    for event in changed:
        p=event['payload']
        if p.get('type')=='custom_tool_call' and 'tools.write_stdin' in p.get('input',''):
            p['input']=p['input'].replace('session_id:84386','session_id:84386,chars:"input"')
    check('nonempty_stdin_rejected',bool(adapter.audit(changed,metadata,str(ROOT))[0]))
    # Execute only fixed, root-authored synthetic expressions, never actual actor code.
    synthetic='const alpha = `a\'\\\\b\n한국어`;\nconst beta = `second`;\nconst command="printf "+JSON.stringify(alpha)+" "+JSON.stringify(beta);\nconst quote=s=>"\'"+s.replace(/\'/g,"\'\\\\\'\'")+"\'";\ntext(await tools.exec_command({cmd:'+json.dumps(f'python3 {ROOT}/tools/agent_io.py --run {RUN} --cmd ')+'+quote(command),max_output_tokens:6000,yield_time_ms:1000}));'
    projected=origin.project(synthetic,str(ROOT),RUN)
    check('authored_synthetic_projected',projected is not None)
    setup='const text=x=>{};const tools={exec_command:async x=>{console.log(JSON.stringify(x));return null;}};'
    def execute(value):
        result=subprocess.run([str(NODE),'--input-type=module','-e',setup+value],capture_output=True,text=True,timeout=10)
        result.check_returncode();return json.loads(result.stdout)
    check('authored_js_semantics_equals_static_projection',execute(synthetic)==execute(projected))
    names=[Path(__file__),Path(origin.__file__),Path(adapter.__file__),NODE,folder/'native-tools.jsonl',ROOT/'runtime'/RUN/'commands.jsonl',ROOT/'runtime'/RUN/'run.json',folder/'grade.json',ROOT/'results/improvement-v1/P02-A1-poll-admissibility-review-v1.json']
    return {'status':'pass','count':len(checks),'checks':checks,'source_hashes':{str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in names},'limits':['Actual actor code statically projected, never evaluated','Only root-authored fixed synthetic JS executed with dummy tools','Original frozen audit, grade and input bytes remain unchanged','Forward collector runtime not yet exercised']}


if __name__=='__main__':
    result=run();path=ROOT/'results/improvement-v1/composed-quote-collector-probes-v3.json'
    with path.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'checks':result['count']}))
