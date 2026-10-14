"""Export actual native runtime evidence and immutable per-turn task snapshots."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import time
from prepare import ROOT

SESSION_ROOT=Path('/Users/junhyounglee/.codex/sessions')

def find_session(agent_path:str)->Path:
    candidates=[]
    for file in SESSION_ROOT.glob('2026/10/*/*.jsonl'):
        try:
            with file.open() as stream: meta=json.loads(next(stream)).get('payload',{})
            origin=meta.get('source',{})
            if not isinstance(origin,dict): continue
            spawn=origin.get('subagent',{}).get('thread_spawn',{})
            if spawn.get('agent_path')==agent_path: candidates.append(file)
        except (OSError,ValueError,TypeError,StopIteration): continue
    if len(candidates)!=1: raise ValueError(f'Expected one owned session for {agent_path}, found {len(candidates)}')
    return candidates[0]

def collect(run_id:str,agent_path:str,request:str|None=None)->dict:
    directory=ROOT/'runtime'/run_id
    metadata=json.loads((directory/'run.json').read_text())
    source=find_session(agent_path)
    models=[]; finals=[]; evidence=[]; usage=[]; tools=[]; completions=[]
    for line in source.read_text().splitlines():
        item=json.loads(line); kind=item.get('type'); payload=item.get('payload',{})
        if kind=='turn_context':
            models.append({'model':payload.get('model'),'effort':payload.get('effort')})
        elif kind=='response_item':
            typ=payload.get('type')
            if typ in {'function_call','function_call_output','custom_tool_call','custom_tool_call_output'}:
                # Tool evidence only. Do not export reasoning records.
                evidence.append(item)
                if typ in {'function_call','custom_tool_call'}: tools.append(payload)
            elif typ=='message' and payload.get('role')=='assistant' and (payload.get('channel')=='final' or payload.get('phase')=='final_answer'):
                text='\n'.join(c.get('text','') for c in payload.get('content',[]) if c.get('type')=='output_text')
                if text: finals.append(text); evidence.append(item)
        elif kind=='event_msg' and payload.get('type')=='token_count':
            usage.append(payload.get('info',{}))
        elif kind=='event_msg' and payload.get('type')=='task_complete':
            completions.append({k:payload.get(k) for k in ('turn_id','started_at','completed_at','duration_ms')})
    if not models or any(m!={'model':'gpt-6.1-sol','effort':'medium'} for m in models):
        raise ValueError(f'Unqualified model metadata: {models}')
    if not finals: raise ValueError('No terminal final response yet; do not infer completion from elapsed time')
    commands=[json.loads(x) for x in (directory/'commands.jsonl').read_text().splitlines()] if (directory/'commands.jsonl').exists() else []
    audit=[]
    for call in tools:
        name=call.get('name','')
        args=str(call.get('arguments',call.get('input','')))
        if name in {'functions.exec','exec'} and args.strip()==metadata.get('bootstrap_code'):
            continue
        if name not in {'functions.exec','exec'} or 'agent_io.py' not in args:
            audit.append({'tool':name,'arguments':args,'reason':'tool call bypasses scoped transport'})
        elif any(word in args for word in ['tools.view_image','tools.web__','tools.mcp__','tools.apply_patch','tools.write_stdin']):
            audit.append({'tool':name,'arguments':args,'reason':'additional unscoped tool access'})
    files={}; hashes={}
    for file in (directory/'repo').rglob('*'):
        if not file.is_file(): continue
        rel=file.relative_to(directory/'repo')
        if any(p in {'.git','.dart_tool','build','__pycache__','.agents'} for p in rel.parts): continue
        hashes[rel.as_posix()]=hashlib.sha256(file.read_bytes()).hexdigest()
        try: files[rel.as_posix()]=file.read_text()
        except UnicodeError: files[rel.as_posix()]='<binary>'
    turns=metadata['turns']
    turn={'index':len(turns),'request':request or (directory/'request.txt').read_text().split('USER TASK\n',1)[-1],
          'final':finals[-1],'files':files,'commands':commands,'collected_at':time.time(),'file_hashes':hashes}
    # Re-exporting the same terminal response must not fabricate a user turn.
    if turns and turns[-1]['final']==turn['final'] and turns[-1]['request']==turn['request']:
        turn['index']=turns[-1]['index']
        turns[-1]=turn
    else:
        turns.append(turn)
    metadata.update(agent_path=agent_path,session_id=source.stem.split('rollout-',1)[-1],
        model_evidence=models,native_usage=usage[-1] if usage else None,
        tool_audit=audit,completion_evidence=completions,
        elapsed_seconds=sum(c['duration_ms']/1000 for c in completions if c.get('duration_ms') is not None),status='collected')
    (directory/'run.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
    out=ROOT/'results'/run_id;out.mkdir(parents=True,exist_ok=True)
    (out/'native-tools.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in evidence))
    (out/'manifest.json').write_text(json.dumps({k:v for k,v in metadata.items() if k!='turns'},ensure_ascii=False,indent=2))
    (out/'turns.json').write_text(json.dumps(turns,ensure_ascii=False,indent=2))
    return {'run_id':run_id,'final':finals[-1],'models':models,'transport_violations':len(audit),'commands':len(commands)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run');p.add_argument('agent_path');p.add_argument('--request')
    args=p.parse_args();print(json.dumps(collect(args.run,args.agent_path,args.request),ensure_ascii=False))
