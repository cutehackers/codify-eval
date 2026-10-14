"""Emit a reproducible bootstrap prompt; dispatch remains in the native runtime."""
import argparse
import json
from pathlib import Path
import time
from prepare import ROOT

def dispatch(run_id):
    directory=ROOT/'runtime'/run_id
    path=directory/'run.json'
    metadata=json.loads(path.read_text())
    if metadata.get('agent_started_at'):
        raise ValueError('Already dispatched; never replace an existing trajectory')
    request=directory/'request.txt'
    code='text(await tools.exec_command('+json.dumps({'cmd':'cat '+str(request),'max_output_tokens':6500},separators=(',',':'))+'));'
    metadata.update(agent_started_at=time.time(),bootstrap_code=code,status='dispatched')
    path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    prompt=('You are the implementation owner of one isolated evaluation task. First execute exactly this code through functions.exec to read your sole initial request. This one request file is the only permitted host read. Then follow that request and perform ALL repository operations through its container command interface. Never read any other host file or use any other connector. Do not read the transport implementation, other runs, or oracle/reference files.\n'+code)
    (directory/'bootstrap.txt').write_text(prompt)
    return prompt

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run');args=parser.parse_args()
    print(dispatch(args.run))
