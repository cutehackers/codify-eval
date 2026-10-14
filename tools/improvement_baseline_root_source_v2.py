"""Original ROOT session anchor and genuine parent/child source joins.

The trusted ROOT identity must come from the calling coordinator environment.
This module cannot establish that caller trust or authorize allocation, replies,
cleanup or comparison. Evaluated agents must never receive the retained prefix.
"""
import hashlib
from pathlib import Path
import re

import improvement_baseline_native_watch_v3 as capture
import improvement_baseline_membership_v2 as membership
import improvement_baseline_runtime_v4 as runtime

ROOT=runtime.catalog.ROOT
SESSIONS=Path('/Users/junhyounglee/.codex/sessions')
require=runtime.require
encoded=runtime.encoded


def session_locator(path,native_id):
    path=Path(path)
    require(type(native_id) is str and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',native_id),
            'Externally known exact native UUID required')
    require(path.is_absolute() and path.resolve(strict=True)==path and not path.is_symlink()
            and path.is_relative_to(SESSIONS) and path.name.endswith('-'+native_id+'.jsonl'),
            'Original native session locator required')
    return path


def parent_header(raw,native_id):
    events=membership.original.core.parse(raw)
    membership.original.inventory.finite(events)
    headers=[e for e in events if e['type']=='session_meta']
    require(len(headers)==1 and events[0]==headers[0], 'Original single ROOT header required')
    header=headers[0]['payload']
    require(header.get('id')==native_id and header.get('agent_path') in (None,'/root')
            and not header.get('parent_thread_id'), 'Original externally trusted ROOT identity required')
    return header


def freeze_parent(source,directory,*,trusted_root_native_id,current_call_nonce):
    source=session_locator(source,trusted_root_native_id)
    raw,entity=capture.native_capture(source)
    header=parent_header(raw,trusted_root_native_id)
    require(type(current_call_nonce) is str and len(current_call_nonce)>=32, 'Fresh ROOT call nonce required')
    calls=[e for e in membership.original.core.parse(raw) if e['payload'].get('type') in ('function_call','custom_tool_call')]
    require(bool(calls) and membership.original.core.route(calls[-1]['payload'],'functions','exec')
            and current_call_nonce in str(calls[-1]['payload'].get('input',calls[-1]['payload'].get('arguments',''))),
            'Fresh current ROOT call is not present in original session')
    call_id=calls[-1]['payload'].get('call_id')
    require(type(call_id) is str and bool(call_id),'Current original ROOT call identity required')
    require(header['id']==trusted_root_native_id,'Original externally trusted ROOT identity changed')
    directory=Path(directory)
    require(directory.is_absolute() and directory.resolve()==directory and directory.is_relative_to(ROOT/'results/improvement-v1'),
            'ROOT-owned exclusive anchor destination required')
    directory.mkdir()
    prefix=directory/'parent-prefix.jsonl'
    with prefix.open('xb') as stream:stream.write(raw)
    prefix.chmod(0o400)
    value={'schema_version':1,'parent_native_id':trusted_root_native_id,
           'original_source':str(source),'original_entity':entity,
           'prefix_reference':runtime.question_reference(prefix),'current_root_call_id':call_id,
           'allocation_authorized':False,'model_pilot_admitted':False}
    path=directory/'anchor.json';runtime.atomic_json(path,value,exclusive=True)
    return runtime.question_reference(path)


def retained_prefix_bytes(reference):
    runtime.question_verify_reference(reference)
    raw,_=capture.native_capture(Path(reference['path']))
    require(len(raw)==reference['entity']['bytes']
            and hashlib.sha256(raw).hexdigest()==reference['entity']['sha256'],
            'Exact retained native prefix bytes required')
    runtime.question_verify_reference(reference)
    return raw


class RootSource:
    def __init__(self,anchor_reference,*,trusted_root_native_id):
        value=runtime.strict.decoded(runtime.question_reference_bytes(anchor_reference))
        require(type(value) is dict and set(value)=={'schema_version','parent_native_id','original_source',
                'original_entity','prefix_reference','current_root_call_id','allocation_authorized','model_pilot_admitted'}
                and type(value['schema_version']) is int and value['schema_version']==1
                and value['allocation_authorized'] is False and value['model_pilot_admitted'] is False,
                'Exact original source anchor required')
        require(value['parent_native_id']==trusted_root_native_id,'External ROOT identity differs from anchor')
        self.anchor_reference=anchor_reference
        self.value=value
        self.source=session_locator(value['original_source'],trusted_root_native_id)
        prefix=retained_prefix_bytes(value['prefix_reference'])
        header=parent_header(prefix,trusted_root_native_id)
        require(header['id']==trusted_root_native_id,'Retained original ROOT prefix identity changed')
        calls=[e for e in membership.original.core.parse(prefix) if e['payload'].get('call_id')==value['current_root_call_id'] and e['payload'].get('type') in ('function_call','custom_tool_call')]
        require(len(calls)==1 and membership.original.core.route(calls[0]['payload'],'functions','exec'), 'Original ROOT anchoring call changed')
        self.prefix_sha256=hashlib.sha256(prefix).hexdigest();self.prefix_bytes=len(prefix)

    def parent(self):
        runtime.question_verify_reference(self.anchor_reference)
        runtime.question_verify_reference(self.value['prefix_reference'])
        raw,entity=capture.native_capture(self.source,self.value['original_entity'])
        require(len(raw)>=self.prefix_bytes
                and hashlib.sha256(raw[:self.prefix_bytes]).hexdigest()==self.prefix_sha256,
                'Original ROOT history rewritten or truncated')
        header=parent_header(raw,self.value['parent_native_id'])
        require(header['id']==self.value['parent_native_id'],'Current original ROOT identity changed')
        return raw,entity

    def root_origin(self,child_locator,expected_path):
        require(type(expected_path) is str and re.fullmatch('/root/[A-Za-z0-9_]+',expected_path),
                'Original registered immediate actor path required')
        parent,parent_entity=self.parent()
        child,child_entity=capture.native_capture(child_locator)
        events,header=membership.original.source(child,expected_path,self.value['parent_native_id'])
        session_locator(child_locator,header['id'])
        prefix=membership.original.first_request_prefix(child,'/root')
        origin=membership.original.native.binding(parent,prefix,'/root',expected_path)
        require(origin['parent_native_id']==self.value['parent_native_id']
                and origin['child_native_id']==header['id'],'Original genuine native allocation changed')
        require(capture.native_capture(self.source,parent_entity)[0]==parent
                and capture.native_capture(child_locator,child_entity)[0]==child,
                'Original source changed during allocation join')
        return {'native_join':origin,'parent_entity':parent_entity,'child_entity':child_entity,
                'allocation_authorized':False,'model_pilot_admitted':False}
