"""Closed observed routes for supplied optional member evidence only.

Future broker must authenticate contract/ledger/turn authority and enforce rights.
This pure parser launches nothing and authorizes neither cleanup nor comparison.
"""
import hashlib
import json
import re
import shlex

import improvement_q01_dialogue_core_v1 as core
import improvement_optional_inventory_v3 as strict
import improvement_optional_membership_v2 as membership
import improvement_optional_lifecycle_v4 as lifecycle

ROOT_OPS = {'read', 'read_reply', 'exec', 'worker', 'view', 'decide', 'integrate', 'verify'}
WORKER_OPS = {'read', 'exec', 'seal'}
require = core.require


def literal_command(code):
    """Only one literal command, optional distinct literal infrastructure knobs."""
    require(isinstance(code, str) and len(code) <= 1048576, 'Bounded literal code required')
    pattern = r'text\s*\(\s*await\s+tools\.exec_command\s*\(\s*\{\s*"?cmd"?\s*:\s*("(?:\\.|[^"\\])*")(.*?)\}\s*\)\s*\)\s*;?'
    match = re.fullmatch(pattern, code.strip(), re.S)
    require(match is not None, 'Sole literal broker wrapper required')
    command = strict.decoded(match.group(1)); rest = match.group(2).strip(); seen = set()
    while rest and rest != ',':
        option = re.match(r',\s*("?(?:yield_time_ms|max_output_tokens)"?)\s*:\s*(0|[1-9][0-9]*)(?=\s*(?:,|$))', rest)
        require(option is not None, 'Unsupported infrastructure option')
        key = option.group(1).strip('"'); value = int(option.group(2))
        require(key not in seen, 'Duplicate infrastructure option')
        require(0 <= value <= (30000 if key == 'yield_time_ms' else 20000), 'Infrastructure option out of range')
        seen.add(key); rest = rest[option.end():].strip()
    return command


def poll(code):
    match = re.fullmatch(r'text\s*\(\s*await\s+tools\.write_stdin\s*\(\s*(\{[^{}]*\})\s*\)\s*\)\s*;?', code.strip(), re.S)
    if match is None:
        return None
    body = re.sub(r'(?<!["\w])([A-Za-z_]\w*)\s*:', r'"\1":', match.group(1))
    body = re.sub(r',\s*\}', '}', body.replace("''", '""'))
    options = strict.decoded(body)
    require(isinstance(options, dict) and set(options) <= {'session_id','chars','yield_time_ms','max_output_tokens'}
            and type(options.get('session_id')) is int and options['session_id'] > 0
            and options.get('chars','') == '', 'Empty owned poll required')
    for key in ('yield_time_ms','max_output_tokens'):
        if key in options:
            require(type(options[key]) is int and 0 <= options[key] <= (300000 if key == 'yield_time_ms' else 20000),
                    'Poll infrastructure option out of range')
    return options


def wrapper(code, contract):
    command = literal_command(code); parts = shlex.split(command)
    expected = ['python3', contract['broker_script'], '--run', contract['run_name'], '--job', contract['job'], '--cap']
    require(len(parts) == 12 and parts[:7] == expected and parts[8] == '--op' and parts[10] == '--data'
            and re.fullmatch('[0-9a-f]{48}', parts[7])
            and hashlib.sha256(parts[7].encode()).hexdigest() == contract['capability_sha256'],
            'Wrong broker run/job/capability/script')
    allowed = ROOT_OPS if contract['job'] == 'root' else WORKER_OPS
    require(parts[9] in allowed, 'Operation forbidden for role')
    base = shlex.join(parts[:11]) + ' '
    canonical = base + shlex.quote(parts[11])
    backslash_literal = base + "'" + parts[11].replace("'", "'\\''") + "'"
    require(command in (canonical, backslash_literal), 'Canonical POSIX literal required; no host expansions')
    data = strict.decoded(parts[11]); require(isinstance(data, dict), 'Broker data object required')
    return {'job':contract['job'], 'op':parts[9], 'data':data}


