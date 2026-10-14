"""Closed constant-string composition; projects syntax without executing actor code."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import improvement_composed_quote_origin_v1 as prior
from transport import STRING, OPTIONS
from prepare import ROOT

MANIFEST=ROOT/'results/improvement-v1/composed-quote-collector-freeze-v2.json'
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
    existing=prior.project(code,root,run_id)
    if existing is not None:return existing
    if not isinstance(code,str) or len(code)>1048576:return None
    rest=code.strip();match=TEMPLATE.match(rest)
    if not match:return None
    command_name,body=match.groups();command=template_value(body)
    if command is None or command_name in {'tools','text','JSON'}:return None
    rest=rest[match.end():]
    quote=re.match(r'const\s+('+IDENT+r')\s*=\s*('+IDENT+r')\s*=>\s*('+STRING+r')\s*\+\s*('+IDENT+r')\.replace\(\s*/\'/g\s*,\s*('+STRING+r')\s*\)\s*\+\s*('+STRING+r')\s*;\s*',rest,re.S)
    if not quote:return None
    quote_name,param,left,receiver,escape,right=quote.groups()
    if quote_name in {command_name,'tools','text','JSON'} or param in {quote_name,command_name,'tools','text','JSON'} or param!=receiver:return None
    if [json.loads(v) for v in [left,escape,right]]!=["'","'\\''","'"]:return None
    rest=rest[quote.end():]
    invocation=re.fullmatch(r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*('+STRING+r')\s*\+\s*'+re.escape(quote_name)+r'\(\s*'+re.escape(command_name)+r'\s*\)('+OPTIONS+r')\}\s*\)\s*\)\s*;?\s*',rest,re.S)
    if not invocation:return None
    prefix=json.loads(invocation.group(1))
    if prefix!=f'python3 {root}/tools/agent_io.py --run {run_id} --cmd ':return None
    outer=prefix+"'"+command.replace("'","'\\''")+"'"
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
    assert value['status']=='frozen' and value['version']=='improvement-composed-quote-collect-v2' and value['historical_mutation_allowed'] is False
    assert {'tools/improvement_composed_quote_origin_v2.py','tools/improvement_composed_quote_collect_v2.py','tools/improvement_composed_quote_collect_v2_probes.py','results/improvement-v1/composed-quote-collector-review-v2.json','results/improvement-v1/composed-quote-collector-probes-v4.json'} <= set(value['source_hashes'])
    for name,digest in value['source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    return value
