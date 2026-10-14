"""Static, bounded immutable string bindings. Never execute actor JavaScript."""
import hashlib
import json
import re
import shlex
import improvement_composed_quote_origin_v6 as prior
from transport import STRING, OPTIONS
from prepare import ROOT

MANIFEST=ROOT/'results/improvement-v1/composed-quote-collector-freeze-v7.json'
IDENT=prior.IDENT
TEMPLATE=prior.TEMPLATE
GLOBALS={'tools','text','JSON'}
QUOTE=re.compile(r'const\s+('+IDENT+r')\s*=\s*('+IDENT+r')\s*=>\s*('+STRING+r')\s*\+\s*('+IDENT+r')\.replace(?:\(\s*/\'/g\s*,\s*|All\(\s*"\'"\s*,\s*)('+STRING+r')\s*\)\s*\+\s*('+STRING+r')\s*;\s*',re.S)
TERM=re.compile(r'('+STRING+r')|`((?:\\.|[^`\\])*)`|JSON\.stringify\(\s*('+IDENT+r')\s*\)|('+IDENT+r')\.replace(?:\(\s*/\'/g\s*,\s*|All\(\s*"\'"\s*,\s*)('+STRING+r')\s*\)|('+IDENT+r')\(\s*('+IDENT+r')\s*\)|('+IDENT+r')',re.S)


def template_value(body, values=None):
    values = {} if values is None else values
    body=body.replace('\r\n','\n').replace('\r','\n');out=[];index=0;characters=0
    while index<len(body):
        ch=body[index]
        if ch=='\\':
            if index+1>=len(body) or body[index+1] not in {'\\','$','`','n','r','t'}:return None
            part={'n':'\n','r':'\r','t':'\t'}.get(body[index+1],body[index+1]);index+=2
        elif body[index:index+2]=='${':
            end=body.find('}',index+2)
            if end<0:return None
            name=body[index+2:end].strip()
            serialized=re.fullmatch(r'JSON\.stringify\(\s*('+IDENT+r')\s*\)',name)
            if serialized:
                identifier=serialized.group(1)
                if identifier not in values:return None
                part=json.dumps(values[identifier],ensure_ascii=False,separators=(',',':'))
            else:
                if re.fullmatch(IDENT,name) is None or name not in values:return None
                part=values[name]
            index=end+1
        else:
            part=ch;index+=1
        characters+=len(part)
        if characters>1048576:return None
        out.append(part)
    value=''.join(out)
    return None if any(0xd800<=ord(c)<=0xdfff for c in value) else value


def expression(rest,values,aliases):
    parts=[];characters=0
    for count in range(1024):
        match=TERM.match(rest)
        if not match:return None
        literal,template,stringified,replaced,escape,called,argument,variable=match.groups()
        if literal is not None:value=json.loads(literal)
        elif template is not None:value=template_value(template,values)
        elif stringified in values:value=json.dumps(values[stringified],ensure_ascii=False,separators=(',',':'))
        elif replaced in values and json.loads(escape)=="'\\''":value=values[replaced].replace("'","'\\''")
        elif called in aliases and argument in values:value="'"+values[argument].replace("'","'\\''")+"'"
        elif variable in values:value=values[variable]
        else:return None
        if not isinstance(value,str) or any(0xd800<=ord(c)<=0xdfff for c in value):return None
        characters+=len(value)
        if characters>1048576:return None
        parts.append(value);rest=rest[match.end():].lstrip()
        if rest.startswith('+'):rest=rest[1:].lstrip();continue
        return ''.join(parts),rest
    return None


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
        result=expression(rest[declaration.end():],values,aliases)
        if result is None:return None
        value,rest=result
        if not rest.startswith(';'):return None
        rest=rest[1:].lstrip();values[name]=value
        if sum(map(len,values.values()))>2097152:return None
    invocation=re.match(r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*',rest)
    if not invocation:return None
    result=expression(rest[invocation.end():],values,aliases)
    if result is None:return None
    outer,rest=result
    ending=re.fullmatch('('+OPTIONS+r')\}\s*\)\s*\)\s*;?\s*',rest,re.S)
    if not ending:return None
    argv=shlex.split(outer)
    if len(argv)!=6 or argv[:5]!=['python3',f'{root}/tools/agent_io.py','--run',run_id,'--cmd']:return None
    # Exact single-quoted shell form excludes host substitutions and operators.
    canonical=f'python3 {root}/tools/agent_io.py --run {run_id} --cmd '+"'"+argv[5].replace("'","'\\''")+"'"
    if outer!=canonical:return None
    return 'text(await tools.exec_command({"cmd":'+json.dumps(outer)+ending.group(1)+'}));'


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
    assert value['status']=='frozen' and value['version']=='improvement-composed-quote-collect-v7' and value['historical_mutation_allowed'] is False
    assert {'tools/improvement_composed_quote_origin_v7.py','tools/improvement_composed_quote_collect_v7.py','tools/improvement_composed_quote_collect_v7_probes.py','results/improvement-v1/composed-quote-collector-review-v8.json','results/improvement-v1/composed-quote-collector-probes-v12.json'} <= set(value['source_hashes'])
    for name,digest in value['source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    return value
