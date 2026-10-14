"""Trusted coordinator startup bridge, without final admission or delivery.

ROOT alone configures this process from its trusted environment. Source joins
cannot establish caller trust. Unknown purposes and second turns are denied.
This initial bridge does not authorize semantic reviews, replies or cleanup.
"""
import copy
from pathlib import Path
import re
import time

import improvement_baseline_question_coordinator_v8 as coordinator
import improvement_baseline_root_source_v3 as source
import improvement_baseline_native_watch_v3 as watch

runtime=coordinator.runtime
require=runtime.require
encoded=runtime.encoded
ROOT=coordinator.ROOT
_context=None


class StartupController:
    def __init__(self,row,owner,root_capability,source_entities,skill_inventory,assignment_reference):
        coordinator.inputs.row_valid(row)
        require(type(root_capability) is str and re.fullmatch('[0-9a-f]{48}',root_capability),
                'Private original ROOT capability required')
        self.row=copy.deepcopy(row);self.owner=owner;self.root_capability=root_capability
        self.graph=copy.deepcopy(source_entities);self.skill=copy.deepcopy(skill_inventory)
        self.assignment=copy.deepcopy(assignment_reference)
        self.folder=ROOT/'runtime'/row['run_id']
        self.original_clock=None
        self.configuration_reference=None
        self.context_commitment=self.context_bytes()

    def context_bytes(self):
        return encoded({'row':self.row,'root_capability':self.root_capability,
                        'source_entities':self.graph,'skill_inventory':self.skill,
                        'assignment_reference':self.assignment,'owner_anchor':self.owner.value,
                        'folder':str(self.folder)})

    def current(self):
        require(self.context_bytes()==self.context_commitment,'Original startup context changed')
        self.owner.parent()
        reference=runtime.question_reference(Path(__file__).resolve())
        coordinator.source_fence(self.graph,[reference])

    def prepared(self):
        self.current()
        state,members=runtime.declared_runtime(self.folder,self.root_capability)
        runtime.question_validate(self.folder)
        require(state['phase']=='running' and state['jobs']['root']['status']=='running'
                and not members['workers'] and set(state['jobs'])=={'root'},
                'Startup requires running original root and no workers')
        config=runtime.strict.decoded((self.folder/'configuration.json').read_bytes())
        reference=runtime.question_reference(self.folder/'configuration.json')
        if self.configuration_reference is None:self.configuration_reference=reference
        require(encoded(reference)==encoded(self.configuration_reference),'Original runtime configuration changed')
        require(config['case']==self.row['case_id'] and config['condition']==self.row['condition']
                and type(config['worker_cap']) is int and config['worker_cap']==self.row['worker_cap']
                and config['task']==coordinator.inputs.public_task(self.row), 'Original registered startup task required')
        clock=(state['started_at'],state['deadline'])
        require(time.time()<clock[1], 'Original startup deadline exhausted')
        if self.original_clock is None:self.original_clock=clock
        require(encoded(clock)==encoded(self.original_clock),'Original startup clock changed')
        return state,members

    def verify(self,purpose,proof):
        self.current()
        require(type(proof) is dict,'Exact startup proof required')
        if purpose=='pre_sdk_freeze':
            require(not self.folder.exists(),'Freeze must precede all SDK allocation')
            require(encoded(proof['row'])==encoded(self.row)
                    and encoded(proof['source_entities'])==encoded(self.graph)
                    and encoded(proof['frozen_skill_inventory'])==encoded(self.skill)
                    and encoded(proof['opaque_assignment_reference'])==encoded(self.assignment)
                    and proof['task']==coordinator.inputs.public_task(self.row),
                    'Original frozen row/graph/skill/assignment/task required')
        elif purpose=='adopt_prepared_runtime':
            state,_=self.prepared()
            require(encoded(proof['row'])==encoded(self.row) and encoded(proof['state'])==encoded(state),
                    'Original actual prepared runtime required')
        elif purpose=='original_observer_ready':
            state,_=self.prepared();ready=proof['ready']
            require(proof['observer_ready_reference']['path']==str(self.folder/'native-observer/ready.json')
                    and encoded(runtime.strict.decoded(runtime.question_reference_bytes(proof['observer_ready_reference'])))==encoded(ready)
                    and ready['root_path']==self.row['actor_path']
                    and ready['parent_id']==self.owner.value['parent_native_id']
                    and ready['actor_control'] is False and type(ready['observer_restarts']) is int
                    and ready['observer_restarts']==0
                    and ready['root_native_id'] is None
                    and encoded(ready['original_started_at'])==encoded(state['started_at'])
                    and encoded(ready['deadline'])==encoded(state['deadline']),
                    'Original pre-birth observer ready required')
        elif purpose=='one_original_root_launch':
            _,members=self.prepared()
            dispatch,_=coordinator.root_dispatch_inputs(self.folder,self.row,self.root_capability,
                self.owner.value['parent_native_id'],members['configuration'],coordinator.inputs.public_task(self.row))
            expected={'task_name':self.row['actor_path'].removeprefix('/root/'),
                      'message':dispatch['native_bootstrap'],'fork_turns':'none',
                      'model':'gpt-6.1-sol','reasoning_effort':'medium'}
            require(encoded(proof['arguments'])==encoded(expected),'Exact original native launch required')
            parent,_=self.owner.parent()
            for event in source.membership.original.core.parse(parent):
                p=event['payload']
                if p.get('type')=='function_call' and source.membership.original.core.route(p,'collaboration','spawn_agent'):
                    args=source.membership.original.core.decode(p['arguments'])
                    require(args.get('task_name')!=expected['task_name'], 'Original actor already dispatched; uncertain ACK cannot retry')
        else:
            raise ValueError('Unqualified coordinator purpose: '+str(purpose))
        self.current()

    def observer(self,observation):
        prepared,_=self.prepared()
        require(observation['root_path']==self.row['actor_path']
                and observation['parent_id']==self.owner.value['parent_native_id'], 'Original observer identity required')
        config=observation['configuration']
        state=runtime.registry.read(self.folder/'registry')
        require(encoded(state)==encoded(observation['registry_state'])
                and encoded(state['configuration'])==encoded(config)
                and config['case_id']==self.row['case_id'] and config['condition']==self.row['condition']
                and type(config['worker_cap']) is int and config['worker_cap']==self.row['worker_cap']
                and encoded(config['started_at'])==encoded(prepared['started_at'])
                and encoded(config['deadline'])==encoded(prepared['deadline']),
                'Original observer registry/configuration required')
        require(not state['workers'],'Initial startup observer cannot approve worker allocation')
        require(type(observation['raw_sources']) is dict
                and set(observation['raw_sources'])<={self.row['actor_path']},
                'Startup observer cannot approve unregistered sources')
        value={'schema_version':1,'root_path':self.row['actor_path'],
               'parent_id':self.owner.value['parent_native_id'],'root_native_id':None,
               'worker_cap':self.row['worker_cap'],'expected_turns':1,'turn_ids':[],
               'phase':'awaiting_semantic_review','original_started_at':config['started_at'],
               'original_deadline':config['deadline'],
               'control_pins':{'runtime_configuration':runtime.question_reference(self.folder/'configuration.json')}}
        raw=observation['raw_sources'].get(self.row['actor_path'])
        if raw is None:return value
        require(type(raw) is bytes,'Original observer source bytes required')
        if not raw.endswith(b'\n'):return value
        events=source.membership.original.core.parse(raw)
        contexts=[e for e in events if e['type']=='turn_context']
        require(len(contexts)<=1,'Startup cannot approve a second root turn')
        incoming=[e for e in events if e['payload'].get('type')=='agent_message' and e['payload'].get('author')=='/root']
        if not contexts or not incoming:return value
        path=watch.find_session(self.row['actor_path'])
        try:origin=self.owner.root_origin(path,self.row['actor_path'])
        except ValueError as error:
            if str(error)=='Observed spawn has no success receipt yet':return value
            raise
        require(watch.native_capture(path,origin['child_entity'])[0].startswith(raw),
                'Observer source is not an original native prefix')
        value['root_native_id']=origin['native_join']['child_native_id']
        require(observation['observed_root_native_id'] in (None,value['root_native_id']),
                'Observed original root UUID changed')
        value['turn_ids']=[coordinator.adapter.lifecycle.turn_id(contexts[0]['payload'])]
        watch.authority_snapshot(value,self.row['actor_path'],self.owner.value['parent_native_id'],config)
        return value


def configure(controller):
    global _context
    require(_context is None and isinstance(controller,StartupController),'ROOT-only single configuration per process')
    controller.current();_context=controller


def verify(purpose,proof):
    require(_context is not None,'Trusted ROOT controller is not configured')
    _context.verify(purpose,proof)


def observer_authority(observation):
    require(_context is not None,'Trusted ROOT controller is not configured')
    return _context.observer(observation)
