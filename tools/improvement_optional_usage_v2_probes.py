"""Synthetic counter/member coverage only, no native allocation qualification."""
import copy
import json
import unittest

import improvement_optional_usage_v2 as usage


def count(total):
    return {'input_tokens':total-2,'cached_input_tokens':total-3,'cache_write_input_tokens':0,
            'output_tokens':2,'reasoning_output_tokens':1,'total_tokens':total}


def native(path,identity,counts,completed=True):
    events=[{'type':'session_meta','payload':{'id':identity,'agent_path':path}}]
    for number,value in enumerate(counts):
        turn=f'turn{number}'
        events.extend([{'type':'event_msg','payload':{'type':'task_started','turn_id':turn}},
                       {'type':'turn_context','payload':{'turn_id':turn,'model':'gpt-6.1-sol','effort':'medium'}}])
        if value is not None:events.append({'type':'event_msg','payload':{'type':'token_count','info':{'total_token_usage':value}}})
        if completed:events.append({'type':'event_msg','payload':{'type':'task_complete','turn_id':turn}})
    return b''.join(json.dumps(e).encode()+b'\n' for e in events)


def member(role):
    return {'agent_path':'/root/product'+('' if role=='root' else '/'+role),
            'native_session_id':'uuid-'+role,'role':role,'source':'immutable-'+role+'.jsonl'}


class WholeMemberCounters(unittest.TestCase):
    def summarize(self,counts,roles=('root',),**kwargs):
        rows=[member(role) for role in roles]
        raw={r['agent_path']:native(r['agent_path'],r['native_session_id'],counts[r['role']]) for r in rows}
        return usage.summarize(rows,raw,**kwargs)

    def test_solo_and_cumulative_two_turns_count_last_once(self):
        result=self.summarize({'root':[count(10),count(30)]})
        self.assertEqual(result['observed_prefix_totals']['total_tokens'],30)
        self.assertEqual(result['distinct_uuid_count'],1)
        self.assertEqual(len(result['members'][0]['opened_turn_ids']),2)
        self.assertFalse(result['complete_final_cost'])

    def test_all_workers_included_independent_of_artifact_decision(self):
        result=self.summarize({'root':[count(30)],'worker1':[count(12)],'worker2':[count(18)]},
                              roles=('root','worker1','worker2'))
        self.assertEqual(result['observed_prefix_totals']['total_tokens'],60)
        self.assertEqual(result['observed_prefix_totals']['input_tokens'],54)
        self.assertEqual(result['observed_prefix_totals']['cached_input_tokens'],51)
        self.assertFalse(result['allocation_membership_qualified'])

    def test_pending_allocation_never_becomes_zero_cost(self):
        result=self.summarize({'root':[count(30)]},pending_slots=['worker1'])
        self.assertIsNone(result['observed_prefix_totals'])
        self.assertEqual(result['members'][0]['usage']['total_tokens'],30)

    def test_missing_allocated_member_makes_whole_total_unknown(self):
        root,worker=member('root'),member('worker1')
        result=usage.summarize([root,worker],{root['agent_path']:native(root['agent_path'],root['native_session_id'],[count(30)])})
        self.assertIsNone(result['observed_prefix_totals'])
        self.assertEqual(result['unknown_usage_paths'],[worker['agent_path']])

    def test_unknown_usage_not_zero(self):
        result=self.summarize({'root':[None]})
        self.assertIsNone(result['observed_prefix_totals'])
        self.assertIsNone(result['members'][0]['usage'])

    def test_invalid_negative_bool_missing_and_subset_counters_unknown(self):
        for field,value in [('input_tokens',-1),('total_tokens',True),('cached_input_tokens',100),
                            ('reasoning_output_tokens',100),('total_tokens',999)]:
            bad=count(30);bad[field]=value
            result=self.summarize({'root':[bad]})
            self.assertIsNone(result['observed_prefix_totals'])
        bad=count(30);del bad['cache_write_input_tokens']
        self.assertIsNone(self.summarize({'root':[bad]})['observed_prefix_totals'])

    def test_invalid_early_counter_not_hidden_by_later_valid_total(self):
        bad=count(10);bad['total_tokens']=False
        result=self.summarize({'root':[bad,count(30)]})
        self.assertIsNone(result['observed_prefix_totals'])

    def test_backwards_cumulative_count_unknown(self):
        result=self.summarize({'root':[count(30),count(10)]})
        self.assertIsNone(result['observed_prefix_totals'])

    def test_duplicate_uuid_path_and_role_denied(self):
        for key in ('native_session_id','agent_path','role'):
            root,worker=member('root'),member('worker1');worker[key]=root[key]
            with self.assertRaises(ValueError):usage.summarize([root,worker],{})

    def test_unregistered_record_denied_and_uuid_conflict_denied(self):
        root=member('root')
        with self.assertRaises(ValueError):usage.summarize([root],{'unknown':b'ignored'})
        with self.assertRaises(ValueError):usage.summarize([root],{root['agent_path']:native(root['agent_path'],'other-uuid',[count(30)])})

    def test_interrupted_prefix_counters_preserved_completion_not_invented(self):
        root=member('root');raw=native(root['agent_path'],root['native_session_id'],[count(30)],completed=False)
        result=usage.summarize([root],{root['agent_path']:raw})
        self.assertEqual(result['observed_prefix_totals']['total_tokens'],30)
        self.assertFalse(result['all_supplied_member_completions_observed'])
        self.assertFalse(result['complete_final_cost'])

    def test_duplicate_counter_key_cannot_hide_prior_negative_value(self):
        root=member('root');raw=native(root['agent_path'],root['native_session_id'],[count(30)])
        raw=raw.replace(b'"input_tokens": 28',b'"input_tokens": -5, "input_tokens": 28')
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            usage.summarize([root],{root['agent_path']:raw})

    def test_nonfinite_json_and_duplicate_header_key_denied(self):
        root=member('root');raw=native(root['agent_path'],root['native_session_id'],[count(30)])
        for bad in [raw.replace(b'"input_tokens": 28',b'"input_tokens": NaN'),
                    raw.replace(b'"id": "uuid-root"',b'"id": "wrong", "id": "uuid-root"')]:
            with self.assertRaises(ValueError):usage.summarize([root],{root['agent_path']:bad})

    def test_wrong_model_denied(self):
        root=member('root');raw=native(root['agent_path'],root['native_session_id'],[count(30)]).replace(b'gpt-6.1-sol',b'gpt-6-sol')
        with self.assertRaises(ValueError):usage.summarize([root],{root['agent_path']:raw})


if __name__=='__main__':unittest.main()
