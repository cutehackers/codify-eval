"""Read retained native metadata after representative actors terminate.

Descriptive observed counters only. No dispatch or native authorization claim.
"""
import hashlib
import json
from pathlib import Path
import sys

from collect import find_session
import improvement_q01_dialogue_core_v1 as core


def collect(actor_path):
    queue=[actor_path];members=[];seen=set();unknown=[]
    while queue:
        name=queue.pop(0)
        if name in seen:continue
        seen.add(name)
        try:
            path=find_session(name);raw=Path(path).read_bytes()
            if not raw.endswith(b'\n'):raise ValueError('Incomplete native frontier')
            events=core.parse(raw);header=events[0]['payload']
            if header.get('agent_path')!=name:raise ValueError('Original actor path mismatch')
            counters=[e for e in events if e['type']=='event_msg' and e['payload'].get('type')=='token_count']
            usage=counters[-1]['payload'].get('info',{}).get('total_token_usage') if counters else None
            valid=type(usage) is dict and all(type(v) is int and v>=0 for v in usage.values())
            ended=[e['timestamp'] for e in events if e['type']=='event_msg' and e['payload'].get('type')=='task_complete']
            started=[e['timestamp'] for e in events if e['type']=='event_msg' and e['payload'].get('type')=='task_started']
            members.append({'actor_path':name,'native_uuid':header['id'],'source':str(path),
                'source_bytes':len(raw),'source_sha256':hashlib.sha256(raw).hexdigest(),
                'usage':usage if valid else None,'task_started':started,'task_complete':ended,
                'terminal_observed':bool(ended),'counter_valid':valid})
            for e in events:
                p=e['payload']
                if p.get('type')=='function_call' and core.route(p,'collaboration','spawn_agent'):
                    args=core.decode(p['arguments']);child=args.get('task_name')
                    if type(child) is str:queue.append(child if child.startswith('/root/') else name+'/'+child)
        except (ValueError,OSError,KeyError,TypeError) as error:
            unknown.append({'actor_path':name,'reason':str(error)})
    uuids=[m['native_uuid'] for m in members]
    complete=not unknown and len(uuids)==len(set(uuids)) and all(m['terminal_observed'] and m['counter_valid'] for m in members)
    totals={}
    for m in members:
        if m['usage']:
            for k,v in m['usage'].items():totals[k]=totals.get(k,0)+v
    return {'schema_version':1,'members':members,'unknown_members':unknown,'known_totals':totals,
        'all_discovered_members_terminal_with_counters':complete,'token_gate':False,
        'cached_input_is_subset':True,'reasoning_output_is_subset':True,
        'billable_currency_known':False,'native_authentication_framework_claim':False,
        'limits':['Native descendant discovery is descriptive, not adversarial sandbox proof',
                  'Research preparation/reviewer cost is reported separately from product actors']}


if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('actor_path unique_output_path required')
    value=collect(sys.argv[1])
    with Path(sys.argv[2]).open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps({'members':len(value['members']),'complete':value['all_discovered_members_terminal_with_counters'],
        'known_totals':value['known_totals']},sort_keys=True))
