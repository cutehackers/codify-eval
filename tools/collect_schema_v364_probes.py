"""Static presentation, unchanged guard and read-only native provenance probes."""
import copy
import hashlib
import json
from pathlib import Path
import re
import shlex
import tempfile
from unittest.mock import patch
import collect_schema_v364 as adapter
import collect_schema as approved
import transport
from prepare import ROOT


def decode_template(body):
    """Bounded static literal decoder for provenance comparison, never JS eval."""
    out=[];i=0
    escapes={'n':'\n','r':'\r','t':'\t','b':'\b','f':'\f','v':'\v','0':'\0'}
    while i<len(body):
        char=body[i];i+=1
        if char!='\\':out.append(char);continue
        if i==len(body):raise ValueError('Unclosed template escape')
        char=body[i];i+=1
        if char in escapes:out.append(escapes[char])
        elif char in "\\`$'\"":out.append(char)
        elif char=='\n':pass
        elif char in ('u','x'):
            count=4 if char=='u' else 2;token=body[i:i+count]
            if len(token)!=count or not re.fullmatch(r'[0-9a-fA-F]+',token):raise ValueError('Unsupported template escape')
            out.append(chr(int(token,16)));i+=count
        else:raise ValueError('Unsupported template escape')
    return ''.join(out)


