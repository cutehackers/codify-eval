"""Prospective question continuation evidence adapter. No actors are dispatched.

The injected CoordinatorGate is trusted code, not a JSON approval. It must
authenticate original source namespace/locators and independent reviewer and
assignment provenance. This module checks original bytes, UUID/call/token joins,
fixed model lifecycle and local immutable commitments. None of those checks
authenticate a dishonest gate or confer cleanup/comparison authority.
"""
import ast
import hashlib
import math
import os
from pathlib import Path
import stat
import time

import improvement_baseline_runtime_v2 as runtime
import improvement_baseline_broker_v2 as broker
import improvement_baseline_native_dispatch_v2 as dispatch
import improvement_baseline_question_branch_v1 as branch
import improvement_baseline_question_lifecycle_v3 as lifecycle
import improvement_baseline_question_routes_v2 as routes
import improvement_baseline_native_inventory_v2 as inventory
import improvement_baseline_membership_v2 as membership2
import improvement_baseline_membership_v1 as membership

core=membership.core
require=core.require
encoded=runtime.encoded
MAX_NATIVE=256*1024*1024


class CoordinatorGate:
    """Implement in coordinator. Returning True or a dictionary is forbidden.

    authorize(purpose, proof) must raise unless original locator/prefix ownership,
    externally authenticated actor/reviewer identity and purpose are authorized.
    Successful return is None. A permissive implementation is not authentication.
    """
    def authorize(self, purpose, proof):
        raise NotImplementedError('Externally authenticated coordinator gate required')


def gate_check(gate,purpose,proof):
    require(isinstance(gate,CoordinatorGate) and type(purpose) is str,
            'Trusted coordinator gate implementation required, not supplied JSON')
    require(gate.authorize(purpose,proof) is None,'Gate must authenticate or raise, never self-approved JSON')


