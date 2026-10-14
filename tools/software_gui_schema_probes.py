"""Bounded fake-interface probes and isolated unchanged Linux qualification."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch
import software_gui_schema as adapter
import software_fixtures as w01
import w02_fixtures as w02
from prepare import ROOT


def fake_probes():
    spec=importlib.util.spec_from_file_location('gui_candidate',ROOT/adapter.DERIVATIVE)
    runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)
    checks=[]
    def check(name,value):checks.append({'name':name,'pass':bool(value)})
    class Clock:
        def __init__(self):self.now=0
        def monotonic(self):return self.now
        def sleep(self,seconds):self.now+=seconds
    class Node:
        def __init__(self,name='Title',interfaces=('EditableText',),focus=False,action=True,setter=True,focus_error=False,set_error=False):
            self.name=name;self.interfaces=interfaces;self.focus=focus;self.action=action;self.setter=setter
            self.focus_error=focus_error;self.set_error=set_error;self.values=[];self.focus_attempts=0
        def get_name(self):return self.name
        def get_interfaces(self):return self.interfaces
        def get_action_iface(self):
            if not self.action:raise RuntimeError('Action interface unavailable')
            return self
        def get_n_actions(self):return 1
        def get_action_name(self,index):return 'focus'
        def do_action(self,index):
            self.focus_attempts+=1
            if self.focus_error:raise RuntimeError('focus failed')
            return self.focus
        def get_component_iface(self):return self
        def grab_focus(self):return self.do_action(0)
        def get_editable_text_iface(self):return self
        def set_text_contents(self,value):
            self.values.append(value)
            if self.set_error:raise RuntimeError('set failed')
            return self.setter
    def attempt(node,success,diagnostic=None):
        driver=runtime.GuiDriver.__new__(runtime.GuiDriver)
        driver.timeout=1;driver.events=[];driver.nodes=lambda:[node]
        clock=Clock();error=None
        with patch.object(runtime,'time',clock):
            try:driver.enter('Title','exact value')
            except AssertionError as fault:error=str(fault)
        ok=error is None
        valid=ok==success and bool([e for e in driver.events if e['action']=='enter'])==success
        if success:valid=valid and node.values==['exact value']
        if diagnostic:valid=valid and any(e.get('phase')==diagnostic for e in driver.events)
        return valid,{'events':driver.events,'error':error,'elapsed_virtual_seconds':clock.now,'setter_attempts':len(node.values)}
    scenarios=[('false focus supported setter',Node(focus=False),True,'focus'),
               ('focus exception supported setter',Node(focus_error=True),True,'focus'),
               ('action absence supported setter',Node(action=False),True,'focus'),
               ('true focus supported setter',Node(focus=True),True,None),
               ('setter false remains failure',Node(setter=False),False,'set_text_contents'),
               ('setter exception remains failure',Node(set_error=True),False,'set_text_contents'),
               ('wrong exact label fails',Node(name='Title other'),False,None),
               ('missing EditableText fails',Node(interfaces=('Text',)),False,None)]
    details=[]
    for name,node,success,diagnostic in scenarios:
        passed,detail=attempt(node,success,diagnostic);check(name,passed)
        if not success:check(name+' bounded timeout',1<=detail['elapsed_virtual_seconds']<1.5)
        details.append({'name':name,**detail})
    class Unsupported(Node):
        def get_editable_text_iface(self):raise RuntimeError('setter interface unavailable')
    passed,detail=attempt(Unsupported(),False,'set_text_contents');check('advertised but unsupported setter fails',passed);details.append({'name':'unsupported setter',**detail})
    class NoFocusAction(Node):
        def get_action_name(self,index):return 'tap'
    node=NoFocusAction(focus=False);passed,detail=attempt(node,True,'focus')
    check('no focus action false Component focus permits supported setter',passed and node.focus_attempts==1);details.append({'name':'component false focus',**detail})
    originals=(w01.ROOT,w02.ROOT);cases=(w01.CASE,w02.CASE)
    try:
        with adapter.derivative_mount():
            check('uniform W01 W02 derivative mount',w01.ROOT==w02.ROOT==adapter.DERIVATIVE_ROOT)
            check('CASE constants unchanged',cases==(w01.CASE,w02.CASE))
            raise RuntimeError('probe failure')
    except RuntimeError:pass
    check('mount roots restored after exception',originals==(w01.ROOT,w02.ROOT))
    with adapter.derivative_mount():pass
    check('mount roots restored after success',originals==(w01.ROOT,w02.ROOT))
    def rejected(fn):
        try:fn();return False
        except (ValueError,OSError):return True
    actual_plan=adapter.candidate_preflight()
    check('original source and frozen collector hashes unchanged',bool(actual_plan))
    with tempfile.TemporaryDirectory() as temporary:
        changed_plan = Path(temporary)/'plan.json'
        for field, value in [('phase','heldout'),('case','W01' if actual_plan['affected_cohort'][0]['case']=='W02' else 'W02'),
                             ('condition','foreign'),('repeat',9)]:
            changed=json.loads(json.dumps(actual_plan));changed['affected_cohort'][0][field]=value
            changed_plan.write_text(json.dumps(changed))
            with patch.object(adapter,'PLAN',changed_plan):check('canonical cohort '+field+' mismatch rejected',rejected(adapter.candidate_preflight))
        changed=json.loads(json.dumps(actual_plan));changed['affected_cohort'].reverse();changed_plan.write_text(json.dumps(changed))
        with patch.object(adapter,'PLAN',changed_plan):check('original cohort order mismatch rejected',rejected(adapter.candidate_preflight))

    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);reg=root/'registration.json'
        for name in adapter.REQUIRED_PINS:
            file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('{}')
        pins={name:adapter.digest(root/name) for name in adapter.REQUIRED_PINS}
        registration={'version':adapter.VERSION,'status':'frozen','source_sha256':pins,
                      'affected_cohort':actual_plan['affected_cohort'],'replacement_run_ids':[row['run_id'] for row in actual_plan['affected_cohort']]}
        with patch.object(adapter,'ROOT',root),patch.object(adapter,'MANIFEST',reg),patch.object(adapter,'candidate_preflight',return_value=actual_plan):
            check('absent registration rejected',rejected(adapter.verify_registration))
            reg.write_text(json.dumps(registration));check('full frozen registration verifies',adapter.verify_registration()==registration)
            for category,change in [('unfrozen',lambda r:r.update(status='draft')),
                                    ('incomplete pins',lambda r:r['source_sha256'].pop(adapter.DERIVATIVE)),
                                    ('selective cohort',lambda r:r['replacement_run_ids'].pop()),
                                    ('altered cohort order',lambda r:r['replacement_run_ids'].reverse())]:
                changed=json.loads(json.dumps(registration));change(changed);reg.write_text(json.dumps(changed))
                check(category+' rejected',rejected(adapter.verify_registration))
            reg.write_text(json.dumps(registration));(root/adapter.DERIVATIVE).write_text('drift')
            check('derivative drift rejected',rejected(adapter.verify_registration))
    row=actual_plan['affected_cohort'][0];run_id=row['run_id']
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);metadata=root/'runtime'/run_id/'run.json';metadata.parent.mkdir(parents=True)
        metadata.write_text(json.dumps({'run_id':run_id,'phase':'software','case_id':row['case'],'condition':row['condition'],'repeat':row['repeat'],'model_evidence':[{'model':'gpt-6.1-sol','effort':'medium'}]}))
        reg=root/'registration.json';reg.write_text('{}')
        registration={'replacement_run_ids':[r['run_id'] for r in actual_plan['affected_cohort']], 'affected_cohort':actual_plan['affected_cohort']}
        def controlled(*args):
            check('frozen grader executes with both derivative roots',w01.ROOT==w02.ROOT==adapter.DERIVATIVE_ROOT)
            raise RuntimeError('grade failure')
        with patch.object(adapter,'ROOT',root),patch.object(adapter,'MANIFEST',reg),patch.object(adapter,'verify_registration',return_value=registration),patch.object(adapter.grade,'grade',side_effect=controlled):
            # root guard must still see the actual original roots, so context alone
            # receives the real source root while metadata uses temporary root.
            original_mount=adapter.derivative_mount
            from contextlib import contextmanager
            @contextmanager
            def mount():
                with patch.object(adapter,'ROOT',ROOT):
                    with original_mount():yield
            with patch.object(adapter,'derivative_mount',mount):
                try:adapter.qualified_grade(run_id)
                except RuntimeError:pass
                check('qualified grade exception restores both roots',originals==(w01.ROOT,w02.ROOT))
                check('unregistered run rejected',rejected(lambda:adapter.qualified_grade('outside')))
                metadata.write_text(json.dumps({'run_id':run_id,'phase':'software','case_id':row['case'],'condition':row['condition'],'repeat':row['repeat'],'model_evidence':[{'model':'gpt-6.1-sol','effort':'medium'}],'dialogue_protocol':{'protocol':'controlled-file-v1'}}))
                core=root/'results/frozen-core-v3.6.json';core.parent.mkdir(parents=True,exist_ok=True);core.write_text('{}')
                derivative=root/adapter.DERIVATIVE;derivative.parent.mkdir(parents=True,exist_ok=True);derivative.write_text('candidate view')
                grade_path=root/'results'/run_id/'grade.json';grade_path.parent.mkdir(parents=True)
                mock_result={'status':'fail','behavior_pass':False,'runtime_evidence':{'checks':[{'command':['docker','run','-v',str(adapter.DERIVATIVE_ROOT/'scripts')+':/grader/scripts:ro','dbus-run-session']}]}}
                grade_path.write_text(json.dumps(mock_result))
                with patch.object(adapter.dialogue_schema,'qualified_grade',return_value=mock_result) as native:
                    actual=adapter.qualified_grade(run_id)
                    check('controlled grading retains native schema entrypoint and failure result',actual==mock_result and native.call_count==1)
                    audit=root/'results'/run_id/'software-gui-transport-audit-v3.6.3.json'
                    proof=json.loads(audit.read_text())
                    check('immutable audit links actual mount derivative model and raw grade',proof['mount_matches_registered_derivative'] and proof['actual_model_evidence']==[{'model':'gpt-6.1-sol','effort':'medium'}] and proof['grade_artifact']['sha256']==adapter.digest(grade_path) and proof['derivative_sha256']==adapter.digest(derivative) and proof['status']=='fail')
                    check('immutable audit refuses overwrite before grading',rejected(lambda:adapter.qualified_grade(run_id)) and native.call_count==1)
                audit.unlink()
                wrong_mount=json.loads(json.dumps(mock_result));wrong_mount['runtime_evidence']['checks'][0]['command'][3]='/foreign/scripts:/grader/scripts:ro'
                grade_path.write_text(json.dumps(wrong_mount))
                with patch.object(adapter.dialogue_schema,'qualified_grade',return_value=wrong_mount):
                    check('actual wrong GUI mount rejected and recorded',rejected(lambda:adapter.qualified_grade(run_id)) and json.loads(audit.read_text())['mount_matches_registered_derivative'] is False)
                audit.unlink()
                early={'status':'evaluation_error','behavior_pass':None,'control_audit':{'status':'evaluation_error'}}
                grade_path.write_text(json.dumps(early))
                with patch.object(adapter.dialogue_schema,'qualified_grade',return_value=early):
                    check('control failure preserved without claiming GUI execution',adapter.qualified_grade(run_id)==early and json.loads(audit.read_text())['gui_executed'] is False and json.loads(audit.read_text())['mount_matches_registered_derivative'] is None)


    return {'version':adapter.VERSION,'verdict':'pass' if all(c['pass'] for c in checks) else 'fail','checks':checks,'fake_interfaces':details,
            'source_sha256':{name:adapter.digest(ROOT/name) for name in adapter.REQUIRED_PINS},
            'limitations':['Fake interfaces qualify input transport only; real reference acceptance remains required.',
                           'Only GuiDriver.enter differs. Labels, other methods, timeouts and frozen acceptance remain identical.']}


def actual_qualification():
    adapter.candidate_preflight()
    destination=ROOT/'runtime/software-validation/gui-transport-v3.6.3'
    if destination.exists():raise ValueError('Qualification directory already exists; preserve unique execution evidence')
    destination.mkdir(parents=True)
    before={case:{variant:w01.tree_hashes(ROOT/f'software_cases/{case}/{variant}') for variant in ('repo','reference','oracle')}
            for case in ('W01','W02')}
    source_pins={name:adapter.digest(ROOT/name) for name in adapter.REQUIRED_PINS}
    records=[]
    variants=[('W01','baseline',w01.CASE/'repo'),('W01','reference',w01.CASE/'reference')]
    for kind in ('omit_restore','duplicate_edit','ignore_delete'):
        variants.append(('W01',kind,w01.mutate_reference(kind,destination/'W01'/('source-'+kind))))
    variants.extend([('W02','baseline',w02.CASE/'repo'),('W02','reference',w02.CASE/'reference')])
    mutant=destination/'W02/source-no-archive';shutil.copytree(w02.CASE/'reference',mutant)
    path=mutant/'lib/todo_controller.dart';text=path.read_text()
    assert 'copyWith(archived: true)' in text or 'copyWith(archived:true)' in text
    path.write_text(text.replace('copyWith(archived: true)','copyWith(archived: false)').replace('copyWith(archived:true)','copyWith(archived:false)'))
    variants.append(('W02','no_archive',mutant))
    for case,variant,source in variants:
        with adapter.derivative_mount():
            result=(w01 if case=='W01' else w02).grade_repo(source,destination/case/variant)
        records.append({'case':case,'variant':variant,**result})
        print(json.dumps({'case':case,'variant':variant,'status':result['status'],'gui_status':result.get('gui',{}).get('status'),'error':result.get('gui',{}).get('error')}),flush=True)
    after={case:{variant:w01.tree_hashes(ROOT/f'software_cases/{case}/{variant}') for variant in ('repo','reference','oracle')}
           for case in ('W01','W02')}
    originals_unchanged=before==after and source_pins=={name:adapter.digest(ROOT/name) for name in adapter.REQUIRED_PINS}
    reference=[r for r in records if r['variant']=='reference']
    controls=[r for r in records if r['variant']!='reference']
    positive=all(r['status']=='pass' for r in reference) and len(reference)==2
    negative=all(r['status']=='fail' and r.get('gui',{}).get('status')=='fail' for r in controls) and len(controls)==6
    semantic_controls=[r for r in controls if r['variant']!='baseline']
    negative=negative and all(all(c['exit_code']==0 for c in r['checks'][:-1]) for r in semantic_controls)
    summary={'version':adapter.VERSION,'verdict':'pass' if positive and negative and originals_unchanged else 'fail',
             'qualification_only_no_actor_or_historical_regrade':True,'originals_unchanged':originals_unchanged,
             'reference_acceptance_pass':positive,'negative_controls_fail_intended_acceptance':negative,
             'source_sha256':source_pins,'fixture_hashes':before,'records':records,
             'runtime_evidence_directory':str(destination),'all_outputs_preserved':True}
    (destination/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'results/software-gui-transport-runtime-qualification-v3.6.3.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--actual',action='store_true');args=parser.parse_args()
    probes=fake_probes()
    (ROOT/'results/software-gui-transport-probes-v3.6.3.json').write_text(json.dumps(probes,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'probe_verdict':probes['verdict'],'checks':len(probes['checks']),'failed':[c for c in probes['checks'] if not c['pass']]}),flush=True)
    if args.actual:
        if probes['verdict']!='pass':raise SystemExit(1)
        summary=actual_qualification();print(json.dumps({'actual_verdict':summary['verdict']}),flush=True)
