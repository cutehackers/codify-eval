"""Read-only real native schema checks and isolated synthetic adapter probes."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import dialogue_control as control
import dialogue_control_probes as base
import dialogue_schema as schema

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'results/native-schema-adapter-probes-v3.6.1.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def content_view(events):
    events = copy.deepcopy(events)
    for event in events:
        payload = event.get('payload', {})
        if payload.get('type') == 'agent_message' and 'message' in payload:
            token = payload.pop('message')
            payload['content'] = ([{'type':'input_text','text':'synthetic undisclosed text'},
                {'type':'encrypted_content','encrypted_content':token}] if token.startswith('gAAAAA')
                else [{'type':'input_text','text':token}])
    return events


def synthetic_regressions(representation):
    original_evidence = control.followup_evidence
    original_write = base.Fixture.write_events
    conversion_counts = []
    def evidence(events, prefix, run, staging):
        view, converted = schema.normalize(events)
        conversion_counts.append(len(converted))
        return original_evidence(view, prefix, run, staging)
    def write(path, events):
        original_write(path, content_view(events) if representation == 'content' else events)
    with patch.object(control, 'followup_evidence', evidence), patch.object(base.Fixture,'write_events',staticmethod(write)):
        probes = base.synthetic_probes()
    return {'representation':representation, 'count':len(probes),
        'passed':sum(p['passed'] for p in probes), 'failed':[p['name'] for p in probes if not p['passed']],
        'normalization_counts':conversion_counts,'evidence_kind':'synthetic_no_actor_reexecution'}


def normalize_checks():
    results = []
    def probe(name, payload, expected=True):
        events = [{'type':'event_msg','payload':{'type':'agent_message',**payload}}]
        original = copy.deepcopy(events)
        try:
            view, audit = schema.normalize(events)
            accepted = True
            unchanged = original == events and view is not events
            truthful = all(c['plaintext_decrypted'] is False and
                c['original_payload_sha256'] == sha(json.dumps(original[c['event_index']]['payload'],sort_keys=True).encode())
                and c['token_sha256'] == sha(view[c['event_index']]['payload']['message'].encode()) for c in audit)
        except ValueError:
            accepted = False; unchanged = original == events; truthful = True; audit = []
        results.append({'name':name,'passed':accepted == expected and unchanged and truthful,
            'accepted':accepted,'input_unchanged':unchanged,'conversion_count':len(audit),
            'audit_hashes_truthful':truthful})
    probe('legacy_string', {'message':'synthetic request'})
    probe('plaintext_content', {'content':[{'type':'input_text','text':'합성 요청'}]})
    probe('encrypted_content_two_blocks', {'content':[{'type':'input_text','text':'synthetic placeholder'},
        {'type':'encrypted_content','encrypted_content':'gAAAAASYNTHETIC'}]})
    probe('malformed_content', {'content':'not a list'}, False)
    probe('duplicate_encrypted_blocks', {'content':[{'type':'encrypted_content','encrypted_content':'gAAAAAone'},
        {'type':'encrypted_content','encrypted_content':'gAAAAAtwo'}]}, False)
    probe('conflicting_legacy_and_content', {'message':'different','content':[{'type':'input_text','text':'synthetic request'}]}, False)
    probe('nonstring_encrypted_content', {'content':[{'type':'encrypted_content','encrypted_content':9}]}, False)
    probe('unknown_content_block', {'content':[{'type':'output_text','text':'synthetic request'}]}, False)
    return results


def restoration_checks():
    results=[]
    for kind in ('grade_exception','typed_attestation_exception','registration_missing','registered_source_drift',
                 'empty_source_pins','partial_source_pins','wrong_core_version','core_grader_drift','unfrozen_registration'):
        with tempfile.TemporaryDirectory(prefix='schema-probe-') as temp:
            manifest=Path(temp)/'registration.json'
            isolated=Path(temp)/'synthetic-root'
            for name in schema.REQUIRED_PINS:
                file=isolated/name; file.parent.mkdir(parents=True,exist_ok=True)
                file.write_text('synthetic pin '+name)
            core={'core_version':'v3.6','freeze_revision':2,
                  'grader_hashes':{'tools/dialogue_control.py':schema.digest(isolated/'tools/dialogue_control.py')}}
            if kind=='wrong_core_version':
                core['core_version']='synthetic-wrong-version'
            if kind=='core_grader_drift':
                core['grader_hashes']['tools/dialogue_control.py']='wrong synthetic core pin'
            base.dump(isolated/'results/frozen-core-v3.6.json',core)
            registration={'version':schema.VERSION,'status':'frozen',
                'source_sha256':{name:schema.digest(isolated/name) for name in schema.REQUIRED_PINS}}
            if kind == 'registered_source_drift':
                registration['source_sha256']['tools/dialogue_schema.py']='wrong synthetic pin'
            if kind=='empty_source_pins':
                registration['source_sha256']={}
            if kind=='partial_source_pins':
                registration['source_sha256'].pop('tools/finalize.py')
            if kind=='unfrozen_registration':
                registration['status']='pending'
            if kind != 'registration_missing':
                base.dump(manifest,registration)
            calls=[]
            def original_evidence(events, *_):
                assert events[0]['payload']['message']=='synthetic request'
                return {}
            def original_attest(identifier):
                control.followup_evidence([{'payload':{'type':'agent_message','content':[{'type':'input_text','text':'synthetic request'}]}}],b'',{}, {})
                raise control.ControlFault('evaluation_error','synthetic_fault','synthetic failure')
            def fake_grade(identifier):
                calls.append(identifier)
                if kind == 'typed_attestation_exception':
                    return control.attest(identifier)
                raise RuntimeError('synthetic grade exception')
            with patch.object(schema,'ROOT',isolated), patch.object(schema,'MANIFEST',manifest), patch.object(control,'followup_evidence',original_evidence), patch.object(control,'attest',original_attest), patch.object(schema.grade,'grade',fake_grade):
                error_audit=None
                try:
                    schema.qualified_grade('synthetic-only')
                    rejected=False
                except Exception as error:
                    rejected=True
                    error_audit=getattr(error,'audit',None)
                restored=control.followup_evidence is original_evidence and control.attest is original_attest
                gate=len(calls)==1 if kind in {'grade_exception','typed_attestation_exception'} else not calls
                truthful=True
                if kind == 'typed_attestation_exception':
                    proof=error_audit.get('native_schema_adapter',{}) if error_audit else {}
                    truthful=len(proof.get('normalized_fields',[]))==1 and not proof['original_native_records_mutated'] and not proof['actor_reexecuted'] and not proof['input_or_behavior_criteria_changed']
                results.append({'name':kind,'passed':rejected and restored and gate and truthful,
                    'functions_restored':restored,'registration_gate_verified':gate,'audit_truthful':truthful,
                    'evidence_kind':'isolated_mock_grade_no_actual_grade'})
    return results


def actual_native_check():
    run_id='auxiliary-S03-C0-1'
    directory=ROOT/'runtime'/run_id
    run=control.read(directory/'run.json')
    staging=control.read(directory/'control-input-stage.json')
    path=control.find_session(run['agent_path'])
    raw=path.read_bytes()
    events=[json.loads(line) for line in raw.decode().splitlines()]
    view, conversions=schema.normalize(events)
    prefix=raw[:staging['first_actor_source_prefix_bytes']]
    proof=control.followup_evidence(view,prefix,run,staging)
    return {'passed':path.read_bytes()==raw and events!=view and bool(conversions),
        'evidence_kind':'real_native_read_only_followup_chain_qualification',
        'run_id':run_id,'original_native_sha256':sha(raw),'original_native_records_mutated':False,
        'conversion_count':len(conversions),'normalized_fields':conversions,
        'qualified_parent_child_chain':proof,'actual_grade_executed':False,
        'plaintext_decrypted':False,'actor_reexecuted':False,
        'limits':['Read-only original frozen followup_evidence invoked on deep-copied normalized view.',
                  'No behavioral grade or acceptance claim. No native plaintext decrypted.']}


def main():
    sources={name:schema.digest(ROOT/name) for name in sorted(schema.REQUIRED_PINS|{
        'tools/dialogue_control_probes.py','tools/transport.py'})}
    regressions=[synthetic_regressions(name) for name in ('legacy','content')]
    checks=normalize_checks()+restoration_checks()
    try:
        actual=actual_native_check()
    except Exception as error:
        actual={'passed':False,'evidence_kind':'real_native_read_only_followup_chain_qualification',
                'error_type':type(error).__name__,'error':str(error),'actual_grade_executed':False}
    unchanged=all(schema.digest(ROOT/name)==digest for name,digest in sources.items())
    report={'version':'v3.6.1','adapter_version':schema.VERSION,'source_sha256':sources,
        'probe_sha256':schema.digest(Path(__file__)),'sources_unchanged':unchanged,
        'scope':'Read-only native representation and isolated adapter regression checks. No actor dispatch, decryption, original grading or Docker execution.',
        'synthetic_regressions':regressions,'adapter_checks':checks,'real_native':actual,
        'passed':unchanged and all(p['passed']==p['count'] for p in regressions) and all(p['passed'] for p in checks) and actual['passed']}
    base.dump(OUTPUT,report)
    print(json.dumps({'passed':report['passed'],'synthetic_regressions':[(p['representation'],p['passed'],p['count'],p['failed']) for p in regressions],
        'adapter_checks_passed':sum(p['passed'] for p in checks),'adapter_checks_count':len(checks),
        'real_native_passed':actual['passed'],'output':str(OUTPUT)}))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