def source_prefix(locator,gate,purpose):
    """Read complete current EOF with exact inode/frontier fence, then authenticate."""
    path=Path(locator)
    require(path.is_absolute() and path.resolve()==path and not path.is_symlink(),
            'Canonical original native locator required')
    before=path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=MAX_NATIVE,
            'Bounded single-link original source required')
    with path.open('rb') as f:
        opened=os.fstat(f.fileno());raw=f.read(MAX_NATIVE+1);after_fd=os.fstat(f.fileno())
    after=path.stat()
    def fence(s):return (s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    require(fence(before)==fence(opened)==fence(after_fd)==fence(after) and len(raw)==before.st_size
            and raw.endswith(b'\n'),'Native source drift or incomplete original frontier')
    core.parse(raw);inventory.finite(core.parse(raw))
    proof={'locator':str(path),'device':before.st_dev,'inode':before.st_ino,
           'frontier_bytes':len(raw),'mode':stat.S_IMODE(before.st_mode),
           'prefix_sha256':core.digest(raw),'mtime_ns':before.st_mtime_ns,'ctime_ns':before.st_ctime_ns}
    gate_check(gate,purpose,proof)
    require(fence(path.stat())==fence(before),'Source changed during coordinator authentication')
    return raw,proof


def extend_prefix(raw,proof,old_raw,old_proof):
    for value in (proof,old_proof):
        require(type(value) is dict and set(value)=={'locator','device','inode','frontier_bytes','mode','prefix_sha256','mtime_ns','ctime_ns'}
                and type(value['locator']) is str and Path(value['locator']).is_absolute()
                and all(type(value[k]) is int and value[k]>=0 for k in ('device','inode','frontier_bytes','mode','mtime_ns','ctime_ns'))
                and value['frontier_bytes']>0 and value['mode']<=0o7777,'Exact typed original inode/frontier proof required')
        branch.sha(value['prefix_sha256'])
    require(len(raw)==proof['frontier_bytes'] and core.digest(raw)==proof['prefix_sha256']
            and len(old_raw)==old_proof['frontier_bytes'] and core.digest(old_raw)==old_proof['prefix_sha256'],
            'Source bytes and inode/frontier proof disagree')
    require(proof['locator']==old_proof['locator'] and proof['device']==old_proof['device']
            and proof['inode']==old_proof['inode'] and proof['mode']==old_proof['mode']
            and len(raw)>=len(old_raw) and raw[:len(old_raw)]==old_raw,
            'Same original source inode and preserved first prefix required')


def after_fence(proof,gate):
    _,current=source_prefix(proof['locator'],gate,'original_source_after_fence')
    require(encoded(current)==encoded(proof),'Original native source changed during evidence validation')


def source_closure():
    paths={Path(__file__).resolve(),*(runtime.catalog.ROOT/p for p in runtime.question_source_closure())}
    queue=list(paths)
    while queue:
        path=queue.pop()
        for node in ast.walk(ast.parse(path.read_bytes())):
            names=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
            for name in names:
                local=runtime.catalog.ROOT/'tools'/(name.split('.')[0]+'.py')
                if local.is_file() and local not in paths:paths.add(local);queue.append(local)
    return {str(p.relative_to(runtime.catalog.ROOT)):runtime.question_file_entity(p) for p in sorted(paths)}


def native_binding(binding):
    require(type(binding) is dict and set(binding)==branch.BINDING_KEYS,'Exact original adapter binding required')
    return {'agent_path':binding['agent_path'],'actor_native_id':binding['root_native_uuid'],
            'parent_native_id':binding['parent_native_uuid']}


def turn_contract(raw,binding,cap,phase):
    require(type(cap) is int and cap in (0,2),'Typed original cumulative cap required')
    ids=[lifecycle.turn_id(e['payload']) for e in core.parse(raw) if e['type']=='turn_context']
    require(len(ids) in (1,2),'No third root turn permitted')
    return {'schema_version':1,'binding':native_binding(binding),'job':'root','expected_turns':len(ids),
            'turn_ids':ids,'native_sha256':core.digest(raw),'worker_cap':cap,'phase':phase}


def first_turn_prefix(raw,turn):
    lines=raw.splitlines(keepends=True)
    return b''.join(lines[:turn['complete_index']+1])


def original_ledger(folder,reference,contract,binding,reply_sha=None):
    state=runtime.load(folder);control=core.decode((Path(folder)/'broker/root/control.json').read_bytes())
    require(type(contract) is dict and set(contract)=={'job','agent_path','broker_script','run_name','capability_sha256','request_sha256','reply_sha256','spawns'},
            'Exact original root route contract required')
    require(contract['job']=='root' and contract['agent_path']==binding['agent_path']
            and contract['broker_script']==str(runtime.catalog.ROOT/'tools/improvement_baseline_broker_v2.py')
            and contract['run_name']==Path(folder).name and contract['capability_sha256']==control['capability_sha256']==state['jobs']['root']['capability_sha256']
            and contract['request_sha256']==control['request_sha256'] and contract['reply_sha256']==reply_sha,
            'Root route authority differs from original broker config or reply commitment')
    rows=sorted([row for job in sorted(state['jobs']) for row in broker.ledger(folder,job)],key=lambda r:r['action_id'])
    raw=runtime.question_reference_bytes(reference)
    require(encoded(core.decode(raw))==encoded(rows),'Supplied action ledger differs from full original broker replay')
    references={}
    for job in sorted(state['jobs']):
        directory=Path(folder)/'broker'/job
        paths=[directory/'control.json',*(p for a in sorted((directory/'actions').iterdir()) for p in (a/'intent.json',a/'receipt.json'))]
        for path in paths:references[str(path)]=runtime.question_reference(path)
    return raw,references


def reviewer_proof(raw,parent_raw,identity,review_raw,completed_after):
    require(type(identity) is dict and type(identity.get('agent_path')) is str
            and identity.get('model')=='gpt-6.1-sol' and identity.get('effort')=='medium',
            'Original fixed-model reviewer identity with explicit path required')
    path=identity['agent_path']
    # Reviewer is a distinct immediate actor of the original coordinator.
    parent=core.parse(parent_raw)[0]['payload']['id']
    events,head=membership.source(raw,path,parent)
    require(head['id']==identity['native_uuid'] and not membership.operations(events),'Reviewer UUID or actor subtree changed')
    bind={'agent_path':path,'actor_native_id':head['id'],'parent_native_id':parent}
    ids=[lifecycle.turn_id(e['payload']) for e in events if e['type']=='turn_context']
    contract={'schema_version':1,'binding':bind,'job':'root','expected_turns':1,'turn_ids':ids,
              'native_sha256':core.digest(raw),'worker_cap':0,'phase':'terminal'}
    _,turns=lifecycle.lifecycle(raw,bind,1,{},turn_contract=contract)
    require(core.decode(turns[0]['final_text'])==core.decode(review_raw),'Original reviewer final differs from semantic review')
    join=membership.native.binding(parent_raw,membership.first_request_prefix(raw,'/root'),'/root',path)
    require(join['child_native_id']==head['id'] and core.instant(events[0]['timestamp']).timestamp()>=completed_after,
            'Reviewer origin must follow original first seal')
    usage=[e for e in events if e['payload'].get('type')=='token_count']
    require(bool(usage),'Original reviewer cost source required')
    totals=usage[-1]['payload'].get('info',{}).get('total_token_usage')
    require(type(totals) is dict and 'total_tokens' in totals and bool(totals)
            and all(type(v) is int and v>=0 for v in totals.values()),'Typed original reviewer cumulative tokens required')
    return {'native_uuid':head['id'],'spawn_call_id':join['spawn_call_id'],'native_sha256':core.digest(raw),
            'completed_at':turns[0]['completed_at'],'total_token_usage':totals,'cost_source_event_sha256':core.digest(encoded(usage[-1]))}


def followup_join(parent_raw,root_raw,binding,turns,intent,staged_at):
    membership.source(parent_raw,'/root')
    require(core.parse(parent_raw)[0]['payload']['id']==binding['parent_native_uuid'],'Original parent UUID changed')
    calls=[];outputs={};seen=set()
    for i,e in enumerate(core.parse(parent_raw)):
        p=e['payload'];kind=p.get('type');cid=p.get('call_id')
        if kind in ('function_call','custom_tool_call'):
            require(type(cid) is str and cid and cid not in seen,'Duplicate parent call');seen.add(cid)
            if core.route(p,'collaboration','followup_task'):
                args=core.decode(p['arguments'])
                if args.get('target') in (binding['agent_path'],binding['agent_path'].rsplit('/',1)[-1]):calls.append((i,e,args))
            elif any(core.route(p,'collaboration',n) for n in ('send_message','interrupt_agent')):
                args=core.decode(p['arguments']);require(args.get('target') not in (binding['agent_path'],binding['agent_path'].rsplit('/',1)[-1]),'Unapproved product parent delivery')
        elif kind in ('function_call_output','custom_tool_call_output'):
            require(cid in seen and cid not in outputs,'Orphan or duplicate parent output');outputs[cid]=(i,e)
    require(len(calls)==1,'Exactly one original same-actor followup required, no uncertain retransmission')
    i,call,args=calls[0];receipt=outputs.get(call['payload']['call_id'])
    require(set(args)=={'target','message'} and receipt is not None and receipt[0]>i
            and receipt[1]['payload']['type']=='function_call_output' and receipt[1]['payload']['output']=='',
            'Successful original followup receipt required')
    incoming=core.parse(root_raw)[turns[1]['incoming_index']]
    token,readable=core.delivery_token(incoming['payload'])
    require(args['message']==token and (not readable or token==intent['message']), 'Parent token differs from second incoming request')
    at=core.instant(call['timestamp']).timestamp();received=core.instant(receipt[1]['timestamp']).timestamp()
    require(staged_at<=intent['at']<=at<=received and at<=core.instant(incoming['timestamp']).timestamp()
            and received<intent['original_deadline'],'Original delivery chronology changed')
    return {'call_id':call['payload']['call_id'],'token_sha256':core.digest(token.encode()),
            'plaintext_verified':readable,'ciphertext_decrypted':False,'parent_sha256':core.digest(parent_raw)}


class Adapter:
    def __init__(self,folder,root_capability,coordinator_capability,gate):
        self.folder=Path(folder).resolve();self.root_cap=root_capability;self.coord_cap=coordinator_capability;self.gate=gate

    def current(self,purpose):
        state,control,history=runtime.question_coordinator_auth(self.folder,self.coord_cap)
        gate_check(self.gate,purpose,{'binding':control['binding'],'question_control':runtime.question_reference(self.folder/'question/configuration.json'),
                                    'source_entities':source_closure(),'original_deadline':control['original_deadline']})
        directory=self.folder/'question/adapter'
        if directory.exists():
            origin=core.decode((directory/'commitment-origin.json').read_bytes())
            require(type(origin) is dict and set(origin)=={'entity'} and
                    encoded(runtime.question_file_entity(directory/'commitment.json'))==encoded(origin['entity']),
                    'Original adapter commitment changed')
            commitment=core.decode((directory/'commitment.json').read_bytes())
            require(type(commitment) is dict and set(commitment)=={'schema_version','source_entities','references','native_proofs','first_contract',
                    'root_origin','allocation_proof','all_cost_member_uuids','external_authentication_required'}
                    and type(commitment['schema_version']) is int and commitment['schema_version']==1
                    and commitment['external_authentication_required'] is True,'Exact typed adapter commitment required')
            require(encoded(commitment['source_entities'])==encoded(source_closure()),'Frozen adapter source closure drift')
            for ref in commitment['references'].values():runtime.question_verify_reference(ref)
            for name in ('reviewer','followup'):
                originpath=directory/(name+'-origin.json')
                if originpath.exists():runtime.question_verify_reference(core.decode(originpath.read_bytes())['reference'])
            if (directory/'reviewer-origin.json').exists():
                reviewproof=core.decode(runtime.question_reference_bytes(core.decode((directory/'reviewer-origin.json').read_bytes())['reference']))
                runtime.question_verify_reference(reviewproof['source'])
                require(reviewproof['source']['entity']['sha256']==reviewproof['native_proof']['prefix_sha256']==reviewproof['cost']['native_sha256'],
                        'Original reviewer cost/source join changed')
        runtime.question_coordinator_auth(self.folder,self.coord_cap)
        return state,control,history

    def save(self,name,value):
        path=self.folder/'question/adapter'/name
        runtime.atomic_json(path,value,exclusive=True)
        return runtime.question_reference(path)

    def snapshot(self,name,raw):
        path=self.folder/'question/adapter'/name
        with path.open('xb') as f:f.write(raw)
        path.chmod(0o444)
        return runtime.question_reference(path)

    def seal_first(self,*,parent_locator,root_locator,child_locators,action_ledger_reference,root_route_contract,membership_reference):
        state,control,history=self.current('first_seal')
        require(not history and type(child_locators) is dict,'Original first phase required')
        binding=control['binding'];root,rootproof=source_prefix(root_locator,self.gate,'original_root_prefix')
        parent,parentproof=source_prefix(parent_locator,self.gate,'original_parent_prefix')
        children={};proofs={}
        for path,locator in child_locators.items():children[path],proofs[path]=source_prefix(locator,self.gate,'original_worker_terminal')
        contract=turn_contract(root,binding,state['worker_cap'],'first_seal')
        require(contract['expected_turns']==1,'First seal cannot contain second turn')
        _,turns=lifecycle.lifecycle(root,native_binding(binding),1,children,turn_contract=contract)
        join=membership.native.binding(parent,membership.first_request_prefix(root,'/root'),'/root',binding['agent_path'])
        require(join['child_native_id']==binding['root_native_uuid'],'Original root spawn UUID differs')
        ledger,original_actions=original_ledger(self.folder,action_ledger_reference,root_route_contract,binding)
        routes.audit_member(root,native_binding(binding),root_route_contract,ledger,
                            {'turn_ids':contract['turn_ids'],'native_sha256':core.digest(root),'approved':True},children,lifecycle_contract=contract)
        reservation=membership2.reservation_prefix(self.folder/'registry')
        allocation=core.decode(runtime.question_reference_bytes(membership_reference))
        require(type(allocation) is dict and set(allocation)=={'root_intent','worker_intents','provision_ledger'},'Original allocation inputs required')
        allocationproof=membership2.reconcile_membership(reservation['state']['configuration'],reservation['state'],
            allocation['root_intent'],allocation['worker_intents'],parent,root,children,allocation['provision_ledger'],self.folder/'registry')
        require(allocationproof['provided_allocation_joins_complete'] is True and not allocationproof['observed_unbound_sources'],
                'Every actual original allocation must be joined, pending is not completion')
        expected={binding['agent_path']+'/'+slot for slot in reservation['state']['workers']}
        require(set(children)==expected and len(children)<=state['worker_cap'],'Cumulative registered original worker coverage changed')
        completed=core.instant(turns[0]['completed_at']).timestamp();sealed=time.time()
        require(control['original_started_at']<=completed<=sealed<control['original_deadline'],'First native completion outside original clock')
        for proof in [rootproof,parentproof,*proofs.values()]:after_fence(proof,self.gate)
        directory=self.folder/'question/adapter';directory.mkdir()
        refs={'root':self.snapshot('first-root-paused.jsonl',root),'first_turn':self.snapshot('first-turn-prefix.jsonl',first_turn_prefix(root,turns[0])),
              'parent':self.snapshot('first-parent.jsonl',parent),'action_ledger':action_ledger_reference,'membership':membership_reference,
              'registry_events':self.snapshot('first-registry-events.jsonl',reservation['full_events_raw'] or b'\n')}
        for n,(path,raw) in enumerate(sorted(children.items())):refs[path]=self.snapshot(f'first-worker-{n}.jsonl',raw)
        refs.update(original_actions)
        refs['registry_configuration']=runtime.question_reference(self.folder/'registry/configuration.json')
        refs['registry_origin']=runtime.question_reference(self.folder/'registry/configuration-origin.json')
        for n,pin in enumerate(reservation['event_pins']):
            eventpath=self.folder/'registry/events'/f'{n:06d}.json'
            # Registry naming is obtained from the already replayed actual paths.
            eventpath=sorted((self.folder/'registry/events').iterdir())[n]
            refs['registry_event_'+str(n)]=runtime.question_reference(eventpath)
        evidence={ref['path']:ref['entity'] for ref in refs.values()}
        members={'root':binding['root_native_uuid'],**{path.rsplit('/',1)[-1]:core.parse(raw)[0]['payload']['id'] for path,raw in children.items()}}
        seal={'schema_version':1,'binding':binding,'original_started_at':control['original_started_at'],'original_deadline':control['original_deadline'],
              'first_completed_at':completed,'sealed_at':sealed,'first_turn_id':turns[0]['turn_id'],'member_native_uuids':members,'evidence_entities':evidence}
        sealref=self.save('first-seal.json',seal);refs['seal']=sealref
        commitment_ref=self.save('commitment.json',{'schema_version':1,'source_entities':source_closure(),'references':refs,
            'native_proofs':{'root':rootproof,'parent':parentproof,'children':proofs},'first_contract':contract,
            'root_origin':join,'allocation_proof':allocationproof,'all_cost_member_uuids':list(members.values()),'external_authentication_required':True})
        self.save('commitment-origin.json',{'entity':commitment_ref['entity']})
        gate_check(self.gate,'authenticated_quiescent_first_seal',{'seal':sealref,'native_proofs':{'root':rootproof,'parent':parentproof,'children':proofs},'registry':reservation})
        runtime.pause_for_question(self.folder,self.coord_cap,sealref)
        return sealref

    def authorize(self,*,review_reference,reviewer_identity,reviewer_locator,parent_locator,assignment_reference,policy_sha256):
        state,control,history=self.current('semantic_review')
        require(len(history)==1,'Exactly original paused first phase required')
        raw,proof=source_prefix(reviewer_locator,self.gate,'independent_reviewer_source')
        parent,parentproof=source_prefix(parent_locator,self.gate,'reviewer_parent_source')
        require(reviewer_identity.get('native_uuid') not in [control['binding']['root_native_uuid'],control['binding']['parent_native_uuid']]
                and reviewer_identity.get('agent_path')!=control['binding']['agent_path'],'Reviewer is not original product or coordinator')
        commitment=core.decode((self.folder/'question/adapter/commitment.json').read_bytes())
        extend_prefix(parent,parentproof,runtime.question_reference_bytes(commitment['references']['parent']),commitment['native_proofs']['parent'])
        require(reviewer_identity.get('native_uuid') not in commitment['all_cost_member_uuids'],'Product worker cannot review its parent')
        seal=core.decode(runtime.question_reference_bytes(commitment['references']['seal']))
        review=runtime.question_reference_bytes(review_reference)
        cost=reviewer_proof(raw,parent,reviewer_identity,review,seal['sealed_at'])
        require(core.instant(cost['completed_at']).timestamp()<control['original_deadline'],'Reviewer exceeded original whole clock')
        gate_check(self.gate,'independent_semantic_review_and_preallocated_assignment',{'review':review_reference,'reviewer':proof,'parent':parentproof,
            'identity':reviewer_identity,'cost':cost,'assignment':assignment_reference,'policy_sha256':policy_sha256})
        after_fence(proof,self.gate);after_fence(parentproof,self.gate)
        reviewerref=self.save('reviewer-proof.json',{'source':self.snapshot('reviewer.jsonl',raw),'native_proof':proof,'parent_proof':parentproof,'cost':cost})
        self.save('reviewer-origin.json',{'reference':reviewerref})
        result=runtime.commit_question_authority(self.folder,self.coord_cap,semantic_review_reference=review_reference,
            private_assignment_reference=assignment_reference,reviewer_identity=reviewer_identity,policy_sha256=policy_sha256)
        return result

    def stage(self,reply_provider):
        state,control,history=self.current('stage_reply')
        require(len(history)==2,'Original semantic authority required')
        authority=core.decode(runtime.question_reference_bytes(history[-1]['payload']['references']['authority']))
        if authority['reply_kind']=='none':return {'expected_root_turns':1,'followup':False}
        if authority['reply_kind']=='neutral':raw=branch.NEUTRAL
        else:
            require(callable(reply_provider),'Opaque out-of-band registered reply provider required')
            gate_check(self.gate,'registered_preallocated_reply_provider',{'assignment':history[-1]['payload']['references']['private_assignment'],
                       'expected_reply_sha256':authority['reply_sha256_or_null']})
            raw=reply_provider(history[-1]['payload']['references']['private_assignment'],authority['reply_sha256_or_null'])
        require(type(raw) is bytes and core.digest(raw)==authority['reply_sha256_or_null'],'Provider reply differs from preallocated authorization')
        return runtime.stage_question_reply(self.folder,self.coord_cap,raw)

    def prepare_followup(self):
        state,control,history=self.current('prepare_same_actor_followup')
        require(len(history)==3,'Original staged reply required')
        path=self.folder/'question/adapter/followup-intent.json'
        require(not path.exists(),'Uncertain original followup cannot be retransmitted')
        runtime.resume_for_reply(self.folder,self.coord_cap)
        message=dispatch.followup_bootstrap(self.folder,self.root_cap,self.coord_cap)
        result=self.save('followup-intent.json',{'schema_version':1,'binding':control['binding'],'message':message,'at':time.time(),
                    'original_deadline':control['original_deadline'],'transport_dispatched':False})
        self.save('followup-origin.json',{'reference':result})
        return result

    def terminal(self,*,parent_locator,root_locator,child_locators,action_ledger_reference,root_route_contract,membership_reference):
        state,control,history=self.current('terminal_continuation_join')
        require(len(history) in (2,5),'No uncertain delivery or incomplete reply read can qualify')
        authority=core.decode(runtime.question_reference_bytes(history[1]['payload']['references']['authority']))
        expected=authority['expected_root_turns']
        require((expected==1 and len(history)==2) or (expected==2 and len(history)==5),'Authority/actual reply receipt mismatch')
        root,rproof=source_prefix(root_locator,self.gate,'terminal_original_root')
        parent,pproof=source_prefix(parent_locator,self.gate,'terminal_original_parent')
        commitment=core.decode((self.folder/'question/adapter/commitment.json').read_bytes())
        first=runtime.question_reference_bytes(commitment['references']['root'])
        firstparent=runtime.question_reference_bytes(commitment['references']['parent'])
        extend_prefix(root,rproof,first,commitment['native_proofs']['root']);extend_prefix(parent,pproof,firstparent,commitment['native_proofs']['parent'])
        children={};proofs={}
        for path,loc in child_locators.items():children[path],proofs[path]=source_prefix(loc,self.gate,'terminal_original_worker')
        require(set(commitment['native_proofs']['children'])<=set(children),'Previously allocated cost member omitted')
        for path,old in commitment['native_proofs']['children'].items():
            extend_prefix(children[path],proofs[path],runtime.question_reference_bytes(commitment['references'][path]),old)
        contract=turn_contract(root,control['binding'],state['worker_cap'],'terminal')
        require(contract['expected_turns']==expected,'Third or unapproved root turn')
        _,turns=lifecycle.lifecycle(root,native_binding(control['binding']),expected,children,turn_contract=contract)
        require(turns[0]['turn_id']==commitment['first_contract']['turn_ids'][0],'First original turn changed')
        delivery=None
        if expected==2:
            intentref=core.decode((self.folder/'question/adapter/followup-origin.json').read_bytes())['reference']
            intent=core.decode(runtime.question_reference_bytes(intentref))
            delivery=followup_join(parent,root,control['binding'],turns,intent,history[2]['at'])
        ledger,_=original_ledger(self.folder,action_ledger_reference,root_route_contract,control['binding'],authority['reply_sha256_or_null'])
        observed=routes.audit_member(root,native_binding(control['binding']),root_route_contract,ledger,
            {'turn_ids':contract['turn_ids'],'native_sha256':core.digest(root),'approved':True},children,lifecycle_contract=contract)
        if expected==2:
            receipt=core.decode(runtime.question_reference_bytes(history[-1]['payload']['references']['broker_receipt']))
            claim=core.decode(runtime.question_reference_bytes(history[-1]['payload']['references']['claim']))
            intentref=claim['broker_intent'];originalintent=core.decode(runtime.question_reference_bytes(intentref))
            entries=core.decode(ledger)
            require(any(encoded(e)==encoded({**originalintent,'status':receipt['status'],'result':receipt.get('result')}) for e in entries)
                    and receipt['status']=='completed' and originalintent['request']=={'job':'root','op':'read_reply','data':{}},
                    'Actual full reply read receipt absent from original action ledger')
        reservation=membership2.reservation_prefix(self.folder/'registry')
        allocation=core.decode(runtime.question_reference_bytes(membership_reference))
        require(type(allocation) is dict and set(allocation)=={'root_intent','worker_intents','provision_ledger'},'Original cumulative allocation inputs required')
        oldallocation=core.decode(runtime.question_reference_bytes(commitment['references']['membership']))
        require(encoded(allocation['root_intent'])==encoded(oldallocation['root_intent'])
                and all(encoded(allocation['worker_intents'].get(k))==encoded(v) for k,v in oldallocation['worker_intents'].items()),
                'Original dispatch intents cannot be reset')
        allocationproof=membership2.reconcile_membership(reservation['state']['configuration'],reservation['state'],
            allocation['root_intent'],allocation['worker_intents'],parent,root,children,allocation['provision_ledger'],self.folder/'registry')
        require(allocationproof['provided_allocation_joins_complete'] is True and not allocationproof['observed_unbound_sources'],
                'Every cumulative allocation needs original outcome evidence')
        require(set(children)=={control['binding']['agent_path']+'/'+s for s in reservation['state']['workers']},'Terminal full cumulative membership mismatch')
        require(core.instant(turns[-1]['completed_at']).timestamp()<control['original_deadline'],'Original deadline exceeded')
        self.current('terminal_source_after_fence')
        gate_check(self.gate,'original_same_uuid_terminal_evidence',{'root':rproof,'parent':pproof,'children':proofs,
                    'contract':contract,'delivery':delivery,'route_observation':observed,'registry':reservation,
                    'original_followup_intent':None if expected==1 else intentref})
        for proof in [rproof,pproof,*proofs.values()]:after_fence(proof,self.gate)
        return {'status':'observed_question_contract','turn_contract':contract,'delivery':delivery,'routes':observed,
                'terminal_inventory_integration_pending':True,
                'cumulative_product_native_uuids':[control['binding']['root_native_uuid']]+[core.parse(x)[0]['payload']['id'] for x in children.values()],
                'reviewer_cost_retained':True,'external_authentication_required':True,'native_qualified':False,
                'cleanup_authorized':False,'comparison':False,'checkpoint6':False,'superiority':False}
