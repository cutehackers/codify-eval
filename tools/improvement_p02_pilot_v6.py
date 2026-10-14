"""Prospective six-run harder pilot. Qualification, actor outcome and inference differ."""
import argparse
import fnmatch
import json
from pathlib import Path
import shutil
import subprocess
import time
from datetime import datetime
import improvement_software_broker_v7 as diagnostics

import improvement_run_v2 as prior
import prepare
import dispatch
import collect_schema_v366 as schema
import improvement_composed_quote_collect_v5 as collector
from improvement_baseline_q02_v2 import quiesce
from improvement_boundary_v1 import inspect_repo
from improvement_qualify_v1 import digest_tree
from improvement_usage_v4 import snapshot
from improvement_p02_verifier_v3 import verify as verify_software
from improvement_software_artifacts_v3 import atomic_json

ROOT=prepare.ROOT
PHASE='control-probe-P02-pilot-v6'
PLAN=ROOT/'results/improvement-v1/P02-prospective-pilot-allocation-plan-v6.json'
FREEZE=ROOT/'results/improvement-v1/P02-pilot-freeze-v6.json'
REVIEW=ROOT/'results/improvement-v1/P02-pilot-runner-v6-prelaunch-review-v1.json'
QUALIFICATION=ROOT/'results/improvement-v1/pilot-P02-behavior-qualification-review-v5.json'
CASE=ROOT/'improvement_cases/pilot-expansion-v11/P02'
BASE_COLLECT=schema.qualified_collect


def read(path):return json.loads(Path(path).read_bytes())
def sha(path):return prior.sha(path)


def case_directory(case):
    assert case=='P02'
    return CASE


def freeze():
    assert not FREEZE.exists()
    plan, review, quality=read(PLAN),read(REVIEW),read(QUALIFICATION)
    assert review['verdict']=='pass' and not review['issues']
    assert quality['verdict']=='pass' and quality['actualbehavior_qualified'] and not quality['issues']
    registration=collector.verify()
    receipt_path=ROOT/'results/improvement-v1/pilot-qualification-v5/P02/receipt.json'
    receipt=read(receipt_path)
    assert receipt['status']=='behavior_qualified' and receipt['source_hashes']==digest_tree(CASE)
    assert receipt['image_id']==read(ROOT/'runtime/image.json')['image_id']
    names={str(path.relative_to(ROOT)) for path in [PLAN,REVIEW,QUALIFICATION,receipt_path,Path(__file__).resolve(),collector.MANIFEST]}
    for pins in [plan['source_hashes'],review['source_hashes'],review['evidence_hashes'],quality['sourcepins'],quality['evidencepins'],quality['fullcase33sourcehashes'],registration['source_hashes']]:
        for name,digest in pins.items():
            assert sha(ROOT/name)==digest,name
            names.add(name)
    value={'status':'frozen','stage':'harder_exploratory_pilot','model':'gpt-6.1-sol','effort':'medium','concurrency':1,
           'trajectory_seconds':1200,'retries':0,'conditions':plan['conditions'],'sequence':plan['sequence'],
           'image_id':receipt['image_id'],'case_hashes':{'P02':prepare.tree_hash(CASE)},
           'skill_hashes':{c:prepare.tree_hash(ROOT/'snapshots'/c) for c in ['C0','C13']},
           'source_hashes':{name:sha(ROOT/name) for name in sorted(names)},
           'primary_confirmation_reuse_allowed':False,'superiority_proven':False,'complete_final_cost':False,
           'independent_tasks':1,'repeats':2,'public_only_actor_inputs':True,
           'deadline_controller':{'owner':'root','clock_anchor':'launch-intent.started_at',
               'observation_interval_seconds_max':30,'normal_close':'bind, actual native completion, collect, grade',
               'deadline_close':'interrupt original bound agent with collaboration.interrupt_agent; poll collaboration.list_agents with {}; retain same handle while live; invoke abort only after actual native receipts prove terminal or handle missing',
               'retry_on_observation_timeout':False,'aborted_final_cost_complete':False},
           'prior_infrastructure_failures':[{'run_id':name,'included_in_research_cost':True,'normal_comparison_eligible':False} for name in ['control-probe-P02-pilot-v1-P02-A-1','control-probe-P02-pilot-v2-P02-A-1','control-probe-P02-pilot-v3-P02-A-1','control-probe-P02-pilot-v4-P02-C0-1']],
           'limits':['Current opaque native initial payload requires prospective root input attestation; complete initial plaintext cannot be independently verified from native ciphertext','Exploratory pilot; no population superiority or final sample size inference','Product timeline includes preparation, observed actor and public verification; external private grading and coordination are separately labeled']}
    atomic_json(FREEZE,value,exclusive=True)
    return value


