"""Actual retired nested actor joins. No closure/qualification promotion."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

import improvement_optional_inventory_v4 as inventory

ROOT=Path(__file__).resolve().parents[1]


class RetiredControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out=ROOT/'runtime/native-optional-control-v7-one_worker/native-close'
        known=json.loads((out/'failed-native-closure.json').read_bytes())
        cls.parent=(out/'failed-closure-coordinator.jsonl').read_bytes()
        cls.root=(out/'root.jsonl').read_bytes();cls.child=(out/'worker1.jsonl').read_bytes()
        cls.commit=known['commitment'];cls.completions={p:v['completion'] for p,v in known['native_terminal_evidence'].items()}
        cls.root_path=cls.commit['root_path'];cls.child_path=cls.root_path+'/worker1'

    def invoke(self,parent=None,root=None,children=None,completions=None):
        parent=self.parent if parent is None else parent;commit=copy.deepcopy(self.commit)
        commit['parent_sha256']=hashlib.sha256(parent).hexdigest();commit['parent_bytes']=len(parent)
        return inventory.completed_inventory(parent,commit['parent_id'],self.completions if completions is None else completions,
            commit['inventory_call_id'],commit,self.root if root is None else root,{self.child_path:self.child} if children is None else children)

    def test_original_retired_child_has_completed_source_and_exact_in_turn_final(self):
        value=self.invoke()
        self.assertEqual(value['current_listed_member_paths'],[self.root_path])
        self.assertEqual(set(value['original_completed_children_absent_from_live_inventory']),{self.child_path})
        self.assertFalse(value['native_qualified']);self.assertFalse(value['cleanup_authorized'])

    def test_retired_child_without_source_or_complete_bytes_denied(self):
        for children in ({},{self.child_path:self.child[:-1]}):
            with self.assertRaises(ValueError):self.invoke(children=children)

    def test_changed_completion_not_replaced_by_current_missing_status(self):
        completions=copy.deepcopy(self.completions);completions[self.child_path]='2026-10-12T05:44:13.345Z'
        with self.assertRaises(ValueError):self.invoke(completions=completions)

    def test_completed_root_required_and_extra_live_descendant_denied(self):
        for change in ('root_missing','root_running','extra'):
            events=inventory.core.parse(self.parent)
            receipt=next(e['payload'] for e in events if e['payload'].get('call_id')==self.commit['inventory_call_id'] and e['payload'].get('type')=='function_call_output')
            body=json.loads(receipt['output']);row=next(r for r in body['agents'] if r['agent_name']==self.root_path)
            if change=='root_missing':body['agents'].remove(row)
            elif change=='root_running':row['agent_status']='running'
            else:body['agents'].append({'agent_name':self.root_path+'/unregistered','agent_status':{'completed':'done'}})
            receipt['output']=json.dumps(body)
            parent=b''.join(json.dumps(e).encode()+b'\n' for e in events)
            with self.assertRaises(ValueError):self.invoke(parent=parent)


if __name__=='__main__':unittest.main()