def run():
    checks=[]
    def check(name,value):checks.append({'name':name,'pass':bool(value)})
    original=transport.wrapper_origin
    review_path=ROOT/'results/software-poll-origin-validity-review-v3.6.4.json'
    review=json.loads(review_path.read_text())
    review_sha=adapter.digest(review_path)
    origins=[];current=[];flagged_count=0
    for reviewed in review['runs']:
        run_id=reviewed['run_id'];out=ROOT/'results'/run_id
        native=out/'native-tools.jsonl';manifest=out/'manifest.json'
        ledger=ROOT/'runtime'/run_id/'commands.jsonl'
        paths=[native,manifest,ledger,ROOT/'runtime'/run_id/'run.json',out/'turns.json']
        paths += [p for p in (out/'grade.json',out/'controlled-input-audit.json',out/'software-gui-transport-audit-v3.6.3.json') if p.exists()]
        before={str(p):adapter.digest(p) for p in paths}
        events=[json.loads(line) for line in native.read_text().splitlines()]
        metadata=json.loads(manifest.read_text());commands=[json.loads(line) for line in ledger.read_text().splitlines()]
        with patch.object(transport,'wrapper_origin',approved.wrapper_origin):
            old_audit,old_polls=transport.audit_transport(events,metadata,str(ROOT))
        with adapter.patched_origin():new_audit,new_polls=transport.audit_transport(events,metadata,str(ROOT))
        added=[p for p in new_polls if p not in old_polls]
        check(run_id+': exact reviewed old flags agree',old_audit==reviewed['original_tool_audit'])
        check(run_id+': only proven old flags removed',not new_audit and len(added)==len(old_audit))
        flagged_count+=len(added)
        for origin in reviewed['origins']:
            call=origin['origin_call_id']
            payload=next(e['payload'] for e in events if e['payload'].get('call_id')==call and e['payload'].get('type') in {'custom_tool_call','function_call'})
            code=payload.get('input',payload.get('arguments',''))
            view,count=adapter.classifier_view(code)
            check(call+': original source rejects/new canonical accepts',not adapter.ORIGINAL_WRAPPER_ORIGIN(code,str(ROOT),run_id) and adapter.wrapper_origin(code,str(ROOT),run_id) and count>0)
            check(call+': exact original code pin',hashlib.sha256(code.encode()).hexdigest()==origin['native_code_sha256'])
            match=adapter.TEMPLATE.fullmatch(code.strip())
            if match:
                decoded=decode_template(match.group(2))
                argv=shlex.split(f"python3 {ROOT}/tools/agent_io.py --run {run_id} --cmd '"+decoded.replace("'","'\\''")+"'")
            else:
                literal=re.search(r'cmd\s*:\s*('+transport.STRING+')',code)
                host=json.loads(literal.group(1));argv=shlex.split(host);decoded=argv[-1]
                canonical_host=json.loads(re.search(r'cmd\s*:\s*('+transport.STRING+')',view).group(1))
                check(call+': direct exact host argv equality',shlex.split(host)==shlex.split(canonical_host))
            check(call+': native inner command and scoped six argv agree',decoded==origin['decoded_inner_command'] and argv==origin['exact_six_scoped_host_argv'] and len(argv)==6)
            actual_records=[record for record in commands if record['command']==decoded]
            check(call+': unique preserved proxy command ledger match',len(actual_records)==1 and actual_records[0]==origin['terminal_native_command_record'])
            owned=[poll for poll in added if poll['origin_call_id']==call]
            check(call+': real SID owns all intended empty polls',bool(owned) and all(p['session_id']==origin['normal_output_session_id'] and p['empty_stdin'] for p in owned))
            outputs=[]
            for event in events:
                p=event['payload']
                if p.get('call_id') in {poll['poll_call_id'] for poll in owned} and p.get('type') in {'function_call_output','custom_tool_call_output'}:
                    outputs.extend(transport.result_objects(p))
            terminal=[o for o in outputs if type(o.get('exit_code')) is int]
            check(call+': one real terminal output closes session',len(terminal)==1 and terminal[0]['exit_code']==origin['terminal_host_exit_code'])
            record=json.loads(terminal[0]['output']) if terminal else None
            check(call+': terminal native output matches full proxy record',record==actual_records[0])
            origins.append({'run_id':run_id,'origin_call_id':call,'session_id':origin['normal_output_session_id'],
                            'source_code_sha256':hashlib.sha256(code.encode()).hexdigest(),'classifier_view_sha256':hashlib.sha256(view.encode()).hexdigest(),
                            'presentation_transform_count':count,'actual_command_sha256':hashlib.sha256(decoded.encode()).hexdigest(),
                            'owned_poll_proofs':owned,'terminal_poll_call_id':origin['terminal_poll_call_id'],'terminal_host_exit_code':terminal[0]['exit_code'] if terminal else None})
        # Unchanged auditor remains responsible for wrong SID/input/origin/result.
        chosen=added[0]
        for name,kind in [('foreign SID','foreign'),('nonempty stdin','stdin'),('poll after completion','after'),('missing origin output','missing'),('abnormal origin output','abnormal'),('wrong poll result SID','wrongresult')]:
            mutated=copy.deepcopy(events)
            if kind in {'foreign','stdin'}:
                p=next(e['payload'] for e in mutated if e['payload'].get('call_id')==chosen['poll_call_id'] and e['payload'].get('type') in {'custom_tool_call','function_call'})
                key='input' if 'input' in p else 'arguments'
                p[key]=f'text(await tools.write_stdin({{session_id:{987654321 if kind=="foreign" else chosen["session_id"]},chars:{json.dumps("x" if kind=="stdin" else "")}}}));'
            elif kind=='after':
                p=copy.deepcopy(next(e for e in mutated if e['payload'].get('call_id')==chosen['poll_call_id'] and e['payload'].get('type') in {'custom_tool_call','function_call'}));p['payload']['call_id']='late_poll';mutated.append(p)
            elif kind=='missing':
                mutated=[e for e in mutated if not (e['payload'].get('call_id')==chosen['origin_call_id'] and e['payload'].get('type') in {'custom_tool_call_output','function_call_output'})]
            else:
                call=chosen['origin_call_id'] if kind=='abnormal' else chosen['poll_call_id']
                p=next(e['payload'] for e in mutated if e['payload'].get('call_id')==call and e['payload'].get('type') in {'custom_tool_call_output','function_call_output'})
                result={'session_id':987654321 if kind=='wrongresult' else chosen['session_id'],'output':'','wall_time_seconds':1}
                if kind=='abnormal':result.pop('wall_time_seconds')
                p['output']=json.dumps(result)
            with adapter.patched_origin():bad,_=transport.audit_transport(mutated,metadata,str(ROOT))
            check(run_id+': '+name+' remains violation',bool(bad))
        check(run_id+': native/ledger/manifest/turns/grade/audits byte unchanged',before=={str(p):adapter.digest(p) for p in paths})
        current.append({'run_id':run_id,'original_violation_count':len(old_audit),'qualified_violation_count':len(new_audit),
                        'added_owned_poll_count':len(added),'native_sha256':before[str(native)],'source_and_artifacts_unmutated':True})
    check('exactly nine real origins and seventeen proven flags',len(origins)==9 and flagged_count==17)
    # Static quote/value equivalence, without launching or evaluating source.
    run_id='probe'
    prefix=f"python3 {ROOT}/tools/agent_io.py --run {run_id} --cmd "
    for inner in ("plain", "apostrophe ' inside", "'", "''", "a'\n b'", 'Unicode 한국어', '', 'last inner space '):
        host=prefix+"'"+inner.replace("'","'\\''")+"'"
        for trailing in (' ','\t','\n',' \t\n'):
            code='text(await tools.exec_command({cmd:'+json.dumps(host+trailing)+'}));'
            view,count=adapter.classifier_view(code)
            canonical=json.loads(re.search(r'cmd\s*:\s*('+transport.STRING+')',view).group(1))
            check('safe outer whitespace '+repr(inner)+repr(trailing),adapter.wrapper_origin(code,str(ROOT),run_id) and shlex.split(host+trailing)==shlex.split(canonical) and shlex.split(canonical)[-1]==inner and count==1)
        for trailing in ('\r','\f','\v','\u00a0'):
            code='text(await tools.exec_command({cmd:'+json.dumps(host+trailing)+'}));'
            check('non-shell whitespace rejected '+repr(inner)+repr(trailing),not adapter.wrapper_origin(code,str(ROOT),run_id))
    malformed='text(await tools.exec_command({cmd:'+json.dumps(prefix+"'unclosed ")+'}));'
    check('malformed host quote view rejects without throwing',adapter.classifier_view(malformed)==(malformed,0) and not adapter.wrapper_origin(malformed,str(ROOT),run_id))
    search=json.dumps("'");replacement=json.dumps("'\\''")
    template='const cmd=`literal \' content`; text(await tools.exec_command({cmd:'+json.dumps(prefix+"'")+'+cmd.replaceAll('+search+','+replacement+')+"\'"}));'
    check('literal replaceAll static equivalence',adapter.wrapper_origin(template,str(ROOT),run_id))
    template_match=adapter.TEMPLATE.fullmatch(template.strip())
    def replace_body(body):return template[:template_match.start(2)]+body+template[template_match.end(2):]
    for count in range(5):
        code=replace_body('\\'*count+'${name}')
        check('escaped interpolation parity '+str(count),adapter.wrapper_origin(code,str(ROOT),run_id)==bool(count%2))
    for name,code in {
        'dynamic search':template.replace(search+',','search,'),
        'wrong search':template.replace(search+',',json.dumps('x')+','),
        'dynamic callback':template.replace(replacement,'callback'),
        'wrong shell quote':template.replace(replacement,json.dumps("'")),
        'replacement expansion':template.replace(replacement,json.dumps('$&')),
        'actual interpolation':replace_body('${value}'),
        'additional statement':template+'text(1);',
        'additional tool':template.replace('tools.exec_command','tools.apply_patch'),
        'other run':template.replace('--run probe','--run other'),
        'unknown prefix':template.replace('python3 ','evilpython3 '),
        'unknown wrapper':template.replace('text(await','notify(await'),
    }.items():check(name+' rejected',not adapter.wrapper_origin(code,str(ROOT),run_id))
    check('original accepted wrapper remains unchanged',adapter.classifier_view(template.replace('.replaceAll('+search+',',".replace(/'/g,"))[1]==0)
    try:
        with adapter.patched_origin():raise RuntimeError('probe')
    except RuntimeError:pass
    check('runtime patch exception restores frozen classifier',transport.wrapper_origin is original)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for name in adapter.REQUIRED_PINS:
            file = root / name; file.parent.mkdir(parents=True, exist_ok=True); file.write_text('{}')
        for operational in ('results/frozen-escaped-template-collection-v3.6.2.json','results/frozen-software-gui-transport-v3.6.3.json'):
            (root/operational).write_text(json.dumps({'status':'frozen','source_sha256':{}}))
        (root / 'results/frozen-core-v3.6.json').write_text(json.dumps({'core_version': 'v3.6', 'freeze_revision': 2, 'grader_hashes': {}}))
        (root / 'results/frozen-native-schema-v3.6.1.json').write_text(json.dumps({'version': 'native-content-v1', 'status': 'frozen', 'source_sha256': {}}))
        registration = {'version': adapter.VERSION, 'status': 'frozen', 'actor_reexecution_allowed': False,
                        'source_sha256': {n: adapter.digest(root/n) for n in adapter.REQUIRED_PINS}}
        reg = root / 'registration.json'
        def rejected(fn):
            try: fn(); return False
            except (ValueError, FileNotFoundError): return True
        with patch.object(adapter, 'ROOT', root), patch.object(adapter, 'MANIFEST', reg):
            check('missing registration rejects', rejected(lambda: adapter.verify_registration(reg)))
            reg.write_text(json.dumps(registration)); check('complete frozen registration verifies', adapter.verify_registration(reg) == registration)
            partial = copy.deepcopy(registration); partial['source_sha256'].pop('tools/transport.py')
            reg.write_text(json.dumps(partial)); check('partial registration rejects', rejected(lambda: adapter.verify_registration(reg)))
            partial = copy.deepcopy(registration); partial['status'] = 'draft'
            reg.write_text(json.dumps(partial)); check('unfrozen registration rejects', rejected(lambda: adapter.verify_registration(reg)))
            reg.write_text(json.dumps(registration)); (root/'tools/transport.py').write_text('drift')
            check('source drift rejects', rejected(lambda: adapter.verify_registration(reg)))
            out = root/'results/probe'; out.mkdir()
            runtime = root/'runtime/probe'; runtime.mkdir(parents=True)
            oldfinal = {'type':'response_item','payload':{'type':'message','role':'assistant','channel':'final','content':[{'type':'output_text','text':'old'}]}}
            newfinal = copy.deepcopy(oldfinal); newfinal['payload']['content'][0]['text']='new'
            turns = [{'index':0,'request':'old request','final':'old','files':{'immutable':'snapshot'}}]
            (out/'native-tools.jsonl').write_text(json.dumps(oldfinal)+'\n')
            (out/'turns.json').write_text(json.dumps(turns)); (out/'manifest.json').write_text('{}')
            (runtime/'run.json').write_text(json.dumps({'status':'collected','turns':turns}))
            session = root/'session.jsonl'
            prefix_events = [
                {'type':'turn_context','payload':{'model':'gpt-6.1-sol','effort':'medium','turn_id':'first'}},
                {'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'first task'}]}},
                {'type':'response_item','payload':{'type':'message','role':'assistant','channel':'analysis','content':[{'type':'output_text','text':'analysis'}]}},
                oldfinal, {'type':'event_msg','payload':{'type':'task_complete','turn_id':'first'}}]
            prefix_bytes = ('\n'.join(json.dumps(e) for e in prefix_events)+'\n').encode()
            suffix_events = [
                {'type':'event_msg','payload':{'type':'task_started','turn_id':'new'}},
                {'type':'turn_context','payload':{'turn_id':'new','model':'gpt-6.1-sol','effort':'medium'}},
                {'type':'response_item','payload':{'type':'agent_message','author':'/root','recipient':'/root/probe',
                    'internal_chat_message_metadata_passthrough':{'turn_id':'new'},
                    'content':[{'type':'encrypted_content','encrypted_content':'gAAAAAopaque-no-decryption'}]}},
                newfinal, {'type':'event_msg','payload':{'type':'task_complete','turn_id':'new'}}]
            suffix_bytes = ('\n'.join(json.dumps(e) for e in suffix_events)+'\n').encode()
            first_sha = __import__('hashlib').sha256(prefix_bytes).hexdigest()
            first_proof_path = out/f'collection-schema-v3.6.4-{first_sha}.json'
            first_proof = {'version':adapter.VERSION,'run_id':'probe','adapter_sha256':adapter.digest(Path(adapter.__file__)),
                           'registration_sha256':adapter.digest(reg),'original_session_bytes':len(prefix_bytes),
                           'original_session_sha256':first_sha,'original_session_path':str(session.resolve()),
                           'agent_path':'/root/probe','original_native_sha256':adapter.digest(out/'native-tools.jsonl')}
            first_proof_path.write_text(json.dumps(first_proof))
            session.write_bytes(prefix_bytes+suffix_bytes)
            check('normal second turn qualifies', adapter.append_qualification('probe',session,'new request','/root/probe')['prior_turns'] == turns)
            # Same final text still constitutes a new turn with a different request.
            same_final_events = copy.deepcopy(suffix_events); same_final_events[3] = oldfinal
            same_final_suffix = ('\n'.join(json.dumps(e) for e in same_final_events)+'\n').encode()
            session.write_bytes(prefix_bytes+same_final_suffix)
            check('identical final new request qualifies append', adapter.append_qualification('probe',session,'new request','/root/probe') is not None)
            session.write_bytes(prefix_bytes+suffix_bytes)
            first_proof_path.unlink()
            check('missing prior sidecar rejects append', adapter.append_qualification('probe',session,'new request','/root/probe') is None)
            first_proof_path.write_text(json.dumps(first_proof))
            duplicate = out/('collection-schema-v3.6.4-'+'f'*64+'.json')
            duplicate.write_text(json.dumps(first_proof))
            check('duplicate matching prior sidecar rejects append', adapter.append_qualification('probe',session,'new request','/root/probe') is None)
            duplicate.unlink()
            for field in ('version','run_id','adapter_sha256','registration_sha256','original_session_bytes',
                          'original_session_sha256','original_session_path','agent_path','original_native_sha256'):
                changed = copy.deepcopy(first_proof)
                changed[field] = 1 if field == 'original_session_bytes' else 'drift'
                first_proof_path.write_text(json.dumps(changed))
                check('prior proof drift '+field, adapter.append_qualification('probe',session,'new request','/root/probe') is None)
            first_proof_path.write_text(json.dumps(first_proof))
            for index, category in ((0,'turn_context'),(1,'user'),(2,'analysis'),(4,'task_complete')):
                changed = copy.deepcopy(prefix_events)
                changed[index]['payload']['mutated'] = True
                mutated = ('\n'.join(json.dumps(e) for e in changed)+'\n').encode()
                session.write_bytes(mutated+suffix_bytes)
                check('full native prefix mutation '+category+' rejects append', adapter.append_qualification('probe',session,'new request','/root/probe') is None)
                check('full native prefix mutation '+category+' cannot bypass preservation', rejected(lambda: adapter.verify_preservation('probe',{})))
            session.write_bytes(prefix_bytes+suffix_bytes)
            identity_negatives = {}
            for category, index, field, value in [('repeat completion ID',4,'turn_id','first'),
                       ('mismatched started ID',0,'turn_id','other'),('mismatched context ID',1,'turn_id','other'),
                       ('wrong model',1,'model','other'),('wrong effort',1,'effort','low'),
                       ('wrong user recipient',2,'recipient','/root/foreign'),('wrong user author',2,'author','/foreign')]:
                changed = copy.deepcopy(suffix_events); changed[index]['payload'][field] = value
                identity_negatives[category] = changed
            for category, index in [('missing started',0),('missing context',1),('missing user',2)]:
                changed = copy.deepcopy(suffix_events); changed.pop(index); identity_negatives[category] = changed
            changed = copy.deepcopy(suffix_events)
            changed[2]['payload']['internal_chat_message_metadata_passthrough']['turn_id'] = 'first'
            identity_negatives['mismatched user turn ID'] = changed
            for category, order in [('final before context',[0,3,1,2,4]),('completion before final',[0,1,2,4,3]),
                                    ('user before context',[0,2,1,3,4]),('context before started',[1,0,2,3,4])]:
                identity_negatives[category] = [suffix_events[i] for i in order]
            repeated = copy.deepcopy(suffix_events)
            for event in repeated:
                payload = event['payload']
                if 'turn_id' in payload: payload['turn_id'] = 'first'
                if payload.get('type') == 'agent_message': payload['internal_chat_message_metadata_passthrough']['turn_id'] = 'first'
            identity_negatives['all IDs reuse first completion ID'] = repeated
            for category, changed in identity_negatives.items():
                session.write_bytes(prefix_bytes+('\n'.join(json.dumps(e) for e in changed)+'\n').encode())
                check('append identity '+category+' rejects', adapter.append_qualification('probe',session,'new request','/root/probe') is None)
            session.write_bytes(prefix_bytes+suffix_bytes)
            check('same request cannot bypass correction guard', adapter.append_qualification('probe',session,'old request','/root/probe') is None)
            session.write_text(json.dumps(oldfinal)+'\n')
            check('same terminal correction requires preservation', adapter.append_qualification('probe',session,'new request','/root/probe') is None
                  and rejected(lambda: adapter.verify_preservation('probe',{})))
            (runtime/'run.json').write_text(json.dumps({'turns':turns}))
            check('clearing collected status cannot bypass guard', rejected(lambda: adapter.verify_preservation('probe',{})))
            session.write_text(json.dumps(newfinal)+'\n')
            check('modified native prefix rejects append', adapter.append_qualification('probe',session,'new request','/root/probe') is None)
            # Execute qualified wrapper against an isolated mock collector to verify
            # that preflight and patch restoration do not touch real actor evidence.
            session.write_text(json.dumps(oldfinal)+'\n')
            preservation_files = {}
            for name in adapter.prior_files('probe'):
                saved = root/'saved'/name
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes((root/name).read_bytes())
                preservation_files[name] = {'sha256': adapter.digest(root/name), 'preserved_path': str(saved)}
            preserved = root/'preservation.json'
            proof = {'version':'software-poll-presentation-original-preservation-v3.6.4','status':'preserved','run_id':'probe',
                     'adapter_sha256': adapter.digest(Path(adapter.__file__)), 'files':preservation_files}
            preserved.write_text(json.dumps(proof))
            registered = {'prior_preservation':{'probe':{'path':str(preserved),'sha256':adapter.digest(preserved)}}}
            check('complete registered correction preservation verifies', adapter.verify_preservation('probe',registered,str(preserved))['sha256']==adapter.digest(preserved))
            check('unregistered explicit preservation rejected', rejected(lambda: adapter.verify_preservation('probe',{},str(preserved))))
            saved = Path(next(iter(preservation_files.values()))['preserved_path']); saved.write_text('drift')
            check('preserved bytes drift rejects', rejected(lambda: adapter.verify_preservation('probe',registered,str(preserved))))
            with patch.object(adapter, 'verify_registration', return_value={}), patch.object(adapter, 'verify_preservation', return_value={}), patch.object(adapter.collect, 'find_session', return_value=session), patch.object(adapter.collect, 'collect', side_effect=RuntimeError('collector exception')):
                try: adapter.qualified_collect('probe','/root/probe')
                except RuntimeError: pass
                check('qualified collector exception restores classifier', transport.wrapper_origin is original)
            first_proof_path.write_text(json.dumps(first_proof))
            session.write_bytes(prefix_bytes+suffix_bytes)
            def mock_collect(*args):
                updated=turns+[{'index':1,'request':'new request','final':'new'}]
                (out/'turns.json').write_text(json.dumps(updated))
                (out/'native-tools.jsonl').write_text(json.dumps(oldfinal)+'\n'+json.dumps(newfinal)+'\n')
                return {'run_id':'probe'}
            with patch.object(adapter, 'MANIFEST', reg), patch.object(adapter, 'verify_registration', return_value={}), patch.object(adapter.collect, 'find_session', return_value=session), patch.object(adapter.collect, 'collect', side_effect=mock_collect):
                result=adapter.qualified_collect('probe','/root/probe','new request')
                check('normal append preserves first snapshot', json.loads((out/'turns.json').read_text())[:-1]==turns)
                proof_path = Path(result['collection_adapter_proof']['path'])
                check('normal append writes versioned additive proof', proof_path.is_file())
                written = json.loads(proof_path.read_text())
                check('new proof retains full session identity bytes and hash', written['original_session_bytes']==session.stat().st_size and written['original_session_sha256']==adapter.digest(session) and written['original_session_path']==str(session.resolve()) and written['agent_path']=='/root/probe')
                with patch.object(adapter,'verify_preservation',return_value={}), patch.object(adapter.collect,'collect') as collector:
                    check('same source proof cannot overwrite or call collector',rejected(lambda:adapter.qualified_collect('probe','/root/probe','new request')) and collector.call_count==0)
            check('future initial collection requires no invented prior preservation',adapter.verify_preservation('future',{}) is None and adapter.prior_files('future')==[])

    # The current-version proof is immutable even for a repeated same source.
    # Original isolated fixtures above execute only a mocked collector.
    historical=[]
    for manifest in sorted((ROOT/'results').glob('*/manifest.json')):
        run_id=manifest.parent.name
        if not run_id.startswith(('primary-','auxiliary-')):continue
        native=manifest.parent/'native-tools.jsonl'
        if not native.exists():continue
        pins={str(p):adapter.digest(p) for p in (manifest,native)}
        events=[json.loads(line) for line in native.read_text().splitlines()]
        meta=json.loads(manifest.read_text())
        with patch.object(transport,'wrapper_origin',approved.wrapper_origin):
            old,old_polls=transport.audit_transport(events,meta,str(ROOT))
        with adapter.patched_origin():new,new_polls=transport.audit_transport(events,meta,str(ROOT))
        historical.append({'run_id':run_id,'source_sha256':pins,'native_and_manifest_unmutated':pins=={str(p):adapter.digest(p) for p in (manifest,native)},
                           'violation_evidence_unchanged':old==new,'poll_evidence_unchanged':old_polls==new_polls,'stored_manifest_audit_agreement':old==meta.get('tool_audit')})
    check('all144 historical audit and polls unchanged',len(historical)==144 and all(r['violation_evidence_unchanged'] and r['poll_evidence_unchanged'] and r['stored_manifest_audit_agreement'] for r in historical))
    check('all144 native and manifests byte unchanged',all(r['native_and_manifest_unmutated'] for r in historical))
    check('independent origin review byte unchanged',adapter.digest(review_path)==review_sha)
    import inspect
    for function in ('prior_files','verify_preservation','append_qualification','patched_origin'):
        old=inspect.getsource(getattr(approved,function)).replace('escaped-template-original-preservation-v1','software-poll-presentation-original-preservation-v3.6.4').replace('collection-schema-v3.6.2','collection-schema-v3.6.4')
        new=inspect.getsource(getattr(adapter,function))
        check('approved guard source retained '+function,old==new)

    return {'version':adapter.VERSION,'verdict':'pass' if all(c['pass'] for c in checks) else 'fail',
            'adapter_sha256':adapter.digest(Path(adapter.__file__)),'probe_source_sha256':adapter.digest(Path(__file__)),
            'review_sha256':review_sha,'checks':checks,'actual_origin_proofs':origins,'current_two_runs':current,'historical144':historical,
            'source_pins':{name:adapter.digest(ROOT/name) for name in adapter.REQUIRED_PINS},
            'allowed_outer_whitespace':'Only ASCII SPACE/TAB/LF following a complete scoped quoted host argument. CR/FF/VT/NBSP rejected.',
            'actions':{'actor_execution':False,'actual_collection':False,'grading':False,'container_mutation':False,'original_artifact_mutation':False},
            'limitations':['Only exact frozen literal wrapper syntax is supported. Unsupported JavaScript fails closed.',
                           'Presentation normalization changes only the classifier view, never source/commands/native evidence.',
                           'Collection still requires root-frozen registration and explicit registered same-artifact preservation.',
                           'Owned SID/empty stdin/output completion and controlled input provenance remain enforced by unchanged frozen code.']}


if __name__=='__main__':
    result=run()
    path=ROOT/'results/software-poll-presentation-qualification-v3.6.4.json'
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'verdict':result['verdict'],'checks':len(result['checks']),'failed':[c for c in result['checks'] if not c['pass']], 'origins':len(result['actual_origin_proofs']), 'polls':sum(r['added_owned_poll_count'] for r in result['current_two_runs']), 'historical':len(result['historical144'])}))