def configure():
    prior.FREEZE=FREEZE;prior.PHASE=PHASE;prior.case_directory=case_directory;prior.quiesce=quiesce
    value=prior.check()
    assert value['model']=='gpt-6.1-sol' and value['effort']=='medium'
    return value


def bound(run_id):
    value=configure();metadata=prior.bind(run_id,value)
    return value,metadata


def owned_identity(metadata):
    result=subprocess.run(['docker','inspect',metadata['container']],capture_output=True,text=True,timeout=30)
    result.check_returncode();identity=json.loads(result.stdout)[0]
    folder=ROOT/'runtime'/metadata['run_id']
    assert identity['Id']==metadata['container_id'] and identity['Image']==metadata['image_id']
    assert identity['HostConfig']['NetworkMode']=='none'
    assert len(identity['Mounts'])==2 and all(m['Type']=='bind' for m in identity['Mounts'])
    assert {m['Destination']:(m['Source'],m['RW']) for m in identity['Mounts']}=={
        '/work/repo':(str(folder/'repo'),True),'/eval-input':(str(folder/'control-inputs'),False)}
    return identity


def remove_owned(metadata):
    before=owned_identity(metadata);assert not before['State']['Running']
    subprocess.run(['docker','rm',metadata['container']],capture_output=True,check=True,timeout=30)
    gone=subprocess.run(['docker','inspect',metadata['container']],capture_output=True,text=True,timeout=30)
    assert gone.returncode!=0 and 'No such object' in gone.stderr
    return {'container_id':before['Id'],'removed':True,'finished_at':time.time()}


def next_allocation(value):
    for row in value['sequence']:
        out=ROOT/'results'/row['run_id'];path=out/'grade.json'
        if not path.exists():
            return row
        outcome=read(path)
        assert outcome['status'] in {'review_pending','pass','fail','infra_error','evaluation_error'}, 'Previous allocation not terminal'
        assert not outcome.get('lifecycle_errors') and outcome.get('product_cleanup',{}).get('removed') is True, 'Previous cleanup unproven'
        if outcome.get('actor_allocated') is not False:
            assert (out/'terminal-native.jsonl').is_file() and (out/'native-usage-v4.json').is_file(), 'Previous raw/cost evidence absent'
            usage=read(out/'native-usage-v4.json')
            assert usage['source_sha256']==sha(out/'terminal-native.jsonl'), 'Previous cost seal unproven'
            if outcome.get('deadline_aborted') is True:
                closure=read(out/'deadline-closure.json')
                assert outcome.get('deadline_aborted') is True and closure['actor_terminal_observed'] is True
                assert closure['parent_prefix_sha256']==sha(out/'deadline-parent-native.jsonl')
                assert closure['child_prefix_sha256']==usage['source_sha256']
                binding=read(out/'actor-binding.json')
                assert closure['agent_path']==binding['agent_path'] and closure['parent_thread_id']==binding['parent_thread_id']
                assert deadline_authority((out/'deadline-parent-native.jsonl').read_bytes(),binding,outcome['started_at']+1200)==closure['authority']
            else:assert usage['native_completion_observed'], 'Previous native terminal absent'
        if outcome['status']=='review_pending' or outcome.get('verification_receipt') or outcome.get('private_grading_allocated'):
            assert outcome.get('owned_grader_removed') is True, 'Previous private grading cleanup unproven'
    raise ValueError('All preregistered allocations already terminal')


