"""Prospective trusted ROOT gate for question-cap0 original launch only.

Caller trust comes from the original ROOT environment, not these JSON joins.
No first seal, semantic review, reply, followup or terminal purpose is supported.
"""
import copy
import os
from pathlib import Path
import stat
import time

import improvement_baseline_question_coordinator_v12 as coordinator
import improvement_baseline_root_source_v4 as source

runtime=coordinator.runtime
require=runtime.require
encoded=runtime.encoded
PROOF_KEYS={'locator','device','inode','frontier_bytes','mode','prefix_sha256','mtime_ns','ctime_ns'}
SOURCE_PURPOSES={'original_parent_launch_prefix','original_root_launch_prefix','original_source_after_fence'}


def validate_source_proof(proof,raw,observed):
    require(type(proof) is dict and set(proof)==PROOF_KEYS and type(raw) is bytes
            and raw.endswith(b'\n') and type(observed) is dict and set(observed)==PROOF_KEYS,
            'Exact complete original source/proof required')
    require(type(proof['locator']) is str and Path(proof['locator']).is_absolute()
            and all(type(proof[k]) is int and proof[k]>=0 for k in
                    ('device','inode','frontier_bytes','mode','mtime_ns','ctime_ns'))
            and proof['frontier_bytes']>0 and proof['mode']<=0o7777,
            'Typed original inode/frontier fields required')
    require(encoded(proof)==encoded(observed) and len(raw)==proof['frontier_bytes']
            and coordinator.adapter.core.digest(raw)==proof['prefix_sha256'],
            'Actual source inode/frontier/hash differs from supplied proof')


