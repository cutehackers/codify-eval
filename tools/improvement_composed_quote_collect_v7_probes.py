"""Prospective bounded serialization interpolation; actor code is never executed."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
import improvement_composed_quote_collect_v6_probes as prior
import improvement_composed_quote_origin_v7 as origin
import improvement_composed_quote_collect_v7 as adapter
from prepare import ROOT
from transport import STRING


def run():
    before = prior.origin, prior.adapter
    prior.origin, prior.adapter = origin, adapter
    try:
        result = prior.run()
    finally:
        prior.origin, prior.adapter = before
    checks = result['checks']
    def check(name, passed):
        assert passed, name
        checks.append({'name': name, 'pass': True})
    run_id = 'control-probe-P03-pilot-v1-P03-C13-1'
    folder = ROOT/'results'/run_id
    names = [folder/n for n in ['native-tools.jsonl','grade.json','independent-terminal-diagnostic-v1.json']]
    names += [ROOT/'runtime'/run_id/n for n in ['run.json','commands.jsonl']]
    sealed = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in names}
    events = [json.loads(line) for line in (folder/'native-tools.jsonl').read_bytes().splitlines()]
    journal = [json.loads(line) for line in (ROOT/'runtime'/run_id/'commands.jsonl').read_bytes().splitlines()]
    call = 'call_76b92ffc28b04421a1dbf7635b5b0cc5'
    code = next(e['payload']['input'] for e in events if e.get('payload',{}).get('type')=='custom_tool_call' and e['payload']['call_id']==call)
    view = origin.project(code,str(ROOT),run_id)
    check('actual_json_stringify_template_recognized',view is not None)
    match = re.search('"cmd":('+STRING+')',view)
    argv = shlex.split(json.loads(match.group(1)))
    check('actual_json_stringify_exact_journal',len(argv)==6 and sum(j['command']==argv[-1] for j in journal)==1)
    metadata = json.loads((ROOT/'runtime'/run_id/'run.json').read_bytes())
    violations,polls = adapter.audit(events,metadata,str(ROOT))
    check('actual_owned_five_empty_polls',not violations and len(polls)==5 and all(p['session_id']==5734 and p['origin_call_id']==call and p['empty_stdin'] for p in polls))
    prefix = f'python3 {ROOT}/tools/agent_io.py --run {run_id} --cmd '
    quote = 'const q=s=>'+json.dumps("'")+'+s.replaceAll('+json.dumps("'")+','+json.dumps("'\\''")+')+'+json.dumps("'")+';'
    piece = "a'\"\\b\n한국어\t\r\u2028\u2029🙂"
    synthetic = 'const piece='+json.dumps(piece)+';const command=`printf ${JSON.stringify(piece)} ${piece}`;'+quote+'text(await tools.exec_command({cmd:'+json.dumps(prefix)+'+q(command)}));'
    view = origin.project(synthetic,str(ROOT),run_id)
    check('authored_json_stringify_recognized',view is not None)
    setup = 'const text=x=>{};const tools={exec_command:async x=>{console.log(JSON.stringify(x));return null;}};'
    def execute(authored):
        node = prior.prior.NODE
        receipt = subprocess.run([str(node),'--input-type=module','-e',setup+authored],capture_output=True,text=True,timeout=10)
        receipt.check_returncode()
        return json.loads(receipt.stdout)
    check('authored_json_stringify_node_semantics',execute(synthetic)==execute(view))
    for expression in ['JSON.stringify(unknown)','JSON.stringify(piece.length)','JSON.stringify(piece[0])','JSON.stringify(piece, null)','JSON.stringify(piece, null, 2)','JSON.stringify(piece+piece)','JSON.stringify(q(piece))','JSON.stringify(piece="x")','JSON.stringify({value:piece})','JSON["stringify"](piece)','JSON.stringify(process.env.HOME)','JSON.stringify(JSON.stringify(piece))']:
        altered = synthetic.replace('${JSON.stringify(piece)}','${'+expression+'}')
        check('closed_serialization_'+expression,origin.project(altered,str(ROOT),run_id) is None)
    check('serialization_reserved_global_shadow_rejected',origin.project('const JSON="x";'+synthetic,str(ROOT),run_id) is None)
    check('serialization_forward_binding_rejected',origin.project(synthetic.replace('const piece=','const missing='),str(ROOT),run_id) is None)
    check('serialization_escaped_interpolation_literal',origin.template_value(r'\${JSON.stringify(piece)}',{'piece':'x'})=='${JSON.stringify(piece)}')
    check('serialization_one_mib_expansion_rejected',origin.template_value('${JSON.stringify(v)}',{'v':'\x00'*200000}) is None)
    check('serialization_exact_empty_string',origin.template_value('${JSON.stringify(v)}',{'v':''})=='""')
    check('historical_sources_unchanged',sealed=={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in names})
    names += [Path(__file__),Path(origin.__file__),Path(adapter.__file__)]
    result['source_hashes'].update({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in names})
    result.update(count=len(checks),inherited_checks=121,prospective_only=True,historical_mutation_allowed=False,actor_code_executed=False)
    return result


if __name__=='__main__':
    result=run()
    path=ROOT/'results/improvement-v1/composed-quote-collector-probes-v12.json'
    with path.open('x') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({'status':result['status'],'checks':result['count']}))
