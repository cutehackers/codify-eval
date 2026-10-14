"""Bounded constant JSON-string interpolation classifier; never execute JS."""
from contextlib import contextmanager
import copy
import json
from pathlib import Path
import re
import subprocess
import saved_quote_transport_v3611 as prior
from prepare import ROOT
import transport

VERSION='interpolated-quote-transport-v3.6.12'
MANIFEST=ROOT/'results/frozen-interpolated-quote-transport-v3.6.12.json'
sha=prior.sha
DECL=re.compile(r'const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*`((?:\\.|[^`\\])*)`\s*;\s*',re.S)


def cooked(body):
    body=body.replace('\r\n','\n').replace('\r','\n')
    out=[];i=0
    escapes={'n':'\n','r':'\r','t':'\t','b':'\b','f':'\f','v':'\v','\\':'\\',"'":"'",'"':'"','`':'`','$':'$'}
    while i<len(body):
        c=body[i]
        if c=='$' and body[i:i+2]=='${':raise ValueError('Unresolved interpolation')
        if c!='\\':out.append(c);i+=1;continue
        i+=1
        if i==len(body):raise ValueError('Trailing escape')
        c=body[i];i+=1
        if c in escapes:out.append(escapes[c])
        elif c=='\n':continue
        elif c in ('u','x'):
            size=4 if c=='u' else 2;digits=body[i:i+size]
            if len(digits)!=size or not re.fullmatch('[0-9a-fA-F]+',digits):raise ValueError('Invalid escape')
            value=int(digits,16)
            if 0xD800<=value<=0xDFFF:raise ValueError('Surrogate escape outside supported grammar')
            out.append(chr(value));i+=size
        elif c=='0' and (i==len(body) or not body[i].isdigit()):out.append('\0')
        else:raise ValueError('Unsupported escape')
    return ''.join(out)


def resolved_command(code,root,run_id):
    rest=code.strip();values={};names=[]
    try:
        for _ in range(2):
            m=DECL.match(rest)
            if not m or m.group(1) in values:return None
            name,body=m.groups()
            if name in {'JSON','tools','text'}:return None
            values[name]=cooked(body);names.append(name);rest=rest[m.end():]
        m=DECL.match(rest)
        if not m or m.group(1) in values or m.group(1) in {'JSON','tools','text'}:return None
        command_name,body=m.groups();rest=rest[m.end():]
        interpolation=re.compile(r'\$\{JSON\.stringify\(([A-Za-z_][A-Za-z0-9_]*)\)\}')
        pieces=[];seen=[];cursor=0
        for item in interpolation.finditer(body):
            if item.group(1) not in values:return None
            pieces.extend([cooked(body[cursor:item.start()]),json.dumps(values[item.group(1)],ensure_ascii=False)])
            seen.append(item.group(1));cursor=item.end()
        if sorted(seen)!=sorted(names):return None
        pieces.append(cooked(body[cursor:]));command=''.join(pieces)
        quote=re.match(r'const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\s*=>\s*('+transport.STRING+r')\s*\+\s*([A-Za-z_][A-Za-z0-9_]*)\.replaceAll\(\s*('+transport.STRING+r')\s*,\s*('+transport.STRING+r')\s*\)\s*\+\s*('+transport.STRING+r')\s*;\s*',rest,re.S)
        if not quote:return None
        fn,arg,left,used,needle,replacement,right=quote.groups()
        if fn in values or fn==command_name or fn in {'JSON','tools','text'} or arg!=used:return None
        if [json.loads(x) for x in (left,needle,replacement,right)]!=["'","'","'\\''","'"]:return None
        rest=rest[quote.end():]
        call=re.fullmatch(r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*('+transport.STRING+r')\s*\+\s*'+re.escape(fn)+r'\(\s*'+re.escape(command_name)+r'\s*\)'+transport.OPTIONS+r'\s*\}\s*\)\s*\)\s*;?\s*',rest,re.S)
        if not call:return None
        prefix=json.loads(call.group(1))
        if prefix!=f'python3 {root}/tools/agent_io.py --run {run_id} --cmd ':return None
        host=prefix+"'"+command.replace("'","'\\''")+"'"
        view='text(await tools.exec_command({cmd:'+json.dumps(host,ensure_ascii=False)+'}));'
        if not prior.prior.ORIGINAL_WRAPPER_ORIGIN(view,root,run_id):return None
        parser=prior.prior.verify_parser_runtime()
        syntax=subprocess.run([parser['path'],*parser['arguments']],input=code,capture_output=True,text=True,timeout=5)
        if syntax.returncode!=0 or syntax.stdout or syntax.stderr:return None
        return {'command':command,'host':host,'classifier_view':view}
    except (ValueError,KeyError,subprocess.SubprocessError):return None


