"""Read-only native audit and isolated collection compatibility probes."""
import copy
import json
from pathlib import Path
import tempfile
import re
from unittest.mock import patch
import collect_schema as adapter
import transport
from prepare import ROOT


def run():
    checks = []
    def check(name, condition):
        checks.append({'name': name, 'pass': bool(condition)})
    run_id = 'software-W01-A-3'
    native = ROOT / 'results' / run_id / 'native-tools.jsonl'
    before = adapter.digest(native)
    events = [json.loads(line) for line in native.read_text().splitlines()]
    metadata = json.loads((ROOT / 'results' / run_id / 'manifest.json').read_text())
    codes = {e['payload'].get('call_id'): e['payload'].get('input', e['payload'].get('arguments', ''))
             for e in events if e['payload'].get('type') in {'custom_tool_call', 'function_call'}}
    targets = {'call_NANSWYfPBHssj26YP7NXYeNq': 4, 'call_0EXMTM7soZ32W6hrfMwEOtr1': 1}
    origins = []
    commands_path = ROOT / 'runtime' / run_id / 'commands.jsonl'
    commands_before = adapter.digest(commands_path)
    commands = [json.loads(line) for line in commands_path.read_text().splitlines()]
    for call, count in targets.items():
        code = codes[call]
        original = code[:]
        view, converted = adapter.classifier_view(code)
        check(call + ': expected conversion', converted == count and code == original)
        check(call + ': old rejects/new accepts', not adapter.ORIGINAL_WRAPPER_ORIGIN(code, str(ROOT), run_id)
              and adapter.wrapper_origin(code, str(ROOT), run_id))
        body = adapter.TEMPLATE.fullmatch(code.strip()).group(2)
        # Bounded lexical comparison only; never evaluate source JavaScript.
        decoded = re.sub(r'\\(.)', lambda m: {'n':'\n','r':'\r','t':'\t','b':'\b','f':'\f','v':'\v'}.get(m.group(1), m.group(1)), body, flags=re.S)
        matched_commands = [c for c in commands if c['command'] == decoded]
        check(call + ': actual command record agrees', len(matched_commands) == 1)
        origins.append({'call_id': call, 'escaped_literal_count': converted,
                        'source_code_sha256': __import__('hashlib').sha256(code.encode()).hexdigest(),
                        'actual_command_sha256': __import__('hashlib').sha256(decoded.encode()).hexdigest(),
                        'command_record_agreement': len(matched_commands) == 1})
    exemplar = codes[next(iter(targets))]
    match = adapter.TEMPLATE.fullmatch(exemplar.strip())
    def shape(body, suffix=None):
        value = exemplar.strip()
        return value[:match.start(2)] + body + value[match.end(2):match.start(3)] + (suffix if suffix is not None else match.group(3))
    for slashes in range(7):
        code = shape('x' + '\\' * slashes + '${name}')
        view, count = adapter.classifier_view(code)
        check(f'backslash parity {slashes}', adapter.wrapper_origin(code, str(ROOT), run_id) == bool(slashes % 2)
              and count == int(bool(slashes % 2)))
        if slashes % 2:
            check(f'paired slash retention {slashes}', ('x' + '\\' * (slashes - 1) + r'\u0024{name}') in view)
    negatives = {
        'actual interpolation': shape('${name}'),
        'mixed escaped actual': shape(r'\${ok} ${bad}'),
        'extra statement before': 'const x=1;' + exemplar,
        'extra statement after': exemplar + 'text(await tools.exec_command({cmd:"bad"}));',
        'unknown suffix tool': shape(r'\${ok}', match.group(3).replace('tools.exec_command', 'tools.other')),
        'other run': exemplar.replace('--run ' + run_id, '--run foreign'),
        'suffix escaped interpolation': shape(r'\${ok}', match.group(3).replace('python3 ', r'\${bad}python3 ')),
        'unclosed template': exemplar.replace('const cmd = `', 'const cmd = "', 1),
    }
    for name, code in negatives.items():
        check(name, not adapter.wrapper_origin(code, str(ROOT), run_id))
    normal = shape('plain literal')
    check('legacy successful view unchanged', adapter.ORIGINAL_WRAPPER_ORIGIN(normal, str(ROOT), run_id)
          and adapter.classifier_view(normal) == (normal, 0) and adapter.wrapper_origin(normal, str(ROOT), run_id))
    original = transport.wrapper_origin
    try:
        with adapter.patched_origin():
            check('runtime patch active', transport.wrapper_origin is adapter.wrapper_origin)
            raise RuntimeError('probe exception')
    except RuntimeError:
        pass
    check('runtime patch restored on exception', transport.wrapper_origin is original)
    with adapter.patched_origin():
        pass
    check('runtime patch restored normally', transport.wrapper_origin is original)
    old_audit, old_polls = transport.audit_transport(events, metadata, str(ROOT))
    with adapter.patched_origin():
        audit, polls = transport.audit_transport(events, metadata, str(ROOT))
    added = [p for p in polls if p not in old_polls]
    check('W01 six exact false violations resolved', len(old_audit) == 6 and not audit and len(added) == 6
          and {p['session_id'] for p in added} == {91998, 2541}
          and {p['origin_call_id'] for p in added} == set(targets))
    check('W01 source and command records unchanged', adapter.digest(native) == before and adapter.digest(commands_path) == commands_before)
    chain = []
    for sid in (91998, 2541):
        related = [p for p in added if p['session_id'] == sid]
        outputs = []
        for e in events:
            p = e['payload']
            if p.get('call_id') in {x['poll_call_id'] for x in related} and p.get('type') in {'custom_tool_call_output', 'function_call_output'}:
                outputs.extend(transport.result_objects(p))
        completed = any(type(o.get('exit_code')) is int for o in outputs)
        check(f'W01 SID {sid} finishes with original native output', completed)
        chain.append({'session_id': sid, 'polls': related, 'completion_exit_codes': [o['exit_code'] for o in outputs if 'exit_code' in o]})
    # The unchanged auditor enforces foreign ownership, empty chars and result chain.
    foreign = copy.deepcopy(events)
    for e in foreign:
        p = e['payload']
        if p.get('call_id') == added[0]['poll_call_id'] and p.get('type') in {'custom_tool_call', 'function_call'}:
            key = 'input' if 'input' in p else 'arguments'
            p[key] = p[key].replace(str(added[0]['session_id']), '987654321')
    with adapter.patched_origin():
        foreign_audit, _ = transport.audit_transport(foreign, metadata, str(ROOT))
    check('foreign SID remains violation', bool(foreign_audit))
    for name, code in [('empty unquoted', 'text(await tools.write_stdin({session_id:4,chars:"",yield_time_ms:0,max_output_tokens:3}));'),
                       ('empty quoted', 'text(await tools.write_stdin({"session_id":4,"chars":"","yield_time_ms":0,"max_output_tokens":3}));')]:
        check(name, transport.poll_options(code) is not None)
    check('nonempty stdin rejected', transport.poll_options('text(await tools.write_stdin({session_id:4,chars:"x"}));') is None)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for name in adapter.REQUIRED_PINS:
            file = root / name; file.parent.mkdir(parents=True, exist_ok=True); file.write_text('{}')
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
            first_proof_path = out/f'collection-schema-v3.6.2-{first_sha}.json'
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
            duplicate = out/('collection-schema-v3.6.2-'+'f'*64+'.json')
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
            proof = {'version':'escaped-template-original-preservation-v1','status':'preserved','run_id':'probe',
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
    actual_appends = []
    for runtime_path in sorted((ROOT/'runtime').glob('auxiliary-S03-*/run.json')):
        run_metadata = json.loads(runtime_path.read_text())
        stage_path = runtime_path.parent/'control-input-stage.json'
        if len(run_metadata.get('turns', [])) != 2 or not stage_path.exists():
            continue
        stage = json.loads(stage_path.read_text())
        actor_source = adapter.collect.find_session(run_metadata['agent_path'])
        actor_sha = adapter.digest(actor_source)
        raw = actor_source.read_bytes()
        size = stage['first_actor_source_prefix_bytes']
        first_raw = raw[:size]
        first_sha = __import__('hashlib').sha256(first_raw).hexdigest()
        first_records = []
        for line in first_raw.decode().splitlines():
            event = json.loads(line); payload = event.get('payload', {})
            typ = payload.get('type')
            if event.get('type') == 'response_item' and (typ in {'function_call','function_call_output','custom_tool_call','custom_tool_call_output'}
                    or (typ == 'message' and payload.get('role') == 'assistant' and (payload.get('channel') == 'final' or payload.get('phase') == 'final_answer')
                        and any(c.get('type') == 'output_text' and c.get('text') for c in payload.get('content', [])))):
                first_records.append(event)
        identifier = runtime_path.parent.name
        with tempfile.TemporaryDirectory() as temporary:
            probe_root = Path(temporary)
            out = probe_root/'results'/identifier; out.mkdir(parents=True)
            run = probe_root/'runtime'/identifier; run.mkdir(parents=True)
            first_turns = run_metadata['turns'][:1]
            (out/'native-tools.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in first_records))
            (out/'turns.json').write_text(json.dumps(first_turns))
            (run/'run.json').write_text(json.dumps({'turns':first_turns}))
            reg = probe_root/'registration-view.json'; reg.write_text('{}')
            proof = {'version':adapter.VERSION,'run_id':identifier,'adapter_sha256':adapter.digest(Path(adapter.__file__)),
                     'registration_sha256':adapter.digest(reg),'original_session_bytes':size,'original_session_sha256':first_sha,
                     'original_session_path':str(actor_source.resolve()),'agent_path':run_metadata['agent_path'],
                     'original_native_sha256':adapter.digest(out/'native-tools.jsonl')}
            (out/f'collection-schema-v3.6.2-{first_sha}.json').write_text(json.dumps(proof))
            with patch.object(adapter,'ROOT',probe_root), patch.object(adapter,'MANIFEST',reg):
                qualified = adapter.append_qualification(identifier,actor_source,run_metadata['turns'][1]['request'],run_metadata['agent_path'])
        source_unmutated = adapter.digest(actor_source)==actor_sha
        check(identifier+': actual completed two-turn native append identity', qualified is not None and source_unmutated and first_sha==stage['first_actor_source_sha256'])
        actual_appends.append({'run_id':identifier,'source_sha256':actor_sha,'first_prefix_bytes':size,
                               'first_prefix_sha256':first_sha,'source_unmutated':source_unmutated,
                               'append_turn_id':qualified['append_turn_id'] if qualified else None,
                               'identity_qualified':qualified is not None,'validation_only_no_collection':True,
                               'temporary_prior_proof_constructed_for_read_only_structure_probe':True})
    check('six actual S03 two-turn structures inspected read-only',len(actual_appends)==6)
    cohort = []
    for manifest in sorted((ROOT/'results').glob('*/manifest.json')):
        identifier = manifest.parent.name
        if not identifier.startswith(('primary-', 'auxiliary-')):
            continue
        raw = manifest.parent/'native-tools.jsonl'
        if not raw.exists(): continue
        initial = adapter.digest(raw)
        records = [json.loads(line) for line in raw.read_text().splitlines()]
        meta = json.loads(manifest.read_text())
        legacy, legacy_polls = transport.audit_transport(records, meta, str(ROOT))
        with adapter.patched_origin():
            compatible, compatible_polls = transport.audit_transport(records, meta, str(ROOT))
        cohort.append({'run_id':identifier,'native_sha256':initial,'native_unmutated':initial==adapter.digest(raw),
                       'legacy_violation_count':len(legacy),'compatible_violation_count':len(compatible),
                       'legacy_violations_unchanged':legacy==compatible,'poll_evidence_unchanged':legacy_polls==compatible_polls,
                       'manifest_legacy_audit_agreement':legacy==meta.get('tool_audit')})
    check('all 144 current completed cohort native records unmutated', len(cohort)==144 and all(x['native_unmutated'] for x in cohort))
    check('all 144 legacy violations and polls unchanged', all(x['legacy_violations_unchanged'] and x['poll_evidence_unchanged'] for x in cohort))
    return {'version':adapter.VERSION,'verdict':'pass' if all(c['pass'] for c in checks) else 'fail',
            'adapter_sha256':adapter.digest(Path(adapter.__file__)),'probe_source_sha256':adapter.digest(Path(__file__)),
            'checks':checks,'W01':{'native_sha256':before,'original_violation_count':len(old_audit),
              'compatible_violation_count':len(audit),'origins':origins,'owned_poll_chains':chain},
            'actual_S03_append_identity':actual_appends,'current_final_cohort':cohort,'differences':[x for x in cohort if not x['legacy_violations_unchanged'] or not x['manifest_legacy_audit_agreement']],
            'limitations':['No native recollection, actor execution, grading, Docker or archive mutation.',
                           'Classifier supports only the existing frozen wrapper syntax with escaped literal template dollars.',
                           'Native event provenance checked by unchanged frozen transport auditor, not executed JavaScript.',
                           'Append identity checks native started/context/incoming metadata/final/completion. It does not decrypt incoming content or replace frozen control attestation of coordinator dispatch, message token, staging or receipt.']}


if __name__ == '__main__':
    result=run()
    destination=ROOT/'results/escaped-template-collection-probes-v3.6.2.json'
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'verdict':result['verdict'],'checks':len(result['checks']), 'failed':[x for x in result['checks'] if not x['pass']], 'cohort':len(result['current_final_cohort']), 'differences':len(result['differences'])}))
