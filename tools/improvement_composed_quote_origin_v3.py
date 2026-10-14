"""Static, bounded immutable string bindings. Never execute actor JavaScript."""
import hashlib
import json
import re
import shlex
import improvement_composed_quote_origin_v2 as prior
from transport import STRING, OPTIONS
from prepare import ROOT

MANIFEST=ROOT/'results/improvement-v1/composed-quote-collector-freeze-v3.json'
IDENT=prior.IDENT
TEMPLATE=prior.TEMPLATE
GLOBALS={'tools','text','JSON'}
QUOTE=re.compile(r'const\s+('+IDENT+r')\s*=\s*('+IDENT+r')\s*=>\s*('+STRING+r')\s*\+\s*('+IDENT+r')\.replace\(\s*/\'/g\s*,\s*('+STRING+r')\s*\)\s*\+\s*('+STRING+r')\s*;\s*',re.S)
TERM=re.compile(r'('+STRING+r')|`((?:\\.|[^`\\])*)`|JSON\.stringify\(\s*('+IDENT+r')\s*\)|('+IDENT+r')',re.S)


def template_value(body):
    body=body.replace('\r\n','\n').replace('\r','\n');out=[];index=0
    while index<len(body):
        ch=body[index]
        if ch=='\\':
            if index+1>=len(body) or body[index+1] not in {'\\','$','`'}:return None
            out.append(body[index+1]);index+=2;continue
        if body[index:index+2]=='${':return None
        out.append(ch);index+=1
    value=''.join(out)
    return None if any(0xd800<=ord(c)<=0xdfff for c in value) else value


def _project(code,root,run_id):
    if not isinstance(code,str) or len(code)>1048576:return None
    rest=code.strip();values={};aliases={};declarations=0
    while rest.startswith('const'):
        declarations+=1
        if declarations>64:return None
        quote=QUOTE.match(rest)
        if quote:
            name,param,left,receiver,escape,right=quote.groups()
            if name in values or name in aliases or name in GLOBALS or param!=receiver:return None
            if param in GLOBALS or param==name:return None
            if [json.loads(v) for v in [left,escape,right]]!=["'","'\\''","'"]:return None
            aliases[name]=True;rest=rest[quote.end():];continue
        declaration=re.match(r'const\s+('+IDENT+r')\s*=\s*',rest)
        if not declaration:return None
        name=declaration.group(1)
        if name in values or name in aliases or name in GLOBALS:return None
        rest=rest[declaration.end():];parts=[];characters=0;terms=0
        while True:
            terms+=1
            if terms>1024:return None
            term=TERM.match(rest)
            if not term:return None
            literal,template,stringified,variable=term.groups()
            if literal is not None:value=json.loads(literal)
            elif template is not None:value=template_value(template)
            elif stringified in values:value=json.dumps(values[stringified],ensure_ascii=False,separators=(',',':'))
            elif variable in values:value=values[variable]
            else:return None
            if not isinstance(value,str) or any(0xd800<=ord(c)<=0xdfff for c in value):return None
            parts.append(value)
            characters+=len(value)
            if characters>1048576:return None
            rest=rest[term.end():].lstrip()
            if rest.startswith('+'):rest=rest[1:].lstrip();continue
            if not rest.startswith(';'):return None
            rest=rest[1:].lstrip();break
        values[name]=''.join(parts)
        if sum(map(len,values.values()))>2097152:return None
    call=re.fullmatch(r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*('+STRING+r')\s*\+\s*('+IDENT+r')\(\s*('+IDENT+r')\s*\)('+OPTIONS+r')\}\s*\)\s*\)\s*;?\s*',rest,re.S)
    if not call:return None
    prefix,alias,name,options=call.groups()
    if alias not in aliases or name not in values:return None
    if json.loads(prefix)!=f'python3 {root}/tools/agent_io.py --run {run_id} --cmd ':return None
    command=values[name];outer=json.loads(prefix)+"'"+command.replace("'","'\\''")+"'"
    if shlex.split(outer)!=['python3',f'{root}/tools/agent_io.py','--run',run_id,'--cmd',command]:return None
    return 'text(await tools.exec_command({"cmd":'+json.dumps(outer)+options+'}));'


def project(code,root,run_id):
    try:return _project(code,root,run_id)
    except (ValueError,TypeError,OverflowError):return None


def inline_view(code,root,run_id):
    return project(code,root,run_id) or prior.inline_view(code,root,run_id)


def wrapper_origin(code,root,run_id):
    view=project(code,root,run_id)
    return prior.wrapper_origin(view if view is not None else code,root,run_id)


def verify_registration():
    prior.verify_registration();value=json.loads(MANIFEST.read_bytes())
    assert value['status']=='frozen' and value['version']=='improvement-composed-quote-collect-v3' and value['historical_mutation_allowed'] is False
    assert {'tools/improvement_composed_quote_origin_v3.py','tools/improvement_composed_quote_collect_v3.py','tools/improvement_composed_quote_collect_v3_probes.py','results/improvement-v1/composed-quote-collector-review-v4.json','results/improvement-v1/composed-quote-collector-probes-v6.json'} <= set(value['source_hashes'])
    for name,digest in value['source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    return value