def _launch(run_id):
    value=configure();row=next_allocation(value)
    assert row['run_id']==run_id,'Next preregistered allocation only'
    assert not subprocess.check_output(['docker','ps','-q','--filter','name=codify-'],text=True,timeout=30).strip()
    folder=ROOT/'runtime'/run_id;assert not folder.exists()
    name='codify-'+run_id.lower()
    absent=subprocess.run(['docker','inspect',name],capture_output=True,text=True,timeout=30)
    assert absent.returncode!=0 and 'No such object' in absent.stderr
    out=ROOT/'results'/run_id;out.mkdir()
    started=time.time();atomic_json(out/'launch-intent.json',{'run_id':run_id,'started_at':started,'actor_retries':0},exclusive=True)
    prepare.case_directory=case_directory
    prepared=prepare.prepare('P02',row['condition'],row['repeat'],PHASE)
    metadata=read(folder/'run.json')
    identity=json.loads(subprocess.check_output(['docker','inspect',metadata['container']],text=True,timeout=30))[0]
    metadata.update(evaluation_core={'path':str(FREEZE),'sha256':sha(FREEZE)},time_limit_seconds=1200,
                    user_turn_limit=1,started_at=started,container_id=identity['Id'])
    atomic_json(folder/'run.json',metadata)
    prior.bind(run_id,value);owned_identity(metadata);inspect_repo(folder/'repo')
    prompt=dispatch.dispatch(run_id)
    metadata=read(folder/'run.json')
    metadata.update(native_dispatch_started_at=metadata['agent_started_at'],agent_started_at=started)
    atomic_json(folder/'run.json',metadata)
    atomic_json(out/'bootstrap-input-intent.json',{'run_id':run_id,'created_at':time.time(),'bootstrap_sha256':sha(folder/'bootstrap.txt'),'request_sha256':sha(folder/'request.txt'),'model':'gpt-6.1-sol','effort':'medium','fork_turns':'none','owner':'root','native_plaintext_equality_required_when_available':True},exclusive=True)
    atomic_json(out/'dispatched.json',{'run_id':run_id,'dispatched_at':time.time(),'prompt_sha256':sha(folder/'request.txt')},exclusive=True)
    return prompt


def native_events(raw):
    assert raw.endswith(b'\n'), 'Incomplete native prefix; observe same session again'
    return [json.loads(line) for line in raw.splitlines()]


def parent_source(parent_id):
    from collect import SESSION_ROOT
    matches=[]
    for path in SESSION_ROOT.glob('2026/10/*/*.jsonl'):
        with path.open('rb') as stream:
            header=json.loads(stream.readline()).get('payload',{})
        if header.get('id')==parent_id:
            assert not header.get('parent_thread_id'), 'Coordinator must be actual root'
            matches.append(path)
    assert len(matches)==1, 'One actual native parent required'
    return matches[0]


def native_calls(events):
    calls={};pairs=[]
    for index,event in enumerate(events):
        p=event.get('payload',{})
        if event.get('type')!='response_item':continue
        if p.get('type')=='function_call' and p.get('namespace')=='collaboration' and p.get('name') in {'spawn_agent','interrupt_agent','list_agents'}:
            assert p['call_id'] not in calls
            calls[p['call_id']]=(index,event,p)
        elif p.get('type')=='function_call_output' and p.get('call_id') in calls:
            start,event_call,call=calls.pop(p['call_id'])
            try:result=json.loads(p['output'])
            except (ValueError,TypeError):result={'invalid_output':True}
            if not isinstance(result,dict):result={'invalid_output':True}
            pairs.append((start,index,event_call,call,result,event))
    return pairs


