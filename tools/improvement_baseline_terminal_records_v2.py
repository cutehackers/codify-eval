"""Pure terminal decoding, not actor inventory or cleanup authorization.

Normal actors use the qualified lifecycle decoder. Failed actors retain pending
tool IDs and observed usage. Caller must independently authenticate turn approval,
original source, native API status and interruption receipt before cleanup.
"""
import improvement_baseline_question_lifecycle_v3 as lifecycle

core=lifecycle.core
require=core.require


def terminal(raw,binding,turn_contract,*,child_sources=None,first_turn_raw=None,
             first_turn_contract=None,first_child_sources=None):
    children={} if child_sources is None else child_sources
    expected=turn_contract['expected_turns']
    lifecycle.decoded_turn_contract(raw,binding,expected,turn_contract)
    events,header=lifecycle.membership.source(raw,binding['agent_path'],binding['parent_native_id'])
    require(header['id']==binding['actor_native_id'],'Original failed actor UUID changed')
    last=events[-1];payload=last['payload']
    interrupted=last['type']=='event_msg' and payload.get('type')=='turn_aborted'
    errored=last['type']=='event_msg' and payload.get('type')=='task_complete' and payload.get('error') is not None
    if not interrupted and not errored:
        _,turns=lifecycle.lifecycle(raw,binding,expected,children,turn_contract=turn_contract)
        return {'status':'completed','completed_at':turns[-1]['completed_at'],
                'api_text':turns[-1]['final_text'],'turns':turns,'pending_call_ids':[],
                'cleanup_authorized':False,'software_pass':None}
    starts=[i for i,e in enumerate(events) if e['type']=='event_msg' and e['payload'].get('type')=='task_started']
    contexts=[i for i,e in enumerate(events) if e['type']=='turn_context']
    parent_path=binding['agent_path'].rsplit('/',1)[0]
    incoming=[i for i,e in enumerate(events) if e['payload'].get('type')=='agent_message'
              and e['payload'].get('author')==parent_path]
    require(len(starts)==len(contexts)==len(incoming)==expected,'Exact approved failed turn count required')
    require(all(events[i]['type']=='response_item' for i in incoming), 'Genuine received parent response items required')
    require([lifecycle.turn_id(events[i]['payload']) for i in contexts]==turn_contract['turn_ids'],
            'Failed contexts differ from approved native turn IDs')
    first_end=-1
    if expected==2:
        require(type(first_turn_raw) is bytes and raw.startswith(first_turn_raw),
                'Original authenticated completed first-turn prefix required')
        require(first_turn_contract is not None and first_turn_contract['expected_turns']==1,
                'First completed turn contract required')
        _,first=lifecycle.lifecycle(first_turn_raw,binding,1,first_child_sources or {},turn_contract=first_turn_contract)
        require(first[0]['turn_id']==turn_contract['turn_ids'][0],'First completed turn identity changed')
        first_end=len(core.parse(first_turn_raw))-1
    start,context,request=starts[-1],contexts[-1],incoming[-1]
    require(first_end<start<context<request<len(events)-1,'Failed last-turn ordering changed')
    identity=turn_contract['turn_ids'][-1]
    require(all(lifecycle.turn_id(events[i]['payload'])==identity for i in (start,context,request,len(events)-1)),
            'Failed start/context/request/terminal turn identity changed')
    require(events[request]['payload'].get('recipient')==binding['agent_path'],
            'Failed original request recipient changed')
    require(all(i<incoming[0] for i,e in enumerate(events) if e['payload'].get('type')=='user_message'
                or (e['payload'].get('type')=='message' and e['payload'].get('role')=='user')),
            'Unapproved user input into failed actor')
    for i,e in enumerate(events[:start]):
        p=e['payload'];kind=p.get('type')
        previous_lifecycle=kind in ('task_complete','turn_aborted','function_call','custom_tool_call','function_call_output','custom_tool_call_output')
        previous_final=kind=='message' and p.get('role')=='assistant' and (p.get('channel')=='final' or p.get('phase')=='final_answer')
        require(not (previous_lifecycle or previous_final) or expected==2 and i<=first_end,
                'Earlier terminal/final/tool outside verified first-turn prefix')
    tail=events[start:]
    require(not any(e['payload'].get('type') in ('task_complete','turn_aborted') for e in tail[:-1])
            and not any(e['payload'].get('type')=='message' and e['payload'].get('role')=='assistant'
                and (e['payload'].get('channel')=='final' or e['payload'].get('phase')=='final_answer') for e in tail),
            'Failed turn cannot contain a normal final or earlier terminal')
    for i,e in enumerate(events):
        p=e['payload']
        if p.get('type')=='agent_message' and p.get('author')!=parent_path:
            require(e['type']=='response_item' and p.get('author') in children and p.get('recipient')==binding['agent_path'],
                    'Unregistered failed actor delivery')
    calls={};outputs=set()
    for i,e in enumerate(events):
        if i<start:continue
        p=e['payload'];kind=p.get('type')
        if kind not in ('function_call','custom_tool_call','function_call_output','custom_tool_call_output'):continue
        require(request<i<len(events)-1 and e['type']=='response_item','Tool outside received failed turn')
        cid=p.get('call_id');require(type(cid) is str and bool(cid),'Original failed tool ID required')
        if kind.endswith('_output'):
            require(cid in calls and cid not in outputs,'Orphan/duplicate failed output')
            outputs.add(cid)
        else:
            require(cid not in calls,'Duplicate failed tool ID');calls[cid]=i
    completed=core.instant(last['timestamp']).timestamp()
    started=core.instant(events[start]['timestamp']).timestamp()
    require(completed>=started,'Failed terminal precedes start')
    if interrupted:
        require(set(payload)=={'type','turn_id','root_turn_id','reason','started_at','completed_at','duration_ms'}
                and payload['reason']=='interrupted','Exact genuine interrupted terminal required')
        root_id=payload['root_turn_id']
        require(type(root_id) is str and bool(root_id)
                and all(events[i]['payload'].get('root_turn_id')==root_id for i in (start,context)),
                'Corresponding root-turn identity changed')
        require(all(type(payload[key]) is int and payload[key]>=0 for key in ('started_at','completed_at','duration_ms')),
                'Exact nonnegative native interruption timing fields required')
        require(events[start]['payload'].get('started_at')==payload['started_at']
                and abs(started-payload['started_at'])<1
                and abs(completed-payload['completed_at'])<1
                and abs((completed-started)*1000-payload['duration_ms'])<1000,
                'Interrupted chronology differs beyond native timing precision')
        status='interrupted';api_text=None
    else:
        error=payload['error']
        require(type(error) is dict and set(error)=={'message','codex_error_info'}
                and error['codex_error_info']=='server_overloaded'
                and type(error['message']) is str and bool(error['message'])
                and payload.get('last_agent_message') is None,'Recognized original capacity error required')
        status='errored';api_text=error['message']
    usage=None
    for e in events:
        if e['payload'].get('type')=='token_count':
            candidate=e['payload'].get('info',{}).get('total_token_usage')
            if candidate is not None:
                require(type(candidate) is dict and 'total_tokens' in candidate
                        and all(type(v) is int and v>=0 for v in candidate.values()),'Typed observed cumulative usage required')
                usage=dict(candidate)
    return {'status':status,'completed_at':last['timestamp'],'api_text':api_text,
            'turn_id':identity,'pending_call_ids':sorted(set(calls)-outputs),
            'last_observed_cumulative_usage':usage,'complete_billed_cost':False,
            'cleanup_authorized':False,'software_pass':None,'model_pilot_admitted':False}
