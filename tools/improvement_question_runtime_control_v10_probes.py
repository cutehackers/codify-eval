"""Frozen control allocator schema/prospective isolation probes; no allocation."""
from copy import deepcopy
import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
import improvement_question_runtime_control_v10 as control


class Probes(unittest.TestCase):
    def value(self):
        return {'source_entities':{'source.py':{'kind':'file','mode':420,'sha256':'fixed'}}, 'source_hashes':{'source.py':'fixed'},
                'case_entities':{'Q05':{},'Q06':{}}, 'runtime_control_scenarios':{'Q05':'normal','Q06':'normal'}, 'cleanup_observation_seconds':180, 'allocation_mode':'runtime_qualification_control','adaptive_runtime_qualified':False,
                'comparison_eligible':False,'primary_confirmation_reuse_allowed':False,'superiority_proven':False,
                'model':'gpt-6.1-sol','effort':'medium','trajectory_seconds':1200,'actor_cap':1,
                'concurrency':1,'retries':0,'image_id':'fixed','conditions':['A'],'skill_hashes':{},
                'sequence':[{'case_id':case,'condition':'A','repeat':1,'run_id':f'{control.PHASE}-{case}-A-1'} for case in control.CASES]}

    def checked(self, value):
        with patch.object(control.legacy.prior,'check',return_value=value), patch.object(control.legacy,'read',return_value={'image_id':'fixed'}), patch.object(control,'entity',return_value={'kind':'file','mode':420,'sha256':'fixed'}), patch.object(control,'case_entities',return_value={}):
            return control.configure()

    def test_process_local_classifier_v2_integration(self):
        old = (control.pilot.FREEZE, control.pilot.PHASE, control.pilot.configure,
               control.pilot.preparation, control.pilot.product_observation,
               control.pilot.failure_close.PHASE, control.watch.pilot,
               control.deadline_close.PHASE, control.legacy.next_allocation, control.pilot.stage, control.pilot.core.lifecycle, control.pilot.core.turn_id)
        try:
            control.install()
            self.assertIs(control.pilot.product_observation, control.product_observation)
            self.assertIs(control.pilot.preparation, control.preparation)
            self.assertEqual(control.pilot.PHASE, 'control-probe-natural-question-runtime-v5')
            self.assertIs(control.legacy.next_allocation, control.next_allocation)
            self.assertIs(control.pilot.stage, control.guarded_stage)
            self.assertEqual(control.deadline_close.PHASE, control.PHASE)
            self.assertEqual(control.preparation.prepare.__defaults__, (1, 'control-probe-natural-question-v1'))
        finally:
            (control.pilot.FREEZE, control.pilot.PHASE, control.pilot.configure,
             control.pilot.preparation, control.pilot.product_observation,
             control.pilot.failure_close.PHASE, control.watch.pilot,
               control.deadline_close.PHASE, control.legacy.next_allocation, control.pilot.stage, control.pilot.core.lifecycle, control.pilot.core.turn_id) = old

    def test_controls_remain_unqualified_and_noncomparative(self):
        value=self.checked(self.value())
        self.assertIs(value['adaptive_runtime_qualified'],False)
        self.assertEqual(value['conditions'],['A'])

    def test_delivery_guard_runs_before_existing_stage(self):
        with patch.object(control.deadline_close, 'require_delivery_open', side_effect=AssertionError('committed')), \
             patch.object(control, 'ORIGINAL_STAGE') as stage:
            with self.assertRaisesRegex(AssertionError, 'committed'):
                control.guarded_stage('synthetic')
            stage.assert_not_called()

    def test_next_allocation_consumes_new_deadline_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); first=root/'results/first'; first.mkdir(parents=True)
            (first/'grade.json').write_text(json.dumps({'deadline_aborted': True}))
            runtime=root/'runtime/first'; runtime.mkdir(parents=True)
            (runtime/'run.json').write_text(json.dumps({'run_id':'first','started_at':0}))
            sequence=[{'run_id':'first'}, {'run_id':'next'}]
            with patch.object(control,'ROOT',root), patch.object(control.deadline_close,'verify_closed',return_value={'native_completion_observed':False}) as verify:
                self.assertEqual(control.next_allocation({'sequence':sequence}), sequence[1])
                verify.assert_called_once()
            with patch.object(control,'ROOT',root), patch.object(control.deadline_close,'verify_closed',side_effect=AssertionError('missing postfence')):
                with self.assertRaisesRegex(AssertionError,'postfence'):
                    control.next_allocation({'sequence':sequence})

    def test_normal_control_uses_only_public_task_without_forced_question(self):
        for case in control.CASES:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root=Path(directory); fixture=root/'fixture'; (fixture/'repo').mkdir(parents=True)
                (fixture/'public').mkdir(); (fixture/'public/request.md').write_text('synthetic public request')
                (fixture/'repo/file').write_text('synthetic')
                (root/'runtime').mkdir(); (root/'runtime/image.json').write_text(json.dumps({'image_id':'synthetic'}))
                with patch.object(control.preparation,'ROOT',root), patch.object(control.preparation,'case_directory',return_value=fixture), patch.object(control.preparation.subprocess,'run') as command:
                    result=control.preparation.prepare(case,'A',1,control.PHASE)
                prompt=Path(result['prompt_file']).read_text()
                metadata=json.loads((Path(result['prompt_file']).parent/'run.json').read_bytes())
                self.assertIn('synthetic public request',prompt)
                self.assertNotIn('clock.sleep',prompt)
                self.assertNotIn("--cmd 'exit 7'",prompt)
                self.assertEqual(metadata['runtime_control_scenario'],'normal')
                self.assertEqual(metadata['model'],'gpt-6.1-sol')
                self.assertEqual(metadata['effort'],'medium')
                self.assertEqual(sum(call.args[0][0]=='docker' for call in command.call_args_list),1)

    def test_false_qualification_and_candidate_or_gate_changes_rejected(self):
        for key,value in [('adaptive_runtime_qualified',True),('comparison_eligible',True),('conditions',['A','C16']),
                          ('trajectory_seconds',60),('model','deliberately-invalid-control'),('effort','high'),
                          ('allocation_mode','comparison'),('retries',1),('actor_cap',2),('actor_cap',True),('concurrency',True),('trajectory_seconds',1200.0),('retries',False),('superiority_proven',True)]:
            changed=deepcopy(self.value());changed[key]=value
            with self.subTest(key=key),self.assertRaises(AssertionError):self.checked(changed)

    def test_reordered_or_extra_allocations_rejected(self):
        changed=self.value();changed['sequence'].reverse()
        with self.assertRaises(AssertionError):self.checked(changed)
        changed=self.value();changed['sequence'].append(deepcopy(changed['sequence'][0]))
        with self.assertRaises(AssertionError):self.checked(changed)

    def test_missing_freeze_does_not_bootstrap_qualification(self):
        with patch.object(control.legacy.prior,'check',side_effect=FileNotFoundError('prospective freeze required')):
            with self.assertRaises(FileNotFoundError):control.configure()

    def test_mode_only_and_kind_changes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source';path.write_text('same bytes')
            before=control.entity(path);path.chmod(0o600)
            self.assertNotEqual(control.entity(path),before)
            link=Path(directory)/'link';link.symlink_to(path)
            with self.assertRaises(AssertionError):control.entity(link)

    def test_nonempty_review_pin_coverage_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.py';source.write_text('same')
            review=root/'review.json';names=set()
            with patch.object(control,'ROOT',root):
                review.write_text(json.dumps({'verdict':'PASS','issues':[]}))
                with self.assertRaises(AssertionError):control.check_review(review,names,required=[source])
                review.write_text(json.dumps({'verdict':'PASS','issues':[],'source_hashes':{'source.py':control.legacy.sha(source)}}))
                control.check_review(review,names,required=[source])
                with self.assertRaises(AssertionError):control.check_review(review,names,required=[root/'missing.py'])

    def test_case_directory_entity_mode_changes_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'lib').mkdir();(root/'lib/source.dart').write_text('same')
            with patch.object(control.pilot,'case_directory',return_value=root):
                before=control.case_entities('Q05');(root/'lib').chmod(0o700)
                self.assertNotEqual(control.case_entities('Q05'),before)
                (root/'link').symlink_to(root/'lib/source.dart')
                with self.assertRaises(AssertionError):control.case_entities('Q05')

    def test_external_runtime_pin_round_trips_with_actual_mode_and_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'project';root.mkdir()
            external=Path(directory)/'external-runtime';external.write_text('runtime bytes');external.chmod(0o755)
            internal=root/'module.py';internal.write_text('module bytes')
            with patch.object(control,'ROOT',root):
                self.assertEqual(control.source_key(internal),'module.py')
                self.assertEqual(control.source_key(external),str(external))
                key=control.source_key(external);before=control.entity(external)
                self.assertEqual(control.entity(root/key),before)
                external.chmod(0o700);self.assertNotEqual(control.entity(root/key),before)

    def test_host_fixture_git_hooks_and_generated_named_dirs_are_frozen(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ['.git/hooks/pre-commit','.dart_tool/package_config.json','build/payload','__pycache__/payload']:
                file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('unchanged')
            with patch.object(control.pilot,'case_directory',return_value=root):
                before=control.case_entities('Q05')
                for name in ['.git/hooks/pre-commit','.dart_tool/package_config.json','build/payload','__pycache__/payload']:
                    self.assertIn(name,before)
                (root/'.git/hooks/pre-commit').write_text('changed')
                self.assertNotEqual(control.case_entities('Q05'),before)

    def test_actual_registered_dependency_freeze_dry_run_no_actor(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);own=root/'synthetic-own-review.json';other=root/'synthetic-freeze-review.json'
            # Synthetic review prerequisites exercise freeze plumbing only.
            # This temporary manifest cannot authorize a real allocation.
            pins={str(p):control.legacy.sha(p) for p in control.closure()}
            value={'verdict':'pass','issues':[],'source_hashes':pins}
            own.write_text(json.dumps(value));other.write_text(json.dumps(value))
            with patch.object(control,'REVIEW',own),patch.object(control,'FREEZE_REVIEW',other),patch.object(control,'FREEZE',root/'temporary-freeze.json'),patch.object(control,'RUNTIME_REVIEW',own),patch.object(control,'LIFECYCLE_REVIEW',own):
                result=control.freeze()
                self.assertIs(result['adaptive_runtime_qualified'],False)
                self.assertTrue(any(Path(name).is_absolute() for name in result['source_entities']))
                self.assertEqual(set(result['source_entities']),set(result['source_hashes']))
                self.assertEqual(set(result['case_entities']),{'Q05','Q06'})

    def test_repeat_boolean_and_float_aliases_rejected(self):
        for repeat in (True,1.0):
            value=self.value();value['sequence'][0]['repeat']=repeat
            with self.subTest(repeat=repeat),self.assertRaises(AssertionError):self.checked(value)

if __name__=='__main__':unittest.main()
