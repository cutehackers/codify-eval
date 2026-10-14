"""Pure closed-grammar and preserved-native probes; no historical mutation."""
import copy
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import improvement_composed_quote_origin_v4 as origin
import improvement_composed_quote_collect_v4 as adapter
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
    single='const command = `printf hello`;\nconst quote=s=>"\'"+s.replace(/\'/g,"\'\\\\\'\'")+"\'";\ntext(await tools.exec_command({cmd:'+json.dumps(f'python3 {ROOT}/tools/agent_io.py --run {RUN} --cmd ')+'+quote(command),max_output_tokens:6000,yield_time_ms:1000}));'
    projected=origin.project(single,str(ROOT),RUN)
    check('single_template_literal_recognized',projected is not None)
    check('single_template_js_semantics_equals_projection',execute(single)==execute(projected))
    for name,changed in [
        ('single_interpolation',single.replace('printf hello','${process.env.HOME}')),
        ('single_reassignment',single.replace('const quote=', 'command="oops";const quote=')),
        ('single_global_binding',single.replace('const command =','const tools =')),
        ('single_duplicate_binding',single.replace('const quote=', 'const command=`x`;const quote=')),
        ('single_quote_collision',single.replace('const quote=', 'const command=')),
        ('single_parameter_global',single.replace('s=>','tools=>').replace('s.replace','tools.replace')),
        ('single_extra_call',single+'text(await tools.exec_command({cmd:"pwd"}));'),
        ('single_wrong_run',single.replace('--run '+RUN,'--run wrong')),
        ('single_mutable',single.replace('const command','let command')),
        ('single_unknown_argument',single.replace('quote(command)','quote(unknown)')),
        ('single_extra_option',single.replace('max_output_tokens:6000','workdir:"/tmp",max_output_tokens:6000')),
    ]:
        check(name,changed!=single and origin.project(changed,str(ROOT),RUN) is None)
    recent_run='control-probe-P02-pilot-v3-P02-A-1'
    recent_folder=ROOT/'results'/recent_run
    recent_raw=(recent_folder/'native-tools.jsonl').read_bytes()
    recent_events=[json.loads(l) for l in recent_raw.splitlines()]
    recent_meta=json.loads((ROOT/'runtime'/recent_run/'run.json').read_bytes())
    recent_journal=[json.loads(l) for l in (ROOT/'runtime'/recent_run/'commands.jsonl').read_bytes().splitlines()]
    for call_id in ['call_63e2429333c74160814ac1f0ec20e271','call_ae332767896f4c64adb152804648d930']:
        recent_code=next(e['payload']['input'] for e in recent_events if e.get('payload',{}).get('call_id')==call_id and e['payload'].get('type')=='custom_tool_call')
        recent_view=origin.project(recent_code,str(ROOT),recent_run)
        check('recent_origin_'+call_id,recent_view is not None)
        matched=__import__('re').search(r'"cmd":('+__import__('transport').STRING+r')',recent_view)
        recent_argv=shlex.split(json.loads(matched.group(1)))
        check('recent_exact_journal_'+call_id,len(recent_argv)==6 and sum(j['command']==recent_argv[-1] for j in recent_journal)==1)
    recent_violations,recent_polls=adapter.audit(recent_events,recent_meta,str(ROOT))
    check('recent_owned_poll_exact_origin',not recent_violations and len(recent_polls)==1 and recent_polls[0]['session_id']==34932 and recent_polls[0]['origin_call_id']=='call_63e2429333c74160814ac1f0ec20e271')
    check('recent_raw_unmodified',recent_raw==(recent_folder/'native-tools.jsonl').read_bytes())
    direct=synthetic.replace('JSON.stringify(alpha)','alpha').replace('JSON.stringify(beta)','beta')
    check('direct_reference_semantics',execute(direct)==execute(origin.project(direct,str(ROOT),RUN)))
    quote_first=direct.replace('const command="printf "+alpha+" "+beta;\n','').replace('text(await tools.exec_command','const command="printf "+alpha+" "+beta;\ntext(await tools.exec_command')
    check('quote_before_command_semantics',execute(quote_first)==execute(origin.project(quote_first,str(ROOT),RUN)))
    escaped=single.replace('printf hello',r'printf \${literal} \`tick\`')
    check('escaped_template_semantics',execute(escaped)==execute(origin.project(escaped,str(ROOT),RUN)))
    for name,changed in [
        ('reference_unknown',direct.replace('+alpha+','+unknown+')),
        ('reference_call',direct.replace('+alpha+','+alpha()+')),
        ('reference_property',direct.replace('+alpha+','+alpha.length+')),
        ('reference_index',direct.replace('+alpha+','+alpha[0]+')),
        ('reference_assignment',direct.replace('+alpha+','+(alpha="oops")+')),
        ('reference_arithmetic',direct.replace('+alpha+','+1+')),
        ('reference_mutable',direct.replace('const alpha','let alpha')),
        ('future_binding',direct.replace('const alpha','const missing').replace('+alpha+','+betaLater+')),
        ('duplicate_quote',direct.replace('text(await','const quote=s=>"oops";text(await')),
        ('too_many_bindings',''.join('const x%d="x";'%i for i in range(65))+single),
    ]:
        check(name,changed!=direct and origin.project(changed,str(ROOT),RUN) is None)
    bounded=single.replace('`printf hello`','+'.join(['""']*1024))
    check('term_count_1024_allowed',origin.project(bounded,str(ROOT),RUN) is not None)
    over=single.replace('`printf hello`','+'.join(['""']*1025))
    check('term_count_1025_rejected',origin.project(over,str(ROOT),RUN) is None)
    huge=single.replace('`printf hello`','+'.join(['""']*20000))
    started=__import__('time').monotonic();closed=origin.project(huge,str(ROOT),RUN) is None
    elapsed=__import__('time').monotonic()-started
    check('term_count_20000_rejected',closed)
    check('term_count_20000_bounded_time',elapsed<1)
    c0_run='control-probe-P02-pilot-v4-P02-C0-1'
    c0_folder=ROOT/'results'/c0_run
    c0_raw=(c0_folder/'native-tools.jsonl').read_bytes()
    c0_events=[json.loads(l) for l in c0_raw.splitlines()]
    c0_meta=json.loads((ROOT/'runtime'/c0_run/'run.json').read_bytes())
    c0_journal=[json.loads(l) for l in (ROOT/'runtime'/c0_run/'commands.jsonl').read_bytes().splitlines()]
    for call_id in ['call_288e2eb8c70c457c8f8ad78fb83695fa','call_7bf88effbcde4babb0918c740be166b6']:
        code0=next(e['payload']['input'] for e in c0_events if e.get('payload',{}).get('call_id')==call_id and e['payload'].get('type')=='custom_tool_call')
        view0=origin.project(code0,str(ROOT),c0_run)
        check('inline_replace_origin_'+call_id,view0 is not None)
        match0=__import__('re').search(r'"cmd":('+__import__('transport').STRING+r')',view0)
        argv0=shlex.split(json.loads(match0.group(1)))
        check('inline_replace_exact_journal_'+call_id,len(argv0)==6 and sum(j['command']==argv0[-1] for j in c0_journal)==1)
    violations0,polls0=adapter.audit(c0_events,c0_meta,str(ROOT))
    check('inline_replace_owned_poll',not violations0 and len(polls0)==1 and polls0[0]['session_id']==3172 and polls0[0]['origin_call_id']=='call_288e2eb8c70c457c8f8ad78fb83695fa')
    check('inline_replace_raw_preserved',c0_raw==(c0_folder/'native-tools.jsonl').read_bytes())
    prefix=f'python3 {ROOT}/tools/agent_io.py --run {RUN} --cmd '
    # Root-authored grammar matrix, with mock tools. Never execute historical code.
    replace='command.replace(/\'/g,"\'\\\\\'\'")'
    header='const command=`printf a\'b`;'
    forms=[
        header+'text(await tools.exec_command({cmd:'+json.dumps(prefix+"'")+'+'+replace+'+"\'",yield_time_ms:1000}));',
        header+'const escaped='+replace+';text(await tools.exec_command({cmd:'+json.dumps(prefix+"'")+'+escaped+"\'"}));',
        header+'const q=s=>"\'"+s.replace(/\'/g,"\'\\\\\'\'")+"\'";const outer='+json.dumps(prefix)+'+q(command);text(await tools.exec_command({cmd:outer}));',
        'text(await tools.exec_command({cmd:'+json.dumps(prefix+"'printf hello'")+'}));',
    ]
    for index,form in enumerate(forms):
        view=origin.project(form,str(ROOT),RUN)
        check('grammar_matrix_recognized_'+str(index),view is not None)
        check('grammar_matrix_node_equality_'+str(index),execute(form)==execute(view))
    for name,form in [
        ('outer_shell_substitution','text(await tools.exec_command({cmd:'+json.dumps(prefix+'"$(id)"')+'}));'),
        ('outer_shell_variable','text(await tools.exec_command({cmd:'+json.dumps(prefix+'"$HOME"')+'}));'),
        ('outer_operator','text(await tools.exec_command({cmd:'+json.dumps(prefix+"'pwd'; id")+'}));'),
        ('wrong_replace_escape',forms[0].replace(replace,'command.replace(/\'/g,"wrong")')),
        ('wrong_replace_regex',forms[0].replace("/\'/g","/x/g")),
        ('replace_callback',forms[0].replace(replace,'command.replace(/\'/g,()=>process.env.HOME)')),
        ('unknown_quote_function',forms[2].replace('q(command)','other(command)')),
        ('mutated_outer',forms[2].replace('text(await','outer="oops";text(await')),
        ('extra_native_call',forms[3]+'await tools.web__run({});'),
        ('expression_too_many_terms',forms[3].replace('cmd:', 'cmd:'+ '+'.join(['""']*1025)+'+')),
    ]:
        check(name,origin.project(form,str(ROOT),RUN) is None)
    for cohort in ['A','C12']:
        native_folder=ROOT/'results'/('control-probe-P02-pilot-v4-P02-'+cohort+'-1')
        native_raw=(native_folder/'native-tools.jsonl').read_bytes()
        native_events=[json.loads(l) for l in native_raw.splitlines()]
        native_metadata=json.loads((ROOT/'runtime'/native_folder.name/'run.json').read_bytes())
        check('current_'+cohort+'_audit_still_passes',not adapter.audit(native_events,native_metadata,str(ROOT))[0])
    names=[Path(__file__),Path(origin.__file__),Path(adapter.__file__),NODE,c0_folder/'native-tools.jsonl',ROOT/'runtime'/c0_run/'commands.jsonl',c0_folder/'grade.json',recent_folder/'native-tools.jsonl',ROOT/'runtime'/recent_run/'commands.jsonl',recent_folder/'grade.json',folder/'native-tools.jsonl',ROOT/'runtime'/RUN/'commands.jsonl',ROOT/'runtime'/RUN/'run.json',folder/'grade.json',ROOT/'results/improvement-v1/P02-A1-poll-admissibility-review-v1.json']
    return {'status':'pass','count':len(checks),'checks':checks,'source_hashes':{str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in names},'limits':['Actual actor code statically projected, never evaluated','Only root-authored fixed synthetic JS executed with dummy tools','Original frozen audit, grade and input bytes remain unchanged','Forward collector runtime not yet exercised']}


if __name__=='__main__':
    result=run();path=ROOT/'results/improvement-v1/composed-quote-collector-probes-v8.json'
    with path.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'checks':result['count']}))