def same_json(left, right):
    """Preserve JSON scalar types: boolean true is never numeric one."""
    return json.dumps(left, sort_keys=True, separators=(',', ':'), allow_nan=False) == json.dumps(right, sort_keys=True, separators=(',', ':'), allow_nan=False)


def result(payload):
    output = payload.get('output')
    if isinstance(output, list):
        if len(output) == 2:
            require(all(isinstance(block,dict) and set(block)=={'type','text'}
                        and block['type']=='input_text' and isinstance(block['text'],str) for block in output),
                    'Exact native renderer plus one result block required')
            require(re.fullmatch(r'Script completed\nWall time (?:0|[1-9][0-9]*)(?:\.[0-9]+)? seconds\nOutput:\n',output[0]['text']) is not None,
                    'Unknown native renderer or nonterminal script frame')
            output=output[1]['text']
        else:
            require(len(output) == 1 and isinstance(output[0], dict) and output[0].get('type') == 'text',
                    'One execution result text required')
            output = output[0].get('text')
    require(isinstance(output, str), 'Execution result string required')
    value = strict.decoded(output)
    require(isinstance(value, dict) and isinstance(value.get('output'), str), 'Execution output unavailable')
    if 'exit_code' in value:
        require(type(value['exit_code']) is int and value.get('session_id') is None,
                'Terminal result cannot retain session')
    else:
        require(type(value.get('session_id')) is int and value['session_id'] > 0, 'Positive pending session required')
    return value


