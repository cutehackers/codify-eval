"""Read-only raw-template qualification and replay of all frozen v364 guards."""
import copy
import inspect
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import collect_schema_v366 as adapter
import collect_schema_v364 as prior
import collect_schema_v364_probes as old_probes
import transport
from prepare import ROOT

SESSION = Path('/Users/junhyounglee/.codex/sessions/2026/10/10/rollout-2026-10-10T15-42-08-01a1248c-2abe-72e1-8be5-3a0b4691b192.jsonl')
SESSION_SHA = '82144ee8687c6d575668b883a9b69872fcba4294b663e74a785bb7aec639d34d'


def legacy_guards():
    """Resolve frozen original artifact names to immutable registered archives."""
    mapping = {}; proofs = []
    for run in ('software-W01-A-3', 'software-W02-B-1'):
        proof_path = ROOT / f'results/software-poll-prior-{run}-final-v3.6.4.json'
        proof = json.loads(proof_path.read_text()); proofs.append(str(proof_path))
        for name, record in proof['files'].items():
            target = Path(record['preserved_path'])
            if adapter.digest(target) != record['sha256']:
                raise ValueError('Frozen archive drift: ' + str(target))
            mapping[str(ROOT / name)] = target
    read_bytes = Path.read_bytes; read_text = Path.read_text; exists = Path.exists
    def redirected_bytes(path): return read_bytes(mapping.get(str(path), path))
    def redirected_text(path, *args, **kwargs): return read_text(mapping.get(str(path), path), *args, **kwargs)
    def redirected_exists(path): return exists(mapping.get(str(path), path))
    with patch.object(Path, 'read_bytes', redirected_bytes), patch.object(Path, 'read_text', redirected_text), patch.object(Path, 'exists', redirected_exists):
        result = old_probes.run()
    return result, {'proofs': proofs, 'read_only_archived_path_mapping': {k: str(v) for k, v in mapping.items()}}


def public_events(path):
    events = []
    for line in path.open():
        event = json.loads(line); payload = event.get('payload', {})
        if event.get('type') == 'response_item' and payload.get('type') in {'function_call', 'custom_tool_call', 'function_call_output', 'custom_tool_call_output'}:
            events.append(event)
    return events


