"""Trusted ROOT bridge for one-turn, cap0, non-question terminal closure.

The actual calling ROOT owns configuration, original observer and exclusive
native dispatch. This source joins original native evidence and the full audit;
it cannot establish caller trust from files or JSON. No allocation occurs here.
Seal and normal close must run in the same ROOT tool call so their original
coordinator snapshot is identical. Later ordinary ROOT appends remain fenced.
"""
import copy
from pathlib import Path

import improvement_baseline_root_controller_v4 as startup
import improvement_baseline_normal_close_v7 as normal

runtime=normal.runtime
coordinator=normal.coordinator
require=runtime.require
encoded=runtime.encoded
ROOT=normal.ROOT
_context=None


class TerminalController:
    def __init__(self,original_startup,prepared_reference,root_locator,frozen_sources):
        require(isinstance(original_startup,startup.StartupController), 'Original ROOT startup context required')
        self.startup=original_startup
        self.row=copy.deepcopy(original_startup.row)
        require(self.row['case_id'] in ('B01','B02') and type(self.row['worker_cap']) is int
                and self.row['worker_cap']==0 and original_startup.assignment is None,
                'Initial actual closure is non-question, one-turn and cap0 only')
        self.folder=ROOT/'runtime'/self.row['run_id']
        self.prepared_reference=copy.deepcopy(prepared_reference)
        self.root_locator=str(Path(root_locator))
        self.graph=copy.deepcopy(frozen_sources)
        self.context_bytes=encoded({'row':self.row,'folder':str(self.folder),
            'prepared_reference':self.prepared_reference,'root_locator':self.root_locator,'graph':self.graph,
            'startup_context':original_startup.context_commitment.hex()})
        self.auth=None;self.audit_inputs_reference=None;self.close_started=False
        self.current_sources()

    def current_sources(self):
        require(encoded({'row':self.row,'folder':str(self.folder),
            'prepared_reference':self.prepared_reference,'root_locator':self.root_locator,'graph':self.graph,
            'startup_context':self.startup.context_commitment.hex()})==self.context_bytes,
            'Original terminal context changed')
        self.startup.current()
        reference=runtime.question_reference(Path(__file__).resolve())
        coordinator.source_fence(self.graph,[reference])
        require(self.prepared_reference['path']==str(self.folder/'coordinator/prepared.json'),
                'Original prepared row path required')
        prepared=runtime.strict.decoded(runtime.question_reference_bytes(self.prepared_reference))
        require(encoded(prepared['row'])==encoded(self.row)
                and encoded(prepared['configuration_reference'])==encoded(self.startup.configuration_reference)
                and encoded((prepared['original_started_at'],prepared['original_deadline']))
                    ==encoded(self.startup.original_clock),'Original prepared startup clock/configuration required')
        return prepared

    def seal(self):
        require(self.auth is None,'Original terminal authority cannot be resealed')
        self.current_sources()
        state,members=runtime.declared_runtime(self.folder,self.startup.root_capability)
        require(state['first_error'] is None and state['phase']=='running'
                and state['jobs']['root']['status']=='running' and set(state['jobs'])=={'root'}
                and not members['workers'],'Original successful root-only runtime required')
        config=members['configuration']
        origin=self.startup.owner.root_origin(self.root_locator,self.row['actor_path'])
        parent,parent_pin=self.startup.owner.parent()
        root_raw,root_pin=normal.preservation.capture.native_capture(self.root_locator,origin['child_entity'])
        require(parent.endswith(b'\n') and root_raw.endswith(b'\n'),'Original complete terminal native sources required')
        events=normal.audit.inventory.core.parse(root_raw)
        contexts=[e['payload'] for e in events if e['type']=='turn_context']
        require(len(contexts)==1,'One actual approved root turn required')
        native_id=origin['native_join']['child_native_id']
        binding={'agent_path':self.row['actor_path'],'actor_native_id':native_id,
                 'parent_native_id':self.startup.owner.value['parent_native_id']}
        turn={'schema_version':1,'binding':binding,'job':'root','expected_turns':1,
              'turn_ids':[normal.audit.routes.lifecycle.turn_id(contexts[0])],
              'native_sha256':normal.audit.inventory.core.digest(root_raw),'worker_cap':0,'phase':'terminal'}
        # Reject interrupted/error/incomplete turns before any closure effects.
        normal.audit.routes.lifecycle.lifecycle(root_raw,binding,1,{},turn_contract=turn)
        parent_events=normal.audit.inventory.core.parse(parent)
        inventories=[e['payload']['call_id'] for e in parent_events
            if e['payload'].get('type')=='function_call'
            and normal.audit.inventory.core.route(e['payload'],'collaboration','list_agents')]
        require(bool(inventories),'Actual latest unfiltered native inventory required')
        inventory_id=inventories[-1]
        path=self.row['actor_path']
        commitment={'parent_id':binding['parent_native_id'],'root_path':path,'member_paths':[path],
            'inventory_call_id':inventory_id,'parent_sha256':normal.audit.inventory.core.digest(parent),
            'parent_bytes':len(parent),'no_more_delivery':True}
        broker_control=self.folder/'broker/root/control.json'
        broker_value=runtime.strict.decoded(runtime.question_reference_bytes(runtime.question_reference(broker_control)))
        dispatch_path=self.folder/'native-dispatch/configuration.json'
        dispatch=runtime.strict.decoded(runtime.question_reference_bytes(runtime.question_reference(dispatch_path)))
        require(dispatch['coordinator_id']==binding['parent_native_id'] and dispatch['root_path']==path,
                'Original native dispatch owner/path required')
        route={'job':'root','agent_path':path,'run_name':self.row['run_id'],
               'broker_script':dispatch['broker_script'],
               'capability_sha256':runtime.hashed(self.startup.root_capability),
               'request_sha256':broker_value['request_sha256'],'spawns':{}}
        require(broker_value['job']=='root' and broker_value['run_id']==state['run_id']
                and broker_value['capability_sha256']==route['capability_sha256']
                and broker_value['configuration_sha256']==state['configuration_sha256'],
                'Original broker registration identity required')
        intent_path=self.folder/'native-dispatch/intents/root.json'
        intent=runtime.strict.decoded(runtime.question_reference_bytes(runtime.question_reference(intent_path)))
        provision={'run_id':config['run_id'],'configuration_sha256':normal.preservation.registry.sha(config),
                   'jobs':{'root':intent['provision']}}
        audit_inputs={'contracts':{path:route},'turn_contracts':{path:turn},
                      'inventory_call_id':inventory_id,'commitment':commitment}
        audit_proof=normal.audit.audit(config,members,intent['intent'],{},parent,root_raw,{},
            provision,self.folder/'registry',audit_inputs['contracts'],
            {path:normal.audit.original_ledger(self.folder,'root')},{path:self.root_locator},
            inventory_id,commitment,turn_contracts=audit_inputs['turn_contracts'])
        require(audit_proof['membership']['coordinator_native_id']==binding['parent_native_id']
                and len(audit_proof['membership']['members'])==1
                and audit_proof['membership']['members'][0]['native_session_id']==native_id,
                'Full audit differs from original native ROOT join')
        directory=self.folder/'root-terminal-authority';directory.mkdir()
        inputs_path=directory/'audit-inputs.json';runtime.atomic_json(inputs_path,audit_inputs,exclusive=True)
        auth={'schema_version':1,'mode':'normal_terminal','run_id':config['run_id'],
              'original_started_at':config['started_at'],'original_deadline':config['deadline'],
              'root_lifecycle_contract':turn,'inventory_call_id':inventory_id,'commitment':commitment,
              'control_pins':{'prepared':self.prepared_reference,
                'startup_binding':self.startup.binding_reference,
                'configuration':self.startup.configuration_reference,
                'broker_control':runtime.question_reference(broker_control),
                'dispatch_configuration':runtime.question_reference(dispatch_path),
                'root_intent':runtime.question_reference(intent_path),
                'audit_inputs':runtime.question_reference(inputs_path)},
              'ambiguous_delivery':[],'interrupt_receipt_references':{},
              'member_native_ids':{path:native_id}}
        self.parent=parent;self.latest_parent=parent;self.parent_pin=parent_pin
        self.root_raw=root_raw;self.root_pin=root_pin
        self.registry_fingerprint=normal.preservation.registry_snapshot_fingerprint(
            normal.preservation.membership.reservation_prefix(self.folder/'registry'))
        self.original_jobs=normal.preservation.immutable_job_fields(state)
        self.registry_state=copy.deepcopy(members);self.dispatch_row=copy.deepcopy(intent)
        self.audit_inputs_reference=auth['control_pins']['audit_inputs']
        self.auth=copy.deepcopy(auth);self.auth_bytes=encoded(auth)
        self.fence()
        runtime.atomic_json(directory/'authority.json',auth,exclusive=True)
        runtime.atomic_json(directory/'native-audit.json',audit_proof,exclusive=True)
        return copy.deepcopy(self.audit_inputs_reference)

    def fence(self):
        self.current_sources()
        require(self.auth is not None and encoded(self.auth)==self.auth_bytes,'Original terminal authority changed')
        for ref in self.auth['control_pins'].values():runtime.question_verify_reference(ref)
        parent,pin=self.startup.owner.parent()
        require(pin==self.parent_pin,'Original coordinator inode changed')
        self.latest_parent=normal.parent_extension_fence(self.parent,parent,self.latest_parent)
        require(normal.preservation.capture.native_capture(self.root_locator,self.root_pin)[0]==self.root_raw,
                'Original completed root source changed')
        state,members=runtime.declared_runtime(self.folder,self.startup.root_capability)
        require(encoded(normal.preservation.immutable_job_fields(state))==encoded(self.original_jobs)
                and encoded(members)==encoded(self.registry_state)
                and normal.preservation.registry_snapshot_fingerprint(
                    normal.preservation.membership.reservation_prefix(self.folder/'registry'))==self.registry_fingerprint,
                'Original terminal job ownership or registry changed')
        return state

    def authority(self,observation):
        self.fence()
        require(encoded(observation['configuration'])==encoded(self.registry_state['configuration'])
                and encoded(observation['registry_state'])==encoded(self.registry_state)
                and encoded(observation['dispatch_rows'])==encoded({'root':self.dispatch_row})
                and observation['coordinator_raw']==self.parent
                and observation['member_raw_by_path']=={self.row['actor_path']:self.root_raw}
                and observation['first_error'] is None,
                'Normal close must use exact original sealed source/registry in same ROOT call')
        current=observation.get('current_coordinator_raw')
        require(type(current) is bytes and current==self.latest_parent,
                'Current original ROOT parent observation differs')
        return copy.deepcopy(self.auth)

    def verify(self,purpose,proof):
        state=self.fence()
        require(type(proof) is dict,'Exact terminal callback proof required')
        if purpose=='original_normal_closer_authority':
            require(encoded(proof)==encoded({'prepared_reference':self.prepared_reference,
                'authority_contract':coordinator.callback_contract(terminal_authority),
                'audit_inputs_reference':self.audit_inputs_reference,
                'member_sources':{self.row['actor_path']:self.root_locator}}),
                'Exact original sealed normal-close inputs required')
            require(not self.close_started,'Original normal close cannot restart')
            self.close_started=True
        elif purpose=='grade_original_stopped_product':
            require(self.close_started,'Grading requires original authorized normal close')
            reference=proof['stopped_snapshot_reference']
            snapshot=runtime.strict.decoded(runtime.question_reference_bytes(reference))
            require(Path(reference['path']).parent==self.folder/'events'
                    and snapshot.get('op')=='stopped_snapshot' and snapshot.get('job')=='root'
                    and snapshot.get('scope_error') is None
                    and snapshot.get('container_id')==state['jobs']['root']['container_id']
                    and state['jobs']['root']['status']=='stopped',
                    'Original scoped same-container stopped snapshot required')
            contract,private=normal.grading.selected_contract(self.row['case_id'],None)
            require(encoded(proof)==encoded({'row':self.row,'stopped_snapshot_reference':reference,
                'qualified_receipt_contract':contract,'private_grading_requested':private,
                'delivered_owner_selection':None,'original_deadline':self.auth['original_deadline']}),
                'Exact frozen non-question private grading contract required')
            require(runtime.inspect(self.folder,state,'root')['State']['Running'] is False,
                    'Original owned product container must actually be stopped')
        else:raise ValueError('Unqualified terminal purpose: '+str(purpose))
        self.fence()


def configure(context):
    global _context
    require(_context is None and isinstance(context,TerminalController),'ROOT-only one original terminal configuration')
    context.current_sources();_context=context


def terminal_authority(observation):
    require(_context is not None,'Trusted ROOT terminal context is not configured')
    return _context.authority(observation)


def verify(purpose,proof):
    require(_context is not None,'Trusted ROOT terminal context is not configured')
    return _context.verify(purpose,proof)