def wrapper_origin(code,root,run_id):
    return resolved_command(code,root,run_id) is not None or prior.wrapper_origin(code,root,run_id)


@contextmanager
def patched_origin():
    with prior.patched_origin():
        old=transport.wrapper_origin;transport.wrapper_origin=wrapper_origin
        try:yield
        finally:transport.wrapper_origin=old


def audit(events,metadata,root):
    with patched_origin():return prior.prior.audit_transport(events,metadata,root)


def compare(run_id):
    p=ROOT/'results'/run_id/'native-tools.jsonl';events=[json.loads(x) for x in p.read_text().splitlines()];meta=json.loads((ROOT/'runtime'/run_id/'run.json').read_text())
    origins=[]
    for e in events:
        q=e.get('payload',{})
        if q.get('type') in ('function_call','custom_tool_call'):
            value=resolved_command(str(q.get('arguments',q.get('input',''))),str(ROOT),run_id)
            if value:origins.append({'call_id':q['call_id'],'command_sha256':__import__('hashlib').sha256(value['command'].encode()).hexdigest()})
    return {'run_id':run_id,'native_sha256':sha(p),'before':prior.audit(events,meta,str(ROOT)),'after':audit(events,meta,str(ROOT)),'resolved_origin_calls':origins}


def verify_registration():
    prior.verify_registration();f=json.loads(MANIFEST.read_text())
    required={'tools/interpolated_quote_transport_v3612.py','tools/interpolated_quote_transport_v3612_probes.py','results/interpolated-quote-transport-qualification-v3.6.12.json','results/interpolated-quote-transport-independent-review-v3.6.12.json'}
    if f.get('version')!=VERSION or f.get('status')!='frozen' or f.get('actor_reexecution_allowed') is not False or not required<=set(f['source_sha256']):raise ValueError('Unregistered interpolation classifier')
    for n,v in f['source_sha256'].items():
        if sha(ROOT/n)!=v:raise ValueError('Changed pin '+n)
    return f


def apply(run_id):
    f=verify_registration();v=compare(run_id);dest=ROOT/'results'/run_id/'interpolated-quote-audit-v3.6.12.json'
    if dest.exists():raise ValueError('Existing audit preserved')
    if v['before']!=v['after']:
        originals={f'runtime/{run_id}/run.json'}|{f'results/{run_id}/{n}' for n in ('manifest.json','native-tools.jsonl','turns.json')};pres=f.get('prior_preservation',{}).get(run_id,{})
        if set(pres)!=originals or (ROOT/'results'/run_id/'grade.json').exists():raise ValueError('Missing originals or existing grade')
        for n,item in pres.items():
            if (ROOT/n).resolve()==(ROOT/item['copy']).resolve() or sha(ROOT/n)!=item['sha256'] or sha(ROOT/item['copy'])!=item['sha256']:raise ValueError('Preservation failed '+n)
        data=[(ROOT/n,json.loads((ROOT/n).read_text())) for n in (f'runtime/{run_id}/run.json',f'results/{run_id}/manifest.json')]
        for p,d in data:
            if (d.get('tool_audit'),d.get('tool_poll_evidence'))!=tuple(v['before']):raise ValueError('Baseline changed')
        for p,d in data:
            before=copy.deepcopy(d);d['tool_audit'],d['tool_poll_evidence']=v['after'];assert {k:x for k,x in before.items() if k not in ('tool_audit','tool_poll_evidence')}=={k:x for k,x in d.items() if k not in ('tool_audit','tool_poll_evidence')};p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
        for n in (f'results/{run_id}/native-tools.jsonl',f'results/{run_id}/turns.json'):
            if sha(ROOT/n)!=pres[n]['sha256']:raise ValueError('Native or turns changed')
    v.update(version=VERSION,registration_sha256=sha(MANIFEST),actor_reexecuted=False,native_unmodified=True)
    with dest.open('x') as stream:json.dump(v,stream,indent=2)
    return v


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('run');a=p.parse_args();print(json.dumps(apply(a.run),indent=2))