def run():
    baseline, archive = legacy_guards()
    checks = list(baseline['checks'])
    def check(name, value): checks.append({'name': name, 'pass': bool(value)})
    check('all230 frozen v364 guards execute unchanged against pinned archives', len(baseline['checks']) == 230 and baseline['verdict'] == 'pass')
    check('native terminal session exact source pin', adapter.digest(SESSION) == SESSION_SHA)
    events = public_events(SESSION)
    run_id = 'software-W01-A-2'
    artifacts = [SESSION, ROOT/f'results/{run_id}/native-tools.jsonl', ROOT/f'results/{run_id}/manifest.json', ROOT/f' runtime/{run_id}/commands.jsonl'.strip()]
    before = {str(p): adapter.digest(p) for p in artifacts}
    metadata = json.loads((ROOT/f'results/{run_id}/manifest.json').read_text())
    commands = [json.loads(l) for l in (ROOT/f'runtime/{run_id}/commands.jsonl').read_text().splitlines()]
    with prior.patched_origin(): old_bad, old_polls = adapter.ORIGINAL_AUDIT(events, metadata, str(ROOT))
    with adapter.patched_origin(): new_bad, new_polls = adapter.audit_transport(events, metadata, str(ROOT))
    failed_attempts = []
    _, origins = adapter.classifier_events(events, metadata, str(ROOT), failed_attempts)
    proofs = []
    for origin in origins:
        command = origin['raw_literal']; argv = origin['exact_six_scoped_host_argv']
        records = [record for record in commands if record['command'] == command]
        check(origin['call_id'] + ': scoped exact six argv and native command ledger agree', len(argv) == 6 and argv[-1] == command and len(records) == 1)
        polls = [p for p in new_polls if p['origin_call_id'] == origin['call_id']]
        results = []
        calls = {origin['call_id']} | {p['poll_call_id'] for p in polls}
        for event in events:
            p = event['payload']
            if p.get('call_id') in calls and p.get('type') in {'custom_tool_call_output', 'function_call_output'}:
                results.extend(transport.result_objects(p))
        terminals = [r for r in results if type(r.get('exit_code')) is int]
        if polls:
            terminal_records = []
            for r in terminals:
                try: terminal_records.append(json.loads(r['output']))
                except ValueError: pass
            check(origin['call_id'] + ': actual owned empty polls terminate in exact ledger record', len(terminals) == 1 and terminal_records == records and all(p['empty_stdin'] for p in polls))
        proofs.append({**origin, 'owned_poll_proofs': polls, 'terminal_host_results': terminals, 'ledger_record': records[0] if len(records) == 1 else None})
    first = next(p for p in proofs if p['call_id'] == 'call_52TaNnXC2CVhEQKZq9l24fQi')
    check('first actual exact prefix store scopes real SID99618', first['prefix_store_in_call'] and len(first['owned_poll_proofs']) == 2 and all(p['session_id'] == 99618 for p in first['owned_poll_proofs']))
    check('first actual raw body is identical to correctly serialized JSON literal command', first['raw_literal'] == first['exact_six_scoped_host_argv'][-1] and first['ledger_record']['command'] == first['raw_literal'])
    # General static literal semantics, not JavaScript execution.
    run = 'probe'; prefix = f'python3 {ROOT}/tools/agent_io.py --run {run} --cmd '
    def raw_code(body, store=True):
        setting = 'store("prefix",' + json.dumps(prefix) + ');' if store else ''
        return 'const cmd=String.raw`' + body + '`;' + setting + 'text(await tools.exec_command({cmd:load("prefix")+"\'"+cmd.replace(/\'/g,"\'\\\\\'\'")+"\'"}));'
    for body in ('plain', "a'postrophe", '\\n\\t\\u0024', '한국어\nnext', '\\${literal}', '\\\\n', '\\`', 'a\r\nb\rc', '', '\\\ncontinued'):
        code = raw_code(body); view, proof, _ = adapter.raw_template_view(code, str(ROOT), run)
        expected = body.replace('\r\n', '\n').replace('\r', '\n')
        check('raw semantics preserve ' + repr(body), proof is not None and proof['raw_literal'] == expected and adapter.ORIGINAL_WRAPPER_ORIGIN(view, str(ROOT), run))
    positive = raw_code('plain')
    for name, code, saved in [
        ('interpolation', raw_code('${value}'), None),
        ('even escape interpolation', raw_code('\\\\${value}'), None),
        ('unescaped backtick', raw_code('a`b'), None),
        ('unknown saved prefix', raw_code('plain', False), None),
        ('foreign saved prefix', raw_code('plain', False), prefix.replace('--run probe', '--run other')),
        ('foreign stored prefix', positive.replace('--run probe', '--run other'), None),
        ('dynamic stored prefix', positive.replace(json.dumps(prefix), 'value'), None),
        ('additional tool', positive + 'text(await tools.apply_patch("x"));', None),
        ('additional expression', positive + 'store("prefix", "other");', None),
        ('arbitrary tagged template', positive.replace('String.raw', 'other.raw'), None),
        ('dynamic replacement', positive.replace('cmd.replace', 'cmd.other'), None),
        ('alternate prefix key', positive.replace('"prefix"', '"other"'), None),
    ]:
        check(name + ' fails closed', adapter.raw_template_view(code, str(ROOT), run, saved)[1] is None)
    def call(cid, code): return {'type':'response_item','payload':{'type':'custom_tool_call','name':'exec','call_id':cid,'input':code}}
    def output(cid, value): return {'type':'response_item','payload':{'type':'custom_tool_call_output','call_id':cid,'output':json.dumps(value)}}
    synthetic = [call('origin', positive), output('origin', {'session_id':42,'output':'','wall_time_seconds':1}),
                 call('poll', 'text(await tools.write_stdin({"session_id":42,"chars":""}));'), output('poll', {'exit_code':0,'output':'done','wall_time_seconds':1})]
    meta = {'run_id':run}
    with adapter.patched_origin():
        bad, polls = adapter.audit_transport(synthetic, meta, str(ROOT))
        check('quoted poll keys and owned empty input still qualify', not bad and len(polls) == 1)
        for name, alter in [('foreign SID',lambda es: es[2]['payload'].update(input='text(await tools.write_stdin({session_id:43,chars:""}));')),
                             ('nonempty input',lambda es: es[2]['payload'].update(input='text(await tools.write_stdin({session_id:42,chars:"x"}));')),
                             ('wrong result SID',lambda es: es[3]['payload'].update(output=json.dumps({'session_id':43,'output':'','wall_time_seconds':1}))),
                             ('missing origin output',lambda es: es.pop(1)),
                             ('extra tool',lambda es: es[0]['payload'].update(input=positive+'text(await tools.apply_patch("x"));')),
                             ('poll after completion',lambda es: es.append(call('late', synthetic[2]['payload']['input']))),
                             ('missing result provenance',lambda es: es[3]['payload'].update(output='{}'))]:
            mutated = copy.deepcopy(synthetic); alter(mutated)
            check(name + ' transport remains violation', bool(adapter.audit_transport(mutated, meta, str(ROOT))[0]))
    # Exact run-local state only. Unknown store/tool access invalidates it.
    sequence = [call('seed',positive),output('seed', {'session_id':42,'output':'','wall_time_seconds':1}),call('overwrite','store("prefix", "foreign");'),call('later',raw_code('plain',False))]
    check('prefix overwrite invalidates subsequent load', len(adapter.classifier_events(sequence,meta,str(ROOT))[1]) == 1)
    for name, middle in [('unknown dynamic store', call('unknown','globalThis["store"]("prefix", "foreign");')),
                         ('missing origin output', None),
                         ('failed origin output', output('seed', {'error':'failure'}))]:
        sequence = [call('seed', positive)]
        if middle is not None: sequence.append(middle)
        sequence.append(call('later',raw_code('plain',False)))
        check(name + ' cannot create or retain saved prefix', len(adapter.classifier_events(sequence,meta,str(ROOT))[1]) == 1)
    check('prefix state resets per independent audit', not adapter.classifier_events([call('later',raw_code('plain',False))],meta,str(ROOT))[1])
    preserved_qualification = ROOT/'results/revisions/raw-template-v3.6.4/initial-conservative-adapter/software-raw-template-qualification-v3.6.6.json'
    if not preserved_qualification.exists():
        candidates = list(preserved_qualification.parent.glob('*qualification*'))
        if len(candidates) != 1: raise ValueError('Initial qualification archive missing')
        preserved_qualification = candidates[0]
    initial = json.loads(preserved_qualification.read_text())
    check('one proven failed compile attempt owns no SID and executes no command', len(failed_attempts) == 1 and failed_attempts[0]['command_executed'] is False and failed_attempts[0]['owned_session_id'] is None and failed_attempts[0]['prefix_state_preserved'])
    failed_call = next(e for e in events if e['payload'].get('call_id') == failed_attempts[0]['call_id'] and e['payload'].get('type') == 'custom_tool_call')
    failed_output = next(e for e in events if e['payload'].get('call_id') == failed_attempts[0]['call_id'] and e['payload'].get('type') == 'custom_tool_call_output')
    rejected_code = failed_call['payload']['input']
    normal_seed = output('seed', {'session_id':42,'output':'','wall_time_seconds':1})
    def failure_sequence(code=rejected_code, failure=None):
        return [call('seed',positive), normal_seed, call('failure',code),
                {'type':'response_item','payload':{'type':'custom_tool_call_output','call_id':'failure','output':copy.deepcopy(failed_output['payload']['output'])}} if failure is None else output('failure',failure),
                call('later',raw_code('plain',False))]
    def exception_count(seq):
        proof = []; adapter.classifier_events(seq,meta,str(ROOT),proof); return len(proof)
    check('general parse-only exception preserves scoped state', exception_count(failure_sequence()) == 1)
    for name, seq in [
        ('SyntaxError text alone',failure_sequence(failure='SyntaxError: Unexpected identifier')),
        ('result object cannot authenticate compile failure',failure_sequence(failure={'exit_code':1,'output':'SyntaxError: x','wall_time_seconds':0})),
        ('valid source runtime SyntaxError',failure_sequence(code=positive + 'throw new SyntaxError("x");')),
        ('valid admitted raw source cannot gain compile exception',failure_sequence(code=raw_code('plain',False))),
        ('extra tool vocabulary',failure_sequence(code=rejected_code.replace('const cmd', 'tools.apply_patch("x");const cmd',1))),
        ('prefix write',failure_sequence(code=rejected_code.replace('const cmd', 'store("prefix","foreign");const cmd',1))),
        ('foreign prefix load',failure_sequence(code=rejected_code.replace('load("prefix")','load("other")'))),
    ]: check(name + ' refuses compile exception', exception_count(seq) == 0)
    interrupted = failure_sequence(); interrupted.insert(3,call('intervening','text(1);'))
    check('intervening executed call refuses compile exception', exception_count(interrupted) == 0)
    unknown_output = failure_sequence(); unknown_output.insert(3,output('unknown',{}))
    check('unknown intervening output refuses compile exception', exception_count(unknown_output) == 0)
    missing = failure_sequence(); missing.pop(3)
    unresolved = failure_sequence(); unresolved.insert(2,call('unresolved',raw_code('plain',False)))
    check('unresolved prior tool refuses compile exception', exception_count(unresolved) == 0)
    bracket_tool = failure_sequence(code=rejected_code.replace('const cmd','tools["apply_patch"]("x");const cmd',1))
    check('bracket additional tool refuses compile exception', exception_count(bracket_tool) == 0)
    check('missing paired failure refuses compile exception', exception_count(missing) == 0)
    duplicate = failure_sequence(); duplicate.insert(3,copy.deepcopy(duplicate[2]))
    check('duplicate call identity refuses compile exception', exception_count(duplicate) == 0)
    check('runtime parser exact absolute path binary and version verify', adapter.verify_parser_runtime() == adapter.PARSER_RUNTIME)
    changed = dict(adapter.PARSER_RUNTIME); changed['sha256'] = '0'*64
    with patch.object(adapter,'PARSER_RUNTIME',changed):
        try: adapter.verify_parser_runtime(); rejected=False
        except ValueError: rejected=True
        check('parser binary drift fails closed',rejected)
    wrong_registration = {'version':adapter.VERSION,'status':'frozen','actor_reexecution_allowed':False,'source_sha256':{}}
    with tempfile.TemporaryDirectory() as temp:
        reg=Path(temp)/'registration.json';reg.write_text(json.dumps(wrong_registration))
        try: adapter.verify_registration(reg); rejected=False
        except ValueError: rejected=True
        check('missing parser preregistration fails closed', rejected)
    actual_c0 = public_events(ROOT/'results/software-W01-C0-3/native-tools.jsonl')
    c0meta = json.loads((ROOT/'results/software-W01-C0-3/manifest.json').read_text())
    with prior.patched_origin(): c0_old,_ = adapter.ORIGINAL_AUDIT(actual_c0,c0meta,str(ROOT))
    with adapter.patched_origin(): c0_new,_ = adapter.audit_transport(actual_c0,c0meta,str(ROOT))
    check('actual W01-C0-3 two send_message violations remain unchanged', c0_old == c0_new and len(c0_new) == 2 and all('send_message' in v['tool'] for v in c0_new))
    check('all source and actual artifacts remain byte unchanged', before == {str(p):adapter.digest(p) for p in artifacts})
    check('frozen guard implementation retained with version rename', all(inspect.getsource(getattr(adapter,name)) == inspect.getsource(getattr(prior,name)).replace('software-poll-presentation','software-raw-template-collection').replace('v3.6.4','v3.6.6').replace('software-raw-template-collection-original-preservation-v3.6.6','raw-template-original-preservation-v3.6.6') for name in ('prior_files','verify_preservation','append_qualification')))
    check('all289 initial conservative qualification checks retained', len(initial['checks']) == 289 and {c['name'] for c in initial['checks']} <= {c['name'] for c in checks})
    return {'version':adapter.VERSION,'verdict':'pass' if all(c['pass'] for c in checks) else 'fail','checks':checks,
            'adapter_sha256':adapter.digest(Path(adapter.__file__)),'probe_source_sha256':adapter.digest(Path(__file__)),
            'prior230_guard_replay':archive,'source_pins':{n:adapter.digest(ROOT/n) for n in adapter.REQUIRED_PINS if (ROOT/n).is_file() and n != 'results/software-raw-template-qualification-v3.6.6.json'},
            'required_frozen_pins':sorted(adapter.REQUIRED_PINS),'missing_preregistration_pins':[n for n in sorted(adapter.REQUIRED_PINS) if not (ROOT/n).exists()],
            'native_source':{'path':str(SESSION),'sha256':SESSION_SHA},'actual_origin_proofs':proofs,'unsuccessful_tool_attempts':failed_attempts, 'parser_runtime':dict(adapter.PARSER_RUNTIME),
            'initial_conservative_qualification_sha256':adapter.digest(preserved_qualification),
            'actual_W01_C0_3_unchanged_violations':c0_new,
            'actual_original_violations':old_bad,'actual_remaining_violations':new_bad,'qualified_owned_polls':new_polls,
            'actual_original_poll_count':len(old_polls),'actual_qualified_poll_count':len(new_polls),
            'actions':{'actor_execution':False,'actual_collection':False,'grading':False,'original_artifact_mutation':False},
            'limitations':['Only authenticated independently parser-rejected scoped raw attempts receive the nonexecution exception.', 'Unknown prefix mutations invalidate later loads until a new exact scoped store.', 'No registration is created by this probe.']}


if __name__ == '__main__':
    result = run()
    (ROOT/'results/software-raw-template-qualification-v3.6.6.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'verdict':result['verdict'],'checks':len(result['checks']),'failed':[c for c in result['checks'] if not c['pass']], 'origins':len(result['actual_origin_proofs']), 'owned_polls':result['actual_qualified_poll_count'],'remaining_violations':len(result['actual_remaining_violations'])}))
