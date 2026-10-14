import copy
import hashlib
import json
import unittest
import improvement_optional_member_cost_v1 as cost
from improvement_optional_usage_v2_probes import native, count


class Controls(unittest.TestCase):
    def fixture(self, roles=('root','worker1','worker2'), unbound=False):
        raw={};locators={};members=[];unbound_rows=[]
        for role in roles:
            path='/root/product'+('' if role=='root' else '/'+role)
            es=[json.loads(line) for line in native(path,'id-'+role,[count(10),count(30)]).splitlines()]
            for n,e in enumerate(es):e['timestamp']=f'2026-10-12T00:00:{n:02d}Z'
            value=b''.join(json.dumps(e).encode()+b'\n' for e in es);raw[path]=value;locators[path]='/native/'+role+'.jsonl'
            row={'job':role,'agent_path':path,'native_session_id':'id-'+role,'raw_bytes':len(value),'raw_sha256':hashlib.sha256(value).hexdigest()}
            (unbound_rows if unbound and role=='worker1' else members).append(row)
        proof={'root_path':'/root/product','members':members,'observed_unbound_sources':unbound_rows,
               'pending_allocation_slots':['worker1'] if unbound else [],'provided_allocation_joins_complete':not unbound}
        return proof,raw,locators

    def test_all_latest_cumulative_once(self):
        d=cost.usage_members(*self.fixture());self.assertEqual(d['observed_prefix_totals']['total_tokens'],90)
        self.assertEqual(d['distinct_uuid_count'],3);self.assertEqual(d['known_valid_prefix_category_totals']['total_tokens'],90)
        self.assertFalse(d['whole_final_cost_qualified'])

    def test_solo_two_turns(self):
        d=cost.usage_members(*self.fixture(('root',)));self.assertEqual(d['observed_prefix_totals']['total_tokens'],30)
        self.assertEqual(len(d['members'][0]['opened_turn_ids']),2)

    def test_pending_unbound_native_is_counted_but_whole_unknown(self):
        d=cost.usage_members(*self.fixture(('root','worker1'),True));self.assertIsNone(d['observed_prefix_totals'])
        self.assertEqual(d['known_valid_prefix_category_totals']['total_tokens'],60)
        self.assertTrue(d['known_valid_prefix_totals_are_partial'])
        self.assertEqual(d['unbound_observed_native_paths'],['/root/product/worker1'])

    def test_pending_without_source_not_zero(self):
        p,r,l=self.fixture(('root',));p['pending_allocation_slots']=['worker1'];p['provided_allocation_joins_complete']=False
        d=cost.usage_members(p,r,l);self.assertIsNone(d['observed_prefix_totals'])
        self.assertEqual(d['known_valid_prefix_category_totals']['total_tokens'],30)

    def test_worker_cannot_be_filtered_from_prefixes(self):
        p,r,l=self.fixture();r.pop('/root/product/worker1');l.pop('/root/product/worker1')
        with self.assertRaises(ValueError):cost.usage_members(p,r,l)

    def test_unbound_native_cannot_be_filtered(self):
        p,r,l=self.fixture(('root','worker1'),True);r.pop('/root/product/worker1');l.pop('/root/product/worker1')
        with self.assertRaises(ValueError):cost.usage_members(p,r,l)

    def test_prefix_append_or_rewrite_requires_new_membership_proof(self):
        for changed in [b'\n',b'changed']:
            p,r,l=self.fixture(('root',));r['/root/product']+=changed
            with self.assertRaises(ValueError):cost.usage_members(p,r,l)

    def test_extra_prefix_and_locator(self):
        p,r,l=self.fixture(('root',));r['/root/extra']=r['/root/product'];l['/root/extra']='/native/extra.jsonl'
        with self.assertRaises(ValueError):cost.usage_members(p,r,l)

    def test_duplicate_uuid(self):
        p,r,l=self.fixture(('root','worker1'));p['members'][1]['native_session_id']=p['members'][0]['native_session_id']
        with self.assertRaises(ValueError):cost.usage_members(p,r,l)

    def test_pending_consistency_and_locator(self):
        p,r,l=self.fixture(('root','worker1'),True);p['provided_allocation_joins_complete']=True
        with self.assertRaises(ValueError):cost.usage_members(p,r,l)
        p,r,l=self.fixture(('root',));l['/root/product']='relative.jsonl'
        with self.assertRaises(ValueError):cost.usage_members(p,r,l)

    def test_unbound_source_cannot_be_declared_reconciled(self):
        p,r,l=self.fixture(('root','worker1'),True);p['pending_allocation_slots']=[];p['provided_allocation_joins_complete']=True
        with self.assertRaises(ValueError):cost.usage_members(p,r,l)

    def test_relative_member_cannot_escape_bound_root(self):
        p,r,l=self.fixture(('root','worker1'));p['members'][1]['agent_path']='worker1'
        with self.assertRaises(ValueError):cost.usage_members(p,r,l)


if __name__=='__main__':unittest.main()