def bind_actor(run_id,agent_path):
    from collect import find_session
    _,metadata=bound(run_id);out=ROOT/'results'/run_id
    path=out/'actor-binding.json'
    source=find_session(agent_path);raw=source.read_bytes();observed=snapshot(raw,agent_path,str(source))
    parent=parent_source(observed['parent_thread_id']);events=native_events(parent.read_bytes())
    expected=(ROOT/'runtime'/run_id/'bootstrap.txt').read_text()
    intent=read(out/'bootstrap-input-intent.json')
    assert intent['run_id']==run_id and intent['owner']=='root'
    assert intent['bootstrap_sha256']==sha(ROOT/'runtime'/run_id/'bootstrap.txt') and intent['request_sha256']==sha(ROOT/'runtime'/run_id/'request.txt')
    assert intent['model']=='gpt-6.1-sol' and intent['effort']=='medium' and intent['fork_turns']=='none'
    child_events=native_events(raw)
    messages=[(i,e) for i,e in enumerate(child_events) if e.get('payload',{}).get('type')=='agent_message']
    tool_calls=[(i,e) for i,e in enumerate(child_events) if e.get('type')=='response_item' and e.get('payload',{}).get('type') in {'custom_tool_call','function_call'}]
    if not tool_calls:raise prior.ActorNotTerminal('Bootstrap tool evidence pending; observe same actor')
    first_index,first_event=tool_calls[0];first=first_event['payload']
    assert first['type']=='custom_tool_call' and first['name']=='exec'
    assert first.get('namespace','functions')=='functions', 'Unexpected explicit bootstrap namespace'
    assert first['input'].strip(' \t\r\n')==expected.split('\n',1)[1].strip(' \t\r\n'), 'Actual first tool must be sole public bootstrap read'
    receipts=[(i,e) for i,e in enumerate(child_events) if e.get('type')=='response_item' and
              e.get('payload',{}).get('type')=='custom_tool_call_output' and e['payload'].get('call_id')==first['call_id']]
    if not receipts:raise prior.ActorNotTerminal('Actual bootstrap read receipt pending; retain same actor')
    assert len(receipts)==1 and receipts[0][0]>first_index
    assert len(tool_calls)==1 or receipts[0][0]<tool_calls[1][0], 'Bootstrap must finish before repository tools'
    blocks=receipts[0][1]['payload']['output']
    assert isinstance(blocks,list) and len(blocks)==2 and all(b.get('type')=='input_text' and isinstance(b.get('text'),str) for b in blocks)
    assert blocks[0]['text'].startswith('Script completed\nWall time ') and blocks[0]['text'].endswith(' seconds\nOutput:\n')
    read_result=json.loads(blocks[1]['text'])
    assert type(read_result.get('exit_code')) is int and read_result['exit_code']==0 and not read_result.get('session_id')
    assert read_result.get('output')==(ROOT/'runtime'/run_id/'request.txt').read_text(), 'Actual successful read must return complete attested public request'
    matches=[];delivery=None
    for start,end,event,call,result,_ in native_calls(events):
        if call['name']!='spawn_agent' or result.get('task_name')!=agent_path:continue
        args=json.loads(call['arguments'])
        assert args.get('fork_turns')=='none' and args.get('model')=='gpt-6.1-sol' and args.get('reasoning_effort')=='medium'
        message=args.get('message')
        assert isinstance(message,str)
        if message==expected:
            delivery={'mode':'native_plaintext','initial_plaintext_verified_from_native':True}
        else:
            assert message.startswith('gAAAA'), 'Unexpected initial payload representation'
            assert len(messages)==1 and messages[0][0]<first_index
            message_event=messages[0][1];message_payload=message_event['payload']
            assert event['timestamp']<=message_event['timestamp']<=first_event['timestamp'], 'Actual dispatch and delivery must precede first read'
            assert message_payload['author']=='/root' and message_payload['recipient']==agent_path
            content=message_payload['content']
            assert len(content)==2 and content[0]=={'type':'input_text','text':'Message Type: NEW_TASK\nTask name: '+agent_path+'\nSender: /root\nPayload:\n'}
            assert content[1]=={'type':'encrypted_content','encrypted_content':message}, 'Actual parent-to-child delivery must match exact opaque bytes'
            delivery={'mode':'root_attested_plaintext_with_native_opaque_delivery','initial_plaintext_verified_from_native':False,'opaque_message_sha256':__import__('hashlib').sha256(message.encode()).hexdigest(),'limit':'Complete initial plaintext is root-attested; native ciphertext is not decrypted or independently checked as plaintext'}
        assert datetime.fromisoformat(event['timestamp'].replace('Z','+00:00')).timestamp()>=intent['created_at'], 'Input intent must precede allocation'
        assert datetime.fromisoformat(event['timestamp'].replace('Z','+00:00')).timestamp()>=metadata['started_at']
        matches.append(call['call_id'])
    assert len(matches)==1, 'One fresh actual allocation required'
    binding={'run_id':run_id,'agent_path':agent_path,'native_session_id':observed['native_session_id'],
             'parent_thread_id':observed['parent_thread_id'],'native_source':str(source),'parent_source':str(parent),
             'spawn_call_id':matches[0],'bootstrap_sha256':sha(ROOT/'runtime'/run_id/'bootstrap.txt'),'input_intent_sha256':sha(out/'bootstrap-input-intent.json'),'delivery':delivery,
             'actual_bootstrap_call_id':first['call_id'],'actual_bootstrap_exit_code':0,'actual_public_request_read_verified':True}
    if path.exists():assert read(path)==binding, 'Cannot replace original actor'
    else:atomic_json(path,binding,exclusive=True)
    return binding


