"""Pure allocation omission, identity, failure and cost counterexamples."""
import copy
import json

from improvement_allocation_v4 import discover, QUOTA


def event(second, kind, payload):
    return {'timestamp': f'2026-10-11T00:00:{second:02d}.000000Z', 'type': kind, 'payload': payload}


def node(identity, path, parent, second):
    return [event(second, 'session_meta', {'id': identity, 'session_id': 'shared-ancestor',
            'agent_path': path, 'parent_thread_id': parent,
            'source': {'subagent': {'thread_spawn': {'parent_thread_id': parent, 'agent_path': path}}}}),
            event(second, 'turn_context', {'turn_id': identity+'-turn', 'model': 'gpt-6.1-sol', 'effort': 'medium'}),
            event(20, 'event_msg', {'type': 'token_count', 'info': {'total_token_usage': {'input_tokens': 100, 'cached_input_tokens': 90, 'output_tokens': 1, 'total_tokens': 101}}}),
            event(21, 'event_msg', {'type': 'task_complete', 'turn_id': identity+'-turn'})]


def spawn(events, second, name, path, call_id):
    events[2:2] = [event(second, 'response_item', {'type': 'function_call', 'name': 'spawn_agent',
                  'namespace': 'collaboration', 'call_id': call_id, 'arguments': json.dumps({'task_name': name,
                   'fork_turns': 'none', 'model': 'gpt-6.1-sol', 'reasoning_effort': 'medium'})}),
                  event(second+2, 'response_item', {'type': 'function_call_output', 'call_id': call_id,
                  'output': json.dumps({'task_name': path})})]


def fixture():
    root = node('root', '/product', 'research', 1)
    worker = node('worker', '/product/worker', 'root', 3)
    grandchild = node('grandchild', '/product/worker/grandchild', 'worker', 6)
    spawn(root, 2, 'worker', '/product/worker', 'allocate-worker')
    spawn(worker, 5, 'grandchild', '/product/worker/grandchild', 'allocate-grandchild')
    return {'root.jsonl': root, 'worker.jsonl': worker, 'grandchild.jsonl': grandchild}


def encode(nodes):
    return {name: b''.join(json.dumps(e).encode()+b'\n' for e in events) for name, events in nodes.items()}