class LaunchGate(coordinator.adapter.CoordinatorGate):
    def __init__(self,*,owner,row,root_capability,prepared_reference,launch_reference,frozen_sources):
        require(isinstance(owner,source.RootSource),'Externally trusted original ROOT source required')
        coordinator.inputs.row_valid(row)
        require(row['case_id'] in ('B03','B04') and type(row['worker_cap']) is int
                and row['worker_cap']==0,'Registered question cap0 launch only')
        self.owner=owner;self.row=copy.deepcopy(row);self.root_capability=root_capability
        self.prepared_reference=copy.deepcopy(prepared_reference)
        self.launch_reference=copy.deepcopy(launch_reference);self.graph=copy.deepcopy(frozen_sources)
        self.folder=coordinator.ROOT/'runtime'/row['run_id']
        self.commitment=self.context()

    def context(self):
        return encoded({'row':self.row,'root_capability_sha256':runtime.hashed(self.root_capability),
            'prepared':self.prepared_reference,'launch':self.launch_reference,'sources':self.graph,
            'parent_anchor':self.owner.value,'folder':str(self.folder)})

    def frontier(self):
        require(self.context()==self.commitment,'Original launch gate context changed')
        coordinator.source_fence(self.graph,[runtime.question_reference(Path(__file__).resolve())])
        self.owner.parent()
        prepared=runtime.strict.decoded(runtime.question_reference_bytes(self.prepared_reference))
        launch=runtime.strict.decoded(runtime.question_reference_bytes(self.launch_reference))
        require(self.prepared_reference['path']==str(self.folder/'coordinator/prepared.json')
                and self.launch_reference['path']==str(self.folder/'coordinator/launch-intent.json')
                and encoded(prepared['row'])==encoded(self.row)
                and encoded(launch['prepared_reference'])==encoded(self.prepared_reference)
                and launch['status']=='dispatch_once_or_preserve_uncertain_ack'
                and launch['actual_native_authenticated'] is False,
                'Original frozen prepared row and one-shot launch intent required')
        state,members=runtime.declared_runtime(self.folder,self.root_capability)
        require(runtime.question_validate(self.folder) is None and state['phase']=='running'
                and set(state['jobs'])=={'root'} and state['jobs']['root']['status']=='running'
                and not members['workers'] and not members['active_leases']
                and encoded(state['started_at'])==encoded(prepared['original_started_at'])
                and encoded(state['deadline'])==encoded(prepared['original_deadline'])
                and time.time()<state['deadline'], 'Original unbound root-only question frontier required')
        dispatch,_=coordinator.root_dispatch_inputs(self.folder,self.row,self.root_capability,
            self.owner.value['parent_native_id'],members['configuration'],coordinator.inputs.public_task(self.row))
        expected={'task_name':self.row['actor_path'].removeprefix('/root/'),
                  'message':dispatch['native_bootstrap'],'fork_turns':'none',
                  'model':'gpt-6.1-sol','reasoning_effort':'medium'}
        require(encoded(launch['arguments'])==encoded(expected),'Original canonical launch arguments changed')
        return state,members,launch

    def original_source(self,proof,kind):
        require(type(proof) is dict and set(proof)==PROOF_KEYS,'Exact native source proof required')
        locator=Path(proof['locator'])
        require(locator.is_absolute() and locator.resolve(strict=True)==locator and not locator.is_symlink(),
                'Canonical original native source locator required')
        before=locator.stat()
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1,'Single-link original native source required')
        if kind=='parent':
            require(locator==self.owner.source,'Only actual original ROOT source permitted')
            raw,_=self.owner.parent()
        else:
            require(locator!=self.owner.source,'Original product and parent must differ')
            origin=self.owner.root_origin(locator,self.row['actor_path'])
            raw,_=source.capture.native_capture(locator,origin['child_entity'])
        observed={'locator':str(locator),'device':before.st_dev,'inode':before.st_ino,
            'frontier_bytes':before.st_size,'mode':stat.S_IMODE(before.st_mode),
            'prefix_sha256':coordinator.adapter.core.digest(raw),
            'mtime_ns':before.st_mtime_ns,'ctime_ns':before.st_ctime_ns}
        validate_source_proof(proof,raw,observed)
        after=locator.stat()
        require((before.st_dev,before.st_ino,before.st_mode,before.st_nlink,before.st_size,before.st_mtime_ns,before.st_ctime_ns)
                ==(after.st_dev,after.st_ino,after.st_mode,after.st_nlink,after.st_size,after.st_mtime_ns,after.st_ctime_ns),
                'Original source changed during authentication')
        return raw

    def authorize(self,purpose,proof):
        require(type(purpose) is str and type(proof) is dict,'Typed launch authentication request required')
        require(purpose in SOURCE_PURPOSES or purpose=='bind_original_question_root',
                'Unqualified question launch purpose: '+str(purpose))
        before=self.frontier()
        if purpose in SOURCE_PURPOSES:
            kind='parent' if purpose=='original_parent_launch_prefix' else 'root'
            if purpose=='original_source_after_fence':
                kind='parent' if proof.get('locator')==str(self.owner.source) else 'root'
            self.original_source(proof,kind)
        else:
            require(set(proof)=={'launch_intent_reference','binding','native_join','parent_proof','root_proof'}
                    and encoded(proof['launch_intent_reference'])==encoded(self.launch_reference),
                    'Exact original bind proof required')
            parent=self.original_source(proof['parent_proof'],'parent')
            child=self.original_source(proof['root_proof'],'root')
            join=coordinator.adapter.membership.native.binding(parent,child,'/root',self.row['actor_path'])
            binding={'run_id':self.row['run_id'],'case_id':self.row['case_id'],
                     'root_native_uuid':join['child_native_id'],'parent_native_uuid':join['parent_native_id'],
                     'agent_path':self.row['actor_path']}
            require(encoded(binding)==encoded(proof['binding']) and encoded(join)==encoded(proof['native_join'])
                    and binding['parent_native_uuid']==self.owner.value['parent_native_id'],
                    'Original native launch join/binding changed')
            calls=[args for cid,event,args,receipt in coordinator.adapter.membership.operations(
                coordinator.adapter.core.parse(parent)) if cid==join['spawn_call_id']]
            require(len(calls)==1 and encoded(calls[0])==encoded(before[2]['arguments']),
                    'Actual original spawn differs from frozen canonical arguments')
            coordinator.active_first_request(child,self.row['run_id'],self.root_capability)
        require(encoded(self.frontier())==encoded(before),'Original launch frontier changed during authentication')