def deadline_authority(raw,binding,deadline):
    events=native_events(raw);headers=[e['payload'] for e in events if e.get('type')=='session_meta']
    assert len(headers)==1 and headers[0]['id']==binding['parent_thread_id'] and not headers[0].get('parent_thread_id')
    pairs=native_calls(events)
    interruptions=[]
    for start,end,event,call,result,output_event in pairs:
        if call['name']=='interrupt_agent' and json.loads(call['arguments'])=={'target':binding['agent_path']}:
            assert 'previous_status' in result and set(result)=={'previous_status'}, 'Interrupt must succeed'
            when=datetime.fromisoformat(event['timestamp'].replace('Z','+00:00')).timestamp()
            if when>=deadline:interruptions.append((end,call['call_id']))
    assert interruptions, 'Actual same-actor deadline interrupt required'
    for end,interrupt_id in reversed(interruptions):
        for start,stop,event,call,result,output_event in pairs:
            if start<=end or call['name']!='list_agents' or json.loads(call['arguments'])!={}:continue
            assert isinstance(result.get('agents'),list)
            agents=result['agents'];names=[a['agent_name'] for a in agents];assert len(names)==len(set(names))
            selected=[a for a in agents if a['agent_name']==binding['agent_path']]
            status=selected[0]['agent_status'] if selected else 'handle_missing'
            closed={'completed','failed','interrupted','shutdown'}
            terminal=(isinstance(status,str) and status in closed|{'handle_missing'} or
                      isinstance(status,dict) and len(status)==1 and next(iter(status)) in closed)
            if terminal:
                return {'interrupt_call_id':interrupt_id,'terminal_poll_call_id':call['call_id'],
                        'observed_status':status,'observed_at':output_event['timestamp']}
    raise prior.ActorNotTerminal('Actual original actor still live; poll same handle, retain resources')