def main():
    outcomes = []
    def check(name, change, predicate, expected=None):
        sources = copy.deepcopy(fixture()); change(sources)
        result = discover(encode(sources), 'root', expected)
        assert predicate(result), name
        assert not result['complete_final_cost'] and not result['allocation_registry_completeness_attested'], name
        outcomes.append({'name': name, 'pass': True, 'verdict': result['verdict']})
    check('nested graph counted once despite shared ancestor ID', lambda n: None,
          lambda r: r['graph_consistent_observed_prefix'] and r['discovered_native_ids']==['grandchild','root','worker'] and r['observed_cost_totals']['total_tokens']==303)
    check('omitted grandchild caller membership fails', lambda n: None, lambda r:r['verdict']=='fail', ['root','worker'])
    check('alias duplicate UUID fails', lambda n:n.update(alias=copy.deepcopy(n['worker.jsonl'])), lambda r:r['verdict']=='fail')
    check('conflicting nested parent fails', lambda n:n['worker.jsonl'][0]['payload']['source']['subagent']['thread_spawn'].update(parent_thread_id='other'), lambda r:r['verdict']=='fail')
    check('successful missing child is known missing', lambda n:n.pop('grandchild.jsonl'), lambda r:any(a['outcome']=='known_missing' for a in r['attempts']))
    check('orphan descendant fails', lambda n:n['worker.jsonl'].__delitem__(slice(2,4)), lambda r:r['verdict']=='fail')
    check('quota rejection preserved without invented no-child authority', lambda n:n['worker.jsonl'][3]['payload'].update(output=QUOTA), lambda r:any(a['outcome']=='rejection_schema_observed_no_child_authority_unavailable' for a in r['attempts']))
    check('generic transport error remains unknown', lambda n:n['worker.jsonl'][3]['payload'].update(output='transport error'), lambda r:any(a['outcome']=='unknown' for a in r['attempts']))
    check('pending spawn receipt preserves attempt', lambda n:n['worker.jsonl'].pop(3), lambda r:any(a['outcome']=='pending' for a in r['attempts']))
    check('fork all fails despite requested model', lambda n:n['root.jsonl'][2]['payload'].update(arguments=json.dumps({'task_name':'worker','fork_turns':'all','model':'gpt-6.1-sol','reasoning_effort':'medium'})), lambda r:r['verdict']=='fail')
    check('actual model mismatch fails', lambda n:n['worker.jsonl'][1]['payload'].update(model='gpt-6-sol'), lambda r:r['verdict']=='fail')
    check('active worker retains observed tokens and blocks terminal claim', lambda n:n['worker.jsonl'].pop(), lambda r:not r['all_observed_sessions_normally_terminal'] and r['observed_cost_totals']['total_tokens']==303)
    check('missing tokens remain unavailable not zero', lambda n:n['grandchild.jsonl'].pop(2), lambda r:r['usage_unavailable_native_ids']==['grandchild'] and r['observed_cost_totals']['total_tokens']==202)
    check('external researcher sibling excluded from product cost', lambda n:n.update(researcher=node('researcher','/research/reviewer','research',2)), lambda r:r['observed_cost_totals']['total_tokens']==303 and 'researcher' not in r['discovered_native_ids'])
    check('duplicate call identity fails', lambda n:n['root.jsonl'].insert(3,copy.deepcopy(n['root.jsonl'][2])), lambda r:r['verdict']=='fail')
    check('backward receipt fails', lambda n:n['root.jsonl'].insert(2,n['root.jsonl'].pop(3)), lambda r:r['verdict']=='fail')
    check('wrong returned path fails', lambda n:n['root.jsonl'][3]['payload'].update(output=json.dumps({'task_name':'/wrong'})), lambda r:r['verdict']=='fail')
    check('unknown allocation namespace fails', lambda n:n['root.jsonl'][2]['payload'].update(namespace='other'), lambda r:r['verdict']=='fail')
    def cycle(nodes):
        h=nodes['root.jsonl'][0]['payload'];h['parent_thread_id']='worker'
        h['source']['subagent']['thread_spawn']['parent_thread_id']='worker'
    check('UUID ancestry cycle fails', cycle, lambda r:r['verdict']=='fail')
    check('wrong model retains observed failure cost', lambda n:n['worker.jsonl'][1]['payload'].update(model='gpt-6-sol'), lambda r:r['verdict']=='fail' and r['observed_cost_totals']['total_tokens']==303)
    check('empty token schema remains unavailable', lambda n:n['grandchild.jsonl'][2]['payload']['info'].update(total_token_usage={}), lambda r:r['usage_unavailable_native_ids']==['grandchild'] and r['observed_cost_totals']['total_tokens']==202)
    def ambiguous_path(nodes):
        other=copy.deepcopy(nodes['worker.jsonl']);other[0]['payload']['id']='worker2'
        other[1]['payload']['turn_id']='worker2-turn';other[-1]['payload']['turn_id']='worker2-turn'
        other[2:4]=[];nodes['worker2.jsonl']=other
    check('distinct UUID ambiguous path preserves both costs', ambiguous_path, lambda r:r['verdict']=='fail' and r['observed_cost_totals']['total_tokens']==404 and 'worker2' in r['discovered_native_ids'])
    check('missing cache preserves known per-metric totals', lambda n:n['grandchild.jsonl'][2]['payload']['info']['total_token_usage'].pop('cached_input_tokens'), lambda r:r['observed_cost_totals']['total_tokens']==303 and r['observed_cost_totals']['input_tokens']==300 and r['unavailable_metrics_by_native_id']=={'grandchild':['cached_input_tokens']})
    def null_total(nodes):
        nodes['grandchild.jsonl'].insert(-1,event(20,'event_msg',{'type':'token_count','info':{'total_token_usage':None}}))
    check('later null total preserves known observations', null_total, lambda r:r['observed_cost_totals']['total_tokens']==303 and r['usage_unavailable_native_ids']==['grandchild'])
    def null_info(nodes):
        nodes['grandchild.jsonl'].insert(-1,event(20,'event_msg',{'type':'token_count','info':None}))
    check('null info preserves graph and known observations', null_info, lambda r:r['discovered_native_ids']==['grandchild','root','worker'] and r['observed_cost_totals']['total_tokens']==303 and r['usage_unavailable_native_ids']==['grandchild'])
    raw=encode(fixture());raw['worker.jsonl']=raw['worker.jsonl'][:-1]
    result=discover(raw,'root');assert result['verdict']=='incomplete' and not result['complete_final_cost']
    assert result['observed_cost_totals']['total_tokens']==303 and not result['all_observed_sessions_normally_terminal']
    assert result['discovered_native_ids']==['grandchild','root','worker']
    outcomes.append({'name':'partial source blocks completeness','pass':True,'verdict':result['verdict']})
    print(json.dumps({'status':'pass','count':len(outcomes),'scope':'Pure observed-graph and counterexamples only; no runtime authority, live nested allocation or complete cost attestation','probes':outcomes},indent=2))


if __name__ == '__main__':
    main()
