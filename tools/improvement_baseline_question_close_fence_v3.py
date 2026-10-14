"""Question closure source fence with immutable members and ROOT append checks.

This does not authenticate the coordinator or authorize delivery, grading or cleanup.
The normal closer supplies the original native inode and already captured parent.
"""
import hashlib
import stat
from pathlib import Path
import improvement_baseline_failure_close_v4 as preservation
import improvement_baseline_normal_close_v4 as normal

runtime=preservation.runtime
require=preservation.require
encoded=preservation.registry.encoded



def native_entity(path,previous_pin=None):
    """Capture original native bytes without treating a session as eval control."""
    path=Path(path)
    before=path.lstat()
    raw,pin=preservation.capture.native_capture(path,previous_pin)
    after=path.lstat()
    require(stat.S_ISREG(before.st_mode) and stat.S_ISREG(after.st_mode)
            and before.st_nlink==after.st_nlink==1
            and (before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)==(pin['device'],pin['inode'])
            and stat.S_IMODE(before.st_mode)==stat.S_IMODE(after.st_mode),
            'Original native identity/mode changed during question capture')
    return {'kind':'file','mode':stat.S_IMODE(before.st_mode),'bytes':len(raw),
            'sha256':hashlib.sha256(raw).hexdigest()},raw,pin

def fence(folder,config,auth,dispatch_config,member_sources,coordinator_source,*,parent_original,parent_pin):
    if config['case_id'] not in ('B03','B04'):return
    _,control,_=runtime._question_snapshot(folder,closing=True)
    reference=auth['control_pins'].get('no_more_delivery')
    require(type(reference) is dict and reference.get('path')==str(Path(folder)/'question/no-more-delivery.json'),
            'Original question no-more-delivery reference required')
    value=preservation.registry.strict.decoded(runtime.question_reference_bytes(reference))
    require(type(value.get('schema_version')) is int and value['schema_version']==1
            and value.get('no_more_delivery') is True
            and encoded(value.get('binding'))==encoded(control['binding'])
            and encoded(value.get('original_deadline'))==encoded(config['deadline']),
            'Question delivery fence identity changed')
    commitment=preservation.registry.strict.decoded(runtime.question_reference_bytes(value['commitment']))
    require(commitment.get('no_more_delivery') is True
            and commitment.get('coordinator_identity')==dispatch_config['coordinator_id']
            and encoded(commitment.get('binding'))==encoded(control['binding'])
            and control['binding']['root_native_uuid']==auth['member_native_ids'][dispatch_config['root_path']],
            'Original question coordinator/root commitment changed')
    entities=commitment.get('native_source_entities')
    names={str(Path(coordinator_source)),*(str(Path(p)) for p in member_sources.values())}
    require(type(entities) is dict and set(entities)==names,
            'Exact cumulative question closure native sources required')
    parent_name=str(Path(coordinator_source));entity=entities[parent_name]
    require(type(entity) is dict and set(entity)=={'kind','mode','bytes','sha256'}
            and entity['kind']=='file' and type(entity['bytes']) is int and entity['bytes']>0
            and type(entity['mode']) is int and type(entity['sha256']) is str,
            'Original typed question coordinator prefix entity required')
    require(type(parent_original) is bytes and len(parent_original)>=entity['bytes'],
            'Question commitment must precede original normal-close parent')
    prefix=parent_original[:entity['bytes']]
    require(hashlib.sha256(prefix).hexdigest()==entity['sha256'],
            'Original question coordinator prefix rewritten')
    # The commitment precedes normal-close inventory. New native activity between
    # those points also invalidates the question commitment, rather than being
    # hidden inside parent_original. The latest inventory must therefore already
    # be in the committed prefix.
    normal.parent_extension_fence(prefix,parent_original,prefix)
    current_entity,current,_=native_entity(coordinator_source,parent_pin)
    normal.parent_extension_fence(parent_original,current,parent_original)
    require(current_entity['mode']==entity['mode'], 'Question coordinator source mode changed')
    for name in names-{parent_name}:
        require(encoded(entities[name])==encoded(native_entity(name)[0]),
                'Question closure member source pin changed')
    runtime.question_verify_reference(reference)
    runtime.question_verify_reference(value['commitment'])
    final_entity,final_parent,_=native_entity(coordinator_source,parent_pin)
    require(final_entity['mode']==entity['mode'], 'Question coordinator source mode changed at final fence')
    normal.parent_extension_fence(parent_original,final_parent,current)