def abort_deadline(run_id,agent_path):
    _,metadata=bound(run_id);out=ROOT/'results'/run_id
    assert time.time()>=metadata['started_at']+1200, 'No early deadline abort'
    assert not (out/'grade.json').exists(), 'Preserve original outcome'
    binding=bind_actor(run_id,agent_path)
    parent_raw=Path(binding['parent_source']).read_bytes()
    authority=deadline_authority(parent_raw,binding,metadata['started_at']+1200)
    source=Path(binding['native_source']);raw=source.read_bytes();observed=snapshot(raw,agent_path,str(source))
    assert observed['native_session_id']==binding['native_session_id']
    for name,data in [('deadline-parent-native.jsonl',parent_raw),('terminal-native.jsonl',raw)]:
        with (out/name).open('xb') as stream:stream.write(data)
    atomic_json(out/'native-usage-v4.json',observed,exclusive=True)
    closure={'agent_path':agent_path,'parent_thread_id':binding['parent_thread_id'],'actor_terminal_observed':True,
             'authority':authority,'parent_prefix_sha256':sha(out/'deadline-parent-native.jsonl'),
             'child_prefix_sha256':observed['source_sha256'],'final_cost_complete':False}
    atomic_json(out/'deadline-closure.json',closure,exclusive=True)
    value={'run_id':run_id,'status':'fail','deadline_aborted':True,'time_limit_exceeded':True,
           'actor_allocated':True,'actor_retried':False,'behavior_pass':False,'overall_pass':False,
           'started_at':metadata['started_at'],'usage':observed,'complete_final_cost':False,
           'cost_scope':'Observed prefix after authoritative interruption; later usage may remain unavailable',
           'lifecycle_errors':[]}
    atomic_json(out/'grade.json',value,exclusive=True)
    try:
        identity=owned_identity(metadata)
        if identity['State']['Running']:
            try:subprocess.run(['docker','stop','-t','2',metadata['container']],capture_output=True,check=True,timeout=10)
            except (subprocess.TimeoutExpired,subprocess.CalledProcessError):
                subprocess.run(['docker','kill',metadata['container']],capture_output=True,check=True,timeout=10)
        assert not owned_identity(metadata)['State']['Running']
        with (out/'deadline-docker-diff.txt').open('x') as stream:
            subprocess.run(['docker','diff',metadata['container']],stdout=stream,stderr=subprocess.PIPE,text=True,check=True,timeout=30)
        diagnostics.preserve_tmp(out,metadata['container'],'deadline')
        atomic_json(out/'deadline-artifact-seal.json',{'files':digest_tree(ROOT/'runtime'/run_id/'repo')},exclusive=True)
        value['product_cleanup']=remove_owned(metadata)
    except Exception as error:value['lifecycle_errors'].append({'type':type(error).__name__,'message':str(error)})
    value['finished_at']=time.time();atomic_json(out/'grade.json',value)
    return value


