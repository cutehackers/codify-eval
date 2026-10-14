"""Static run-scoped origin qualification; no source execution or actor rerun."""
import copy
import hashlib
import json
import re
import shlex
from datetime import datetime
from pathlib import Path
import collect_schema_v366 as prior
import transport
from prepare import ROOT

VERSION = 'improvement-inert-origin-v2'
REGISTER = ROOT/'results/improvement-v1/inert-origin-freeze-v2.json'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def literal_command(code, root, run):
    expr = r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*'
    end = transport.OPTIONS + r'\s*\}\s*\)\s*\)\s*;?\s*'
    match = re.fullmatch(expr+'('+transport.STRING+')'+end, code.strip())
    if not match: return None
    try: command=json.loads(match.group(1))
    except ValueError: return None
    prefix=f'python3 {root}/tools/agent_io.py --run {run} --cmd '
    if not command.startswith(prefix): return None
    tail=command[len(prefix):]
    # The argument must begin quoted. No whitespace, escapes, substitutions,
    # control operators, globbing, history, or other active syntax may be exposed.
    if not tail.startswith("'"): return None
    state=None
    for char in tail:
        if state=="'":
            if char=="'": state=None
        elif state=='"':
            if char=='"': state=None
            elif char!="'": return None
        elif char in "'\"": state=char
        elif not re.fullmatch(r'[A-Za-z0-9_./:-]',char): return None
    if state is not None: return None
    try: argv=shlex.split(command)
    except ValueError: return None
    if len(argv)!=6 or argv[:5]!=['python3',f'{root}/tools/agent_io.py','--run',run,'--cmd']: return None
    return argv[5]

def origin_proofs(events, receipts, metadata, root):
    proofs={};run=metadata['run_id']
    calls={};outputs={};positions={};code_counts={}
    for index,e in enumerate(events):
        positions[id(e)]=index
        p=e.get('payload',{});cid=p.get('call_id');kind=p.get('type')
        if kind in {'function_call','custom_tool_call'}:
            calls.setdefault(cid,[]).append(e)
            text=str(p.get('arguments',p.get('input','')))
            code_counts[text]=code_counts.get(text,0)+1
        elif kind in {'function_call_output','custom_tool_call_output'}: outputs.setdefault(cid,[]).append(e)
    for cid, entries in calls.items():
        if len(entries)!=1 or len(outputs.get(cid,[]))!=1: continue
        e=entries[0];p=e['payload']
        if p.get('name') not in {'exec','functions.exec'}: continue
        code=str(p.get('arguments',p.get('input','')))
        if code_counts[code]!=1: continue
        command=literal_command(code,root,run)
        if command is None: continue
        out=outputs[cid][0]
        if positions[id(out)]<=positions[id(e)]: continue
        try:
            start=datetime.fromisoformat(e['timestamp'].replace('Z','+00:00'))
            end=datetime.fromisoformat(out['timestamp'].replace('Z','+00:00'))
            matches=[r for r in receipts if r.get('command')==command and r.get('container')==metadata['container'] and start<=datetime.fromisoformat(r['time'])<=end]
        except (KeyError,ValueError,TypeError): continue
        if len(matches)!=1: continue
        results=list(transport.result_objects(out['payload']))
        if len(results)!=1: continue
        result=results[0]
        if (type(result.get('session_id')) is not int or result['session_id']<=0 or 'exit_code' in result or 'output' not in result or 'wall_time_seconds' not in result): continue
        proofs[code]={'call_id':cid,'session_id':result['session_id'],'command_sha256':hashlib.sha256(command.encode()).hexdigest(),'receipt':matches[0]}
    return proofs

def audit(events,receipts,metadata,root):
    proofs=origin_proofs(events,receipts,metadata,root)
    with prior.patched_origin():
        old=transport.wrapper_origin
        transport.wrapper_origin=lambda code,r,run: old(code,r,run) or (r==root and run==metadata['run_id'] and code in proofs)
        try: result=prior.audit_transport(events,metadata,root)
        finally: transport.wrapper_origin=old
    return result,proofs

def compare(run):
    base=ROOT/'results'/run;runtime=ROOT/'runtime'/run
    events=[json.loads(x) for x in (base/'native-tools.jsonl').read_text().splitlines()]
    receipts=[json.loads(x) for x in (runtime/'commands.jsonl').read_text().splitlines()]
    m=json.loads((runtime/'run.json').read_text())
    with prior.patched_origin(): before=prior.audit_transport(events,m,str(ROOT))
    after,proofs=audit(events,receipts,m,str(ROOT))
    return {'run_id':run,'before':before,'after':after,'origins':proofs}

def apply(run):
    frozen=json.loads(REGISTER.read_text())
    assert frozen['status']=='frozen' and frozen['actor_reexecution_allowed'] is False
    for name,digest in frozen['source_sha256'].items(): assert sha(ROOT/name)==digest,name
    row=frozen['runs'][run];value=compare(run)
    assert not (ROOT/'results'/run/'grade.json').exists()
    for name,item in row['originals'].items():
        assert sha(ROOT/name)==item['sha256']==sha(ROOT/item['copy']),name
    assert value['after']==row['expected_after']
    for name in [f'runtime/{run}/run.json',f'results/{run}/manifest.json']:
        path=ROOT/name;data=json.loads(path.read_text());original=copy.deepcopy(data)
        assert [data['tool_audit'],data['tool_poll_evidence']]==list(value['before'])
        data['tool_audit'],data['tool_poll_evidence']=value['after']
        assert {k:v for k,v in data.items() if k not in {'tool_audit','tool_poll_evidence'}}=={k:v for k,v in original.items() if k not in {'tool_audit','tool_poll_evidence'}}
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    for name,item in row['originals'].items():
        if name.endswith(('native-tools.jsonl','turns.json')): assert sha(ROOT/name)==item['sha256']
    value.update(actor_reexecuted=False,registration_sha256=sha(REGISTER))
    with (ROOT/'results'/run/'inert-origin-audit-v2.json').open('x') as f: json.dump(value,f,ensure_ascii=False,indent=2)
    return value