def audit_member(raw, immutable_binding, contract, broker_action_ledger_raw, turn_authority, child_sources=None):
    require(contract['job'] in ('root','worker1','worker2') and isinstance(contract.get('spawns'), dict),
            'Bounded role contract required')
    require(contract['agent_path'] == immutable_binding['agent_path'], 'Contract/binding path mismatch')
    role_path = r'/root/[A-Za-z0-9_]+' + ('' if contract['job']=='root' else '/'+contract['job'])
    require(re.fullmatch(role_path, contract['agent_path']) is not None, 'Native role/path mismatch')
    events, _ = membership.source(raw, contract['agent_path'], immutable_binding['parent_native_id'])
    require(isinstance(turn_authority, dict) and set(turn_authority) == {'turn_ids','native_sha256','approved'}
            and turn_authority['approved'] is True and turn_authority['native_sha256'] == core.digest(raw)
            and isinstance(turn_authority['turn_ids'], list) and len(turn_authority['turn_ids']) in (1,2),
            'Pinned supplied turn authority required')
    if child_sources is None:
        # Legacy standalone role parser retains its separately authenticated
        # one/two-turn interface. New normal composite always supplies sources.
        events, turns = core.lifecycle(raw, immutable_binding, len(turn_authority['turn_ids']))
    else:
        events, turns = lifecycle.lifecycle(raw, immutable_binding, len(turn_authority['turn_ids']),child_sources)
    require([t['turn_id'] for t in turns] == turn_authority['turn_ids'], 'Approved turn IDs changed')
    if contract['job'] != 'root':
        require(not contract['spawns'] and len(turns) == 1, 'Workers cannot delegate or resume')
    require(len(contract['spawns']) <= 2, 'Optional worker cap exceeded')
    ledger = strict.decoded(broker_action_ledger_raw)
    require(isinstance(ledger, list), 'Original action ledger list required')
    ids = set(); entries = []
    for entry in ledger:
        require(isinstance(entry, dict) and type(entry.get('action_id')) is int and entry['action_id'] >= 0
                and entry['action_id'] not in ids and isinstance(entry.get('request'), dict)
                and entry['request'].get('job') in ('root','worker1','worker2'), 'Unknown or duplicate action ledger row')
        ids.add(entry['action_id'])
        if entry['request']['job'] == contract['job']: entries.append(entry)
    calls = {}; outputs = set(); owned = {}; used_sessions = set(); routes = []; spawns = set()
    bootstrap_verified = False; reply_verified = len(turns) == 1; reply_started = False
    final_indexes = {t['final_index'] for t in turns}
    for index,event in enumerate(events):
        p = event['payload']; kind = p.get('type'); cid = p.get('call_id')
        if index in final_indexes:
            require(set(calls) == outputs and not owned, 'Turn final with outstanding native calls or sessions')
        if kind in ('function_call','custom_tool_call'):
            require(event.get('type') == 'response_item' and isinstance(cid,str) and cid and cid not in calls,
                    'Invalid or duplicate native call')
            turn = next((n for n,t in enumerate(turns) if t['incoming_index'] < index < t['final_index']), None)
            require(turn is not None, 'Call outside actual received turn')
            route = {'call_id':cid, 'call_type':kind, 'event':event, 'turn':turn}
            if core.route(p,'functions','exec'):
                require(not (p.get('input') is not None and p.get('arguments') is not None), 'Ambiguous execution source')
                code = p.get('input',p.get('arguments')); require(isinstance(code,str), 'Execution source required')
                options = poll(code)
                if options is not None:
                    sid = options['session_id']; require(sid in owned, 'Foreign or closed session poll')
                    origin = owned[sid]
                    require(origin['turn'] == turn and core.instant(event['timestamp']) >= origin['last_receipt'],
                            'Poll turn or clock changed')
                    route.update(mode='poll', session=sid, origin=origin)
                else:
                    request = wrapper(code,contract); op = request['op']
                    if not routes:
                        require(op == 'read' and request['data'] == {} and turn == 0, 'First sole public read required')
                    else:
                        require(bootstrap_verified and op != 'read', 'Work before complete bootstrap or repeated read')
                    if turn == 1 and not reply_verified:
                        require(op == 'read_reply' and request['data'] == {} and not reply_started, 'Second turn must read staged reply exactly once first')
                        reply_started = True
                    elif op == 'read_reply':
                        raise ValueError('Unexpected or repeated staged reply read')
                    route.update(mode='broker', request=request, chunks=[], outer_exit_code=None)
                    routes.append(route)
            elif contract['job'] == 'root' and kind == 'function_call':
                require(bootstrap_verified and (turn == 0 or reply_verified), 'Coordination before public input read')
                args = strict.decoded(p['arguments'])
                if core.route(p,'collaboration','spawn_agent'):
                    supplied = contract['spawns'].get(cid)
                    require(isinstance(supplied,dict) and cid not in spawns and set(args) == {'task_name','message','model','reasoning_effort','fork_turns'}
                            and args['task_name'] in ('worker1','worker2') and supplied['agent_path'] == contract['agent_path']+'/'+args['task_name']
                            and args['model'] == 'gpt-6.1-sol' and args['reasoning_effort'] == 'medium' and args['fork_turns'] == 'none'
                            and isinstance(args['message'],str) and args['message'].startswith('gAAAAA') and core.digest(args['message'].encode()) == supplied['request_token_sha256'],
                            'Unregistered native worker dispatch')
                    spawns.add(cid);route.update(mode='spawn',child=supplied['agent_path'])
                elif core.route(p,'collaboration','list_agents'):
                    require(args == {'path_prefix':contract['agent_path']}, 'Root may inspect only own subtree')
                    route['mode']='status'
                elif core.route(p,'collaboration','wait_agent'):
                    require(isinstance(args,dict) and set(args) == {'timeout_ms'} and type(args['timeout_ms']) is int
                            and 10000 <= args['timeout_ms'] <= 60000, 'Bounded native wait required')
                    route['mode']='wait'
                else:raise ValueError('Forbidden native coordinator route')
            else:raise ValueError('Forbidden native tool route')
            calls[cid]=route
        elif kind in ('function_call_output','custom_tool_call_output'):
            require(event.get('type') == 'response_item' and cid in calls and cid not in outputs, 'Orphan or duplicate receipt')
            route = calls[cid]; expected = 'custom_tool_call_output' if route['call_type']=='custom_tool_call' else 'function_call_output'
            require(kind == expected and core.instant(event['timestamp']) >= core.instant(route['event']['timestamp']), 'Receipt type/clock mismatch')
            received_turn = next((n for n,t in enumerate(turns) if t['incoming_index'] < index < t['final_index']), None)
            require(received_turn == route['turn'], 'Receipt outside original invocation turn')
            outputs.add(cid)
            if route['mode']=='spawn':
                require(strict.decoded(p['output']) == {'task_name':route['child']}, 'Actual worker success receipt required')
            elif route['mode'] in ('status','wait'):
                value = strict.decoded(p['output']); require(isinstance(value,dict), 'Native coordination receipt required')
                if route['mode']=='status':
                    allowed_paths = {contract['agent_path']} | {r['agent_path'] for r in contract['spawns'].values()}
                    agents = value.get('agents')
                    require(isinstance(agents,list) and all(isinstance(a,dict) and isinstance(a.get('agent_name'),str)
                            and a['agent_name'] in allowed_paths for a in agents)
                            and len({a['agent_name'] for a in agents}) == len(agents),
                            'Unregistered or duplicate status member')
            else:
                value=result(p); origin=route['origin'] if route['mode']=='poll' else route
                origin['chunks'].append(value['output']); origin['last_receipt']=core.instant(event['timestamp'])
                if route['mode']=='poll':
                    sid=route['session'];require(value.get('session_id') in (None,sid), 'Poll returned foreign session')
                    if 'exit_code' in value:del owned[sid]
                elif 'exit_code' not in value:
                    sid=value['session_id'];require(sid not in used_sessions, 'Async session reused')
                    used_sessions.add(sid);owned[sid]=origin
                if 'exit_code' in value:
                    origin['outer_exit_code']=value['exit_code']
                    if origin['request']['op'] in ('read','read_reply'):
                        body=strict.decoded(''.join(origin['chunks']))
                        require(value['exit_code']==0 and isinstance(body,dict) and body.get('status')=='ok'
                                and isinstance(body.get('result'),dict) and isinstance(body['result'].get('text'),str), 'Public input read failed')
                        expected_hash=contract['request_sha256'] if origin['request']['op']=='read' else contract.get('reply_sha256')
                        require(core.digest(body['result']['text'].encode())==expected_hash, 'Public input incomplete or changed')
                        if origin['request']['op']=='read':bootstrap_verified=True
                        else:reply_verified=True
    require(bootstrap_verified and reply_verified and set(calls)==outputs and not owned
            and spawns==set(contract['spawns']), 'Unclosed native calls, sessions or registered allocations')
    require(len(routes)==len(entries), 'Action/native request coverage mismatch')
    for route,entry in zip(routes,entries):
        require(same_json(entry['request'], route['request']), 'Action/native request differs')
        if entry.get('status')=='completed':
            require('result' in entry, 'Completed action result missing');expected={'status':'ok','result':entry['result']};code=0
        elif entry.get('status')=='failed':
            error=entry.get('error');require(isinstance(error,dict) and set(error)=={'type','message'} and all(isinstance(v,str) for v in error.values()), 'Action failure missing')
            expected={'status':'error',**error};code=1
        else:raise ValueError('Action remains pending')
        require(route['outer_exit_code']==code and same_json(strict.decoded(''.join(route['chunks'])), expected),
                'Actual broker result differs from original action ledger')
    return {'status':'normal_closed_observed_routes','native_sha256':core.digest(raw),'native_bytes':len(raw),
            'action_ledger_sha256':core.digest(broker_action_ledger_raw.encode() if isinstance(broker_action_ledger_raw,str) else broker_action_ledger_raw),
            'native_call_count':len(calls),'broker_request_count':len(routes),'actual_worker_spawn_ids':sorted(spawns),
            'turns':turns,'bootstrap_verified':bootstrap_verified,'native_qualified':False,
            'turn_authority_authenticated':False,'contract_ledger_authenticated':False,
            'cleanup_authorized':False,'comparison':False,'superiority':False}
