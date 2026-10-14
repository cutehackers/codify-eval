"""Record whole-session native usage without inventing billable currency."""
import argparse,hashlib,json,pathlib
from collect import find_session
ROOT=pathlib.Path(__file__).resolve().parents[1]
def usage(agent_path):
 source=find_session(agent_path);counts=[];models=[];ends=[]
 for line in source.read_text().splitlines():
  item=json.loads(line);p=item.get('payload',{})
  if item['type']=='turn_context':models.append({k:p.get(k) for k in ('model','effort')})
  if item['type']=='event_msg' and p.get('type')=='token_count':counts.append(p.get('info',{}))
  if item['type']=='event_msg' and p.get('type')=='task_complete':ends.append({k:p.get(k) for k in ('turn_id','duration_ms','started_at','completed_at')})
 if not models or any(m!={'model':'gpt-6.1-sol','effort':'medium'} for m in models):raise ValueError('Unqualified model or reasoning')
 total=counts[-1].get('total_token_usage') if counts else None
 return {'agent_path':agent_path,'native_source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_bytes':source.stat().st_size,'models':models,'completions':ends,'usage':total,'native_completion_observed':bool(ends),'status':'completed' if ends else 'no_native_completion_observed','metrics_unavailable':[] if total is not None else ['token_usage'],'billable_currency_observed':False,'scope':'Entire session; sum all participating sessions exactly once, including failures; never sum cumulative per-event usage'}
def aggregate(records, expected_agent_paths):
 seen=set();groups={}
 for r in records:
  key=r['agent_path']
  if key in seen:raise ValueError('Duplicate session membership')
  seen.add(key);role=r['role']
  if role not in {'product','external_evaluation'}:raise ValueError('Unknown cost role')
  groups.setdefault(role,[]).append(r)
 if seen!=set(expected_agent_paths):raise ValueError('Incomplete or unexpected cohort membership')
 return {role:{'sessions':len(items),'observed_sessions':sum(i['usage'] is not None for i in items),'native_completions':sum(i['native_completion_observed'] for i in items),'usage':{k:sum(i['usage'].get(k,0) for i in items) if all(i['usage'] is not None and k in i['usage'] for i in items) else None for k in ('input_tokens','cached_input_tokens','output_tokens','total_tokens')},'all_attempts_included':True,'billable_currency_observed':False} for role,items in groups.items()}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('agent_path');p.add_argument('output');a=p.parse_args();d=usage(a.agent_path);out=pathlib.Path(a.output).resolve();out.relative_to(ROOT/'results/improvement-v1')
 if out.exists():raise ValueError('Preserve earlier usage receipt')
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(d,indent=2));print(json.dumps(d,ensure_ascii=False))
