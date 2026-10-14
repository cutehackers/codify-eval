"""ROOT-only question NMD commit for externally authenticated native sources.

Uses the existing original coordinator capability and question lifecycle lock.
The calling ROOT must supply original session locators and enforce all-member
terminal -> final unfiltered inventory -> commitment chronology. This helper
checks byte identities, not caller trust or native session membership.
"""
import time
from pathlib import Path
import improvement_baseline_question_close_fence_v2 as sources
import improvement_baseline_question_branch_v1 as branch
runtime=sources.runtime
require=sources.require
encoded=sources.encoded


def commit(folder,coordinator_capability,reason,commitment_reference):
    with runtime.question_operation_lock(folder):
        _,control,_=runtime.question_coordinator_auth(folder,coordinator_capability,closing=True)
        require(type(reason) is str and bool(reason.strip()),'Explicit coordinator close reason required')
        value=runtime.strict.decoded(runtime.question_reference_bytes(commitment_reference))
        require(type(value) is dict and set(value)=={'schema_version','binding','coordinator_identity',
                'native_source_entities','no_more_delivery','committed_at'}
                and type(value['schema_version']) is int and value['schema_version']==1
                and encoded(value['binding'])==encoded(control['binding'])
                and value['coordinator_identity']==control['coordinator_identity']
                and value['no_more_delivery'] is True
                and type(value['native_source_entities']) is dict and bool(value['native_source_entities']),
                'Exact original coordinator native commitment required')
        at=branch.finite(value['committed_at'])
        require(control['original_started_at']<=at<=time.time(),'Original commitment clock changed')
        for path,entity in value['native_source_entities'].items():
            branch.entity(entity)
            require(encoded(sources.native_entity(path)[0])==encoded(entity),
                    'Original native commitment source changed')
        runtime.question_verify_reference(commitment_reference)
        output=Path(folder)/'question/no-more-delivery.json'
        runtime.atomic_json(output,{'schema_version':1,'binding':control['binding'],'reason':reason,
            'commitment':commitment_reference,'original_deadline':control['original_deadline'],
            'no_more_delivery':True,'committed_at':time.time()},exclusive=True)
        return runtime.question_reference(output)