def launch(run_id):
    out=ROOT/'results'/run_id
    fresh=not out.exists()
    try:
        return _launch(run_id)
    except Exception as error:
        if not fresh or not (out/'launch-intent.json').exists():
            raise
        intent=read(out/'launch-intent.json')
        value={'run_id':run_id,'status':'infra_error','reason':str(error),'actor_allocated':False,
               'actor_retried':False,'behavior_pass':None,'overall_pass':None,'lifecycle_errors':[]}
        atomic_json(out/'grade.json',value,exclusive=True)
        folder=ROOT/'runtime'/run_id;name='codify-'+run_id.lower()
        try:
            found=subprocess.run(['docker','inspect',name],capture_output=True,text=True,timeout=30)
            if found.returncode==0:
                identity=json.loads(found.stdout)[0]
                assert identity['Image']==read(FREEZE)['image_id']
                assert identity['HostConfig']['NetworkMode']=='none'
                assert datetime.fromisoformat(identity['Created'].replace('Z','+00:00')).timestamp()>=intent['started_at']
                assert len(identity['Mounts'])==2 and all(m['Type']=='bind' for m in identity['Mounts']) and {m['Destination']:(m['Source'],m['RW']) for m in identity['Mounts']}=={
                    '/work/repo':(str(folder/'repo'),True),'/eval-input':(str(folder/'control-inputs'),False)}
                metadata={'run_id':run_id,'container':name,'container_id':identity['Id'],'image_id':identity['Image']}
                atomic_json(out/'failed-preparation-identity.json',identity,exclusive=True)
                if identity['State']['Running']:
                    try:subprocess.run(['docker','stop','-t','2',name],capture_output=True,check=True,timeout=10)
                    except Exception:subprocess.run(['docker','kill',name],capture_output=True,check=True,timeout=10)
                assert not owned_identity(metadata)['State']['Running']
                diagnostics.preserve_tmp(out,name,'failed-preparation')
                value['product_cleanup']=remove_owned(metadata)
            else:
                assert 'No such object' in found.stderr
                value['product_cleanup']={'removed':True,'no_container_allocated':True}
        except Exception as cleanup:
            value['lifecycle_errors'].append({'type':type(cleanup).__name__,'message':str(cleanup)})
        value['finished_at']=time.time();atomic_json(out/'grade.json',value)
        raise


def collect(run_id,agent_path):
    _,metadata=bound(run_id)
    binding=bind_actor(run_id,agent_path)
    owned_identity(metadata)
    assert schema.qualified_collect is BASE_COLLECT
    schema.qualified_collect=collector.qualified_collect
    try:
        result=prior.collect_run(run_id,agent_path)
    finally:
        schema.qualified_collect=BASE_COLLECT
    from collect import find_session
    source=find_session(agent_path);raw=source.read_bytes();observed=snapshot(raw,agent_path,str(source))
    out=ROOT/'results'/run_id
    atomic_json(out/'native-usage-v4.json',observed,exclusive=True)
    with (out/'terminal-native.jsonl').open('xb') as stream:stream.write(raw)
    assert observed['native_session_id']==binding['native_session_id'] and observed['native_completion_observed']
    completion_times=[datetime.fromisoformat(e['timestamp'].replace('Z','+00:00')).timestamp()
                      for e in native_events(raw) if e.get('type')=='event_msg' and e.get('payload',{}).get('type')=='task_complete']
    timing={'allocation_started_at':metadata['started_at'],'native_terminal_at':max(completion_times),
            'allocation_to_native_terminal_seconds':max(completion_times)-metadata['started_at'],
            'native_duration_seconds':sum(c['duration_ms']/1000 for c in observed['completions']),
            'filesystem_stopped_observed_at':read(out/'quiescence.json')['finished_at']}
    timing['allocation_to_quiescence_seconds']=timing['filesystem_stopped_observed_at']-metadata['started_at']
    atomic_json(out/'product-timing.json',timing,exclusive=True)
    if (out/'grade.json').exists():
        outcome=read(out/'grade.json')
        gone=subprocess.run(['docker','inspect',metadata['container']],capture_output=True,text=True,timeout=30)
        assert gone.returncode!=0 and 'No such object' in gone.stderr, 'Failed collector resource removal unproven'
        outcome.update(product_cleanup={'removed':True,'container_id':metadata['container_id'],'finished_at':time.time()},actor_allocated=True,
                       product_timing=timing,time_limit_exceeded=timing['allocation_to_native_terminal_seconds']>1200)
        atomic_json(out/'grade.json',outcome)
    return result


