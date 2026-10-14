import copy
import json
import unittest
import improvement_optional_inventory_v2 as inv
import improvement_q01_dialogue_core_v1 as core


def event(second, payload, kind='response_item'):
    return {'timestamp': f'2026-10-12T00:00:{second:02d}Z', 'type': kind, 'payload': payload}


class InventoryControls(unittest.TestCase):
    def source(self, count=2):
        paths = ['/root/product'] + [f'/root/product/worker{i}' for i in range(count)]
        rows = [{'agent_name': p, 'agent_status': {'completed': 'done'}} for p in paths]
        rows.append({'agent_name': '/root/product_other', 'agent_status': 'running'})
        return [event(0, {'id': 'parent'}, 'session_meta'),
                event(5, {'type': 'function_call', 'namespace': 'collaboration', 'name': 'list_agents',
                          'call_id': 'inventory', 'arguments': '{}'}),
                event(6, {'type': 'function_call_output', 'call_id': 'inventory',
                          'output': json.dumps({'agents': rows})})], {p: '2026-10-12T00:00:04Z' for p in paths}

    def check(self, events, members, commitment_change=None):
        raw = ('\n'.join(json.dumps(e) for e in events) + '\n').encode()
        commitment = {'parent_id': 'parent', 'root_path': '/root/product', 'member_paths': sorted(members, key=str),
                      'inventory_call_id': 'inventory', 'parent_sha256': core.digest(raw),
                      'parent_bytes': len(raw), 'no_more_delivery': True}
        if commitment_change: commitment.update(commitment_change)
        return inv.completed_inventory(raw, 'parent', members, 'inventory', commitment)

    def test_valid_cardinalities(self):
        for n in range(3):
            with self.subTest(n=n):
                result = self.check(*self.source(n))
                self.assertFalse(result['cleanup_authorized'])
                self.assertFalse(result['native_qualified'])

    def test_bad_current_rows(self):
        for change in ['missing', 'extra', 'nested', 'duplicate', 'running', 'interrupted']:
            with self.subTest(change=change):
                e,m = self.source(); rows=json.loads(e[-1]['payload']['output'])['agents']
                if change=='missing': rows.pop(0)
                elif change=='extra': rows.append({'agent_name':'/root/product/unregistered','agent_status':{'completed':'done'}})
                elif change=='nested': rows.append({'agent_name':'/root/product/worker0/child','agent_status':{'completed':'done'}})
                elif change=='duplicate': rows.append(copy.deepcopy(rows[0]))
                else: rows[0]['agent_status'] = 'running' if change=='running' else {'interrupted':'done'}
                e[-1]['payload']['output']=json.dumps({'agents':rows})
                with self.assertRaises(ValueError): self.check(e,m)

    def test_stale_and_pending_inventory(self):
        for receipt in [False,True]:
            e,m=self.source(); e.append(event(7,{'type':'function_call','namespace':'collaboration','name':'list_agents','call_id':'later','arguments':'{}'}))
            if receipt: e.append(event(8,{'type':'function_call_output','call_id':'later','output':'{"agents":[]}'}))
            with self.assertRaises(ValueError): self.check(e,m)

    def test_filtered_inventory(self):
        e,m=self.source(); e[1]['payload']['arguments']='{"path_prefix":"/root/product"}'
        with self.assertRaises(ValueError): self.check(e,m)

    def test_pending_duplicate_and_wrong_receipt(self):
        for change in ['pending','duplicate','custom']:
            e,m=self.source()
            if change=='pending': e.pop()
            elif change=='duplicate': e.append(copy.deepcopy(e[-1]))
            else: e[-1]['payload']['type']='custom_tool_call_output'
            with self.assertRaises(ValueError): self.check(e,m)

    def test_late_completion(self):
        e,m=self.source(); m['/root/product']='2026-10-12T00:00:07Z'
        with self.assertRaises(ValueError): self.check(e,m)

    def test_no_more_delivery_exact_fence(self):
        for c in [{'no_more_delivery':False},{'parent_bytes':1},{'parent_sha256':'bad'},{'member_paths':[]}]:
            with self.assertRaises(ValueError): self.check(*self.source(),commitment_change=c)

    def test_later_operations(self):
        for name,target in [('spawn_agent',None),('followup_task','/root/product'),('send_message','worker0'),('interrupt_agent','/root/product/worker1')]:
            e,m=self.source(); args={'task_name':'new'} if target is None else {'target':target}
            e.append(event(7,{'type':'function_call','namespace':'collaboration','name':name,'call_id':'activity','arguments':json.dumps(args)}))
            with self.assertRaises(ValueError): self.check(e,m)

    def test_foreign_later_delivery(self):
        e,m=self.source();e.append(event(7,{'type':'function_call','namespace':'collaboration','name':'send_message','call_id':'foreign','arguments':'{"target":"/root/unrelated"}'}))
        self.check(e,m)

    def test_wrong_parent(self):
        e,m=self.source();e[0]['payload']['parent_thread_id']='another'
        with self.assertRaises(ValueError):self.check(e,m)

    def test_non_immediate_member(self):
        e,m=self.source();m['/root/product/worker0/child']='2026-10-12T00:00:04Z'
        with self.assertRaises(ValueError):self.check(e,m)

    def test_queued_delivery_before_inventory(self):
        e,m=self.source()
        e.insert(1,event(4,{'type':'function_call','namespace':'collaboration','name':'followup_task',
                          'call_id':'queued','arguments':'{"target":"/root/product/worker0"}'}))
        with self.assertRaises(ValueError): self.check(e,m)

    def test_relative_delivery(self):
        for target in ['product/worker0','product','unresolved']:
            e,m=self.source();e.append(event(7,{'type':'function_call','namespace':'collaboration',
                'name':'send_message','call_id':'relative','arguments':json.dumps({'target':target})}))
            with self.assertRaises(ValueError):self.check(e,m)

    def test_wrong_event_type(self):
        for i in [1,2]:
            e,m=self.source();e[i]['type']='event_msg'
            with self.assertRaises(ValueError):self.check(e,m)

    def test_integer_commitment(self):
        with self.assertRaises(ValueError):self.check(*self.source(),commitment_change={'no_more_delivery':1})

    def test_overflow_numbers(self):
        e,m=self.source();e[-1]['payload']['output']=e[-1]['payload']['output'][:-1]+',"extra":1e999}'
        with self.assertRaises(ValueError):self.check(e,m)
        e,m=self.source();e[0]['payload']['extra']=float('inf')
        with self.assertRaises(ValueError):self.check(e,m)

    def test_worker_only_subtree(self):
        e,m=self.source();m={'/root/product/worker0':'2026-10-12T00:00:04Z'}
        with self.assertRaises(ValueError):self.check(e,m)

    def test_mixed_path_types(self):
        e,m=self.source();m[1]='2026-10-12T00:00:04Z'
        with self.assertRaises(ValueError):self.check(e,m)


if __name__ == '__main__': unittest.main()
