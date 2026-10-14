"""Closed constant-string composition; projects syntax without executing actor code."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import saved_quote_transport_v3611 as prior
from transport import STRING, OPTIONS
from prepare import ROOT

MANIFEST=ROOT/'results/improvement-v1/composed-quote-collector-freeze-v1.json'
IDENT=r'[A-Za-z_][A-Za-z0-9_]*'
TEMPLATE=re.compile(r'const\s+('+IDENT+r')\s*=\s*`((?:\\.|[^`\\])*)`\s*;\s*',re.S)


def template_value(body):
    if '${' in body:return None
    # Only the observed escaped-backslash form. Other JS escape forms fail closed.
    body=body.replace('\r\n','\n').replace('\r','\n')
    result=[];i=0
    while i<len(body):
        if body[i]=='\\':
            if i+1>=len(body) or body[i+1]!='\\':return None
            result.append('\\');i+=2
        else:result.append(body[i]);i+=1
    value=''.join(result)
    return None if any(0xd800<=ord(c)<=0xdfff for c in value) else value


def _project(code,root,run_id):
    if not isinstance(code,str) or len(code)>1048576:return None
    rest=code.strip();values={}
    while True:
        match=TEMPLATE.match(rest)
        if not match:break
        name,body=match.groups();value=template_value(body)
        if name in values or name in {'tools','text','JSON'} or value is None or len(values)>=32:return None
        values[name]=value;rest=rest[match.end():]
    if not values:return None
    command_match=re.match(r'const\s+('+IDENT+r')\s*=\s*',rest)
    if not command_match:return None
    command_name=command_match.group(1)
    if command_name in values or command_name in {'tools','text','JSON'}:return None
    rest=rest[command_match.end():];parts=[]
    term=re.compile('('+STRING+r')|JSON\.stringify\(\s*('+IDENT+r')\s*\)')
    while True:
        match=term.match(rest)
        if not match:return None
        if match.group(1):parts.append(json.loads(match.group(1)))
        elif match.group(2) in values:parts.append(json.dumps(values[match.group(2)],ensure_ascii=False,separators=(',',':')))
        else:return None
        rest=rest[match.end():].lstrip()
        if rest.startswith('+'):rest=rest[1:].lstrip();continue
        if not rest.startswith(';'):return None
        rest=rest[1:].lstrip();break
    quote=re.match(r'const\s+('+IDENT+r')\s*=\s*('+IDENT+r')\s*=>\s*('+STRING+r')\s*\+\s*('+IDENT+r')\.replace\(\s*/\'/g\s*,\s*('+STRING+r')\s*\)\s*\+\s*('+STRING+r')\s*;\s*',rest,re.S)
    if not quote:return None
    quote_name,param,left,receiver,escape,right=quote.groups()
    if quote_name in values or quote_name in {command_name,'tools','text','JSON'} or param!=receiver:return None
    if [json.loads(v) for v in [left,escape,right]]!=["'","'\\''","'"]:return None
    rest=rest[quote.end():]
    invocation=re.fullmatch(r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*('+STRING+r')\s*\+\s*'+re.escape(quote_name)+r'\(\s*'+re.escape(command_name)+r'\s*\)('+OPTIONS+r')\}\s*\)\s*\)\s*;?\s*',rest,re.S)
    if not invocation:return None
    prefix=json.loads(invocation.group(1))
    if prefix!=f'python3 {root}/tools/agent_io.py --run {run_id} --cmd ':return None
    command=''.join(parts);outer=prefix+"'"+command.replace("'","'\\''")+"'"
    try:argv=shlex.split(outer)
    except ValueError:return None
    if argv!=['python3',f'{root}/tools/agent_io.py','--run',run_id,'--cmd',command]:return None
    return 'text(await tools.exec_command({"cmd":'+json.dumps(outer)+invocation.group(2)+'}));'


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
    assert value['status']=='frozen' and value['version']=='improvement-composed-quote-collect-v1' and value['historical_mutation_allowed'] is False
    assert {'tools/improvement_composed_quote_origin_v1.py','tools/improvement_composed_quote_collect_v1.py','tools/improvement_composed_quote_collect_v1_probes.py','results/improvement-v1/composed-quote-collector-review-v1.json','results/improvement-v1/composed-quote-collector-probes-v3.json'} <= set(value['source_hashes'])
    for name,digest in value['source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    return value