def grade(run_id):
    _,metadata=bound(run_id);folder=ROOT/'runtime'/run_id;out=ROOT/'results'/run_id
    assert not (out/'grade.json').exists()
    assert metadata['status']=='collected' and len(metadata['turns'])==1
    assert not owned_identity(metadata)['State']['Running']
    inspect_repo(folder/'repo');actual=digest_tree(folder/'repo')
    assert actual==read(out/'artifact-seal.json')['files']
    original=digest_tree(CASE/'repo')
    if metadata['condition']!='A':
        original.update({'.agents/skills/codify/'+n:d for n,d in digest_tree(ROOT/'snapshots'/metadata['condition']).items()})
    changes=sorted(n for n in set(original)|set(actual) if original.get(n)!=actual.get(n))
    case_meta=read(CASE/'metadata.json')
    invalid=[n for n in changes if not any(fnmatch.fnmatch(n,p) for p in case_meta['allowed_paths'])]
    protected=[n for n in case_meta['protected_paths'] if original.get(n)!=actual.get(n)]
    skill_intact=metadata['condition']=='A' or prepare.tree_hash(folder/'repo/.agents/skills/codify')==metadata['skill_hash']
    value={'run_id':run_id,'status':'grading','behavior_pass':None,'scope_pass':not invalid and not protected and skill_intact,
           'report_pass':None,'overall_pass':None,'changed':changes,'out_of_scope':invalid,'protected_changes':protected,
           'skill_intact':skill_intact,'usage':read(out/'native-usage-v4.json'),'superiority_proven':False,
           'primary_confirmation_reuse_allowed':False,'complete_final_cost':False,'started_at':metadata['started_at'],
           'grading_started_at':time.time(),'lifecycle_errors':[],
           'product_timing':read(out/'product-timing.json'),
           'time_limit_exceeded':read(out/'product-timing.json')['allocation_to_native_terminal_seconds']>1200,
           'transport_violations':metadata.get('tool_audit',[]),
           'private_grading_budget_seconds':600,'private_grading_time_separate_from_actor_budget':True}
    atomic_json(out/'grade.json',value,exclusive=True)
    try:
        assert not metadata.get('tool_audit'), 'Transport boundary violation; software grade ineligible'
        source=ROOT/'runtime/P02-private-grading-v6'/run_id/'source'
        source.parent.mkdir(parents=True);shutil.copytree(folder/'repo',source,ignore=shutil.ignore_patterns('.git','.dart_tool','build','__pycache__','.agents'))
        shutil.copytree(CASE/'oracle/test',source/'test',dirs_exist_ok=True)
        value['private_grading_allocated']=True
        atomic_json(out/'grade.json',value)
        execution=verify_software(source,source.parent/'execution',time.time()+600,24,True)
        value.update(verification_receipt=str((source.parent/'execution/receipt.json').relative_to(ROOT)),
                     verification_receipt_sha256=sha(source.parent/'execution/receipt.json'),checks=execution['checks'],
                     machine=execution.get('machine'),owned_grader_removed=execution.get('removed'))
        assert execution['status']=='completed' and execution['removed'] and execution['source_unchanged']
        value['behavior_pass']=execution['pass']
        value['status']='review_pending'
    except Exception as error:
        value.update(status='evaluation_error',first_error={'type':type(error).__name__,'message':str(error)})
    finally:
        try:value['product_cleanup']=remove_owned(metadata)
        except Exception as error:
            value['lifecycle_errors'].append({'type':type(error).__name__,'message':str(error)});value['status']='evaluation_error'
        value['finished_at']=time.time();value['allocation_to_grade_cleanup_seconds']=value['finished_at']-metadata['started_at']
        atomic_json(out/'grade.json',value)
    return value


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['freeze','prepare','bind','abort','collect','grade']);parser.add_argument('run',nargs='?');parser.add_argument('agent_path',nargs='?');args=parser.parse_args()
    result=freeze() if args.action=='freeze' else launch(args.run) if args.action=='prepare' else bind_actor(args.run,args.agent_path) if args.action=='bind' else abort_deadline(args.run,args.agent_path) if args.action=='abort' else collect(args.run,args.agent_path) if args.action=='collect' else grade(args.run)
    print(result if isinstance(result,str) else json.dumps({k:v for k,v in result.items() if k not in {'source_hashes','checks','usage','machine'}},ensure_ascii=False))
