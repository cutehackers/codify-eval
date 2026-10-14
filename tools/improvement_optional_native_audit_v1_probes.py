"""Retrospective actual solo evidence joins, not prospective qualification."""
import copy
import json
from pathlib import Path
import unittest

import improvement_optional_native_audit_v1 as audit
import improvement_optional_broker_v10 as broker

ROOT=Path(__file__).resolve().parents[1]


class CompositeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder=ROOT/'runtime/native-optional-control-v3-solo';out=folder/'native-evidence'
        row=json.loads((folder/'native-dispatch/intents/root.json').read_bytes())
        state=audit.membership.registry.read(folder/'registry');config=state['configuration']
        source=out/'root.jsonl';raw=source.read_bytes();parent=(out/'coordinator-prefix.jsonl').read_bytes()
        closure=json.loads((ROOT/'results/improvement-v1/fresh-optional-native-control-native-closure-v3-solo.json').read_bytes())
        control=json.loads((folder/'broker/root/control.json').read_bytes());path=row['intent']['agent_path']
        contract={'job':'root','agent_path':path,'run_name':folder.name,'broker_script':str(Path(broker.__file__).resolve()),
                  'capability_sha256':control['capability_sha256'],'request_sha256':row['intent']['public_request_sha256'],
                  'reply_sha256':None,'spawns':{}}
        provision={'run_id':config['run_id'],'configuration_sha256':audit.membership.original.digest(config),'jobs':{'root':row['provision']}}
        cls.inputs=[config,state,row['intent'],{},parent,raw,{},provision,folder/'registry',
                    {path:contract},{path:broker.ledger(folder,'root')},{path:str(source)},
                    closure['no_more_delivery_commitment']['inventory_call_id'],closure['no_more_delivery_commitment']]

    def values(self):
        # Immutable raw bytes are shared, mutable control objects copied.
        return [copy.deepcopy(v) if isinstance(v,(dict,list)) else v for v in self.inputs]

    def test_actual_original_solo_join_retains_whole_counter_once_without_qualification(self):
        value=audit.audit(*self.values())
        self.assertTrue(value['observed_native_dimensions_pass'])
        self.assertEqual(value['usage']['distinct_uuid_count'],1)
        self.assertEqual(value['usage']['observed_prefix_totals']['total_tokens'],372865)
        self.assertFalse(value['native_qualified']);self.assertFalse(value['whole_final_cost_qualified'])
        self.assertFalse(value['cleanup_authorized']);self.assertFalse(value['comparison_eligible'])

    def test_allocation_binding_cannot_change_lifecycle_identity(self):
        value={'agent_path':'/root/a','native_session_id':'id','binding':{'child_path':'/root/b','child_native_id':'id','parent_native_id':'parent'}}
        with self.assertRaises(ValueError):audit.lifecycle_binding(value)

    def test_missing_contract_ledger_or_native_locator_denied(self):
        for index in (9,10,11):
            values=self.values();values[index]={}
            with self.assertRaises(ValueError):audit.audit(*values)

    def test_wrong_role_capability_and_public_request_hash_denied(self):
        for key in ('capability_sha256','request_sha256'):
            values=self.values();contract=next(iter(values[9].values()));contract[key]='0'*64
            with self.assertRaises(ValueError):audit.audit(*values)

    def test_fabricated_integration_clock_or_repeat_denied(self):
        for change in ('too_early','too_late','boolean','repeat'):
            values=self.values();ledger=next(iter(values[10].values()));integration=next(row for row in ledger if row['request']['op']=='integrate')
            if change=='repeat':ledger.append(copy.deepcopy(integration))
            else:integration['started_at']={'too_early':values[0]['started_at']-1,'too_late':values[0]['deadline']+1,'boolean':True}[change]
            with self.assertRaises(ValueError):audit.audit(*values)

    def test_zero_one_two_worker_completion_order_and_early_native_dispatch(self):
        values=self.values();path=next(iter(values[9]));raw=values[5];contract=values[9][path];ledger=values[10][path]
        final=audit.inventory.decoded(audit.membership.reservation_prefix(values[8])['full_events_raw'].splitlines()[-1])
        ends=[e for e in audit.inventory.core.parse(raw) if e['type']=='event_msg' and e['payload'].get('type')=='task_complete']
        root_end=audit.inventory.core.instant(ends[-1]['timestamp']).timestamp()
        starts=[audit.inventory.core.instant(e['timestamp']).timestamp() for e in audit.inventory.core.parse(raw)
                if e['payload'].get('type')=='custom_tool_call' and audit.routes.poll(e['payload']['input']) is None
                and audit.routes.wrapper(e['payload']['input'],contract)['op']=='integrate']
        for count in range(3):
            self.assertTrue(audit.integration_order(raw,contract,values[0],ledger,[starts[0]-i-1 for i in range(count)],root_end,final['at']))
        with self.assertRaises(ValueError):audit.integration_order(raw,contract,values[0],ledger,[starts[0]+1],root_end,final['at'])
        with self.assertRaises(ValueError):audit.integration_order(raw,contract,values[0],ledger,[],root_end,starts[0]-1)

    def test_wrong_or_stale_current_inventory_and_false_delivery_commitment_denied(self):
        for change in ('wrong_id','false_commitment'):
            values=self.values()
            if change=='wrong_id':values[12]='wrong'
            else:values[13]['no_more_delivery']=False
            with self.assertRaises(ValueError):audit.audit(*values)


if __name__=='__main__':unittest.main()
