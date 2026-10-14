"""Original first-turn transport regressions; no model, Docker or policy staging."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import collect
import improvement_question_pilot_v6 as pilot
import improvement_question_prepare_v7 as preparation

ROOT=Path(__file__).resolve().parents[1]

class Probes(unittest.TestCase):
    def first(self,case):
        run=f'control-probe-natural-question-runtime-v5-{case}-A-1'
        out=ROOT/'results'/run
        binding=json.loads((out/'actor-binding.json').read_bytes())
        with patch.object(pilot,'adapt'),patch.object(collect,'find_session',return_value=out/'first-native.jsonl'),patch.object(pilot.old,'first',return_value='allowed') as original:
            if case=='Q05':
                self.assertEqual(pilot.first(run,binding['agent_path']),'allowed');original.assert_called_once()
            else:
                with self.assertRaisesRegex(AssertionError,'first-turn actor transport'):pilot.first(run,binding['agent_path'])
                original.assert_not_called()

    def test_original_compliant_first_turn_reaches_seal(self):self.first('Q05')
    def test_actual_forbidden_message_rejected_before_seal_or_reply(self):self.first('Q06')

    def test_preparation_same_restrictions_and_candidate_install_for_all_conditions(self):
        for condition in ('A','C0','C16'):
            with self.subTest(condition=condition),tempfile.TemporaryDirectory() as folder:
                root=Path(folder);case=root/'case';(case/'repo/lib').mkdir(parents=True);(case/'repo/lib/source.dart').write_text('placeholder')
                (case/'public').mkdir();(case/'public/request.md').write_text('PUBLIC TASK ONLY')
                (root/'runtime').mkdir();(root/'runtime/image.json').write_text(json.dumps({'image_id':'fixture'}))
                for name in ('C0','C16'):
                    s=root/'snapshots'/name;s.mkdir(parents=True);(s/'SKILL.md').write_text('fixture skill '+name)
                with patch.object(preparation,'ROOT',root),patch.object(preparation,'case_directory',return_value=case),patch.object(preparation.subprocess,'run'):
                    row=preparation.prepare('Q05',condition,2,'pilot-fresh-question-v6')
                path=Path(row['prompt_file']);prompt=path.read_text();meta=json.loads(path.with_name('run.json').read_bytes())
                self.assertIn('PUBLIC TASK ONLY',prompt);self.assertIn('collaboration.send_message',prompt)
                self.assertEqual(meta['allocation_mode'],'development_comparison');self.assertEqual(meta['model'],'gpt-6.1-sol');self.assertEqual(meta['effort'],'medium')
                self.assertEqual((path.parent/'repo/.agents/skills/codify/SKILL.md').exists(),condition!='A')

    def test_preparation_rejects_aliases_and_wrong_namespace_before_effects(self):
        for repeat,phase in ((True,'pilot-fresh-question-v6'),(1.0,'pilot-fresh-question-v6'),(0,'pilot-fresh-question-v6'),(4,'pilot-fresh-question-v6'),(1,'control-probe-natural-question-runtime-v5')):
            with self.subTest(repeat=repeat,phase=phase),patch.object(preparation.subprocess,'run') as command:
                with self.assertRaises(AssertionError):preparation.prepare('Q05','A',repeat,phase)
                command.assert_not_called()

    def test_deadline_gate_uses_new_closed_authority_and_never_legacy_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);out=root/'results/first';out.mkdir(parents=True)
            (out/'grade.json').write_text(json.dumps({'deadline_aborted':True}))
            run=root/'runtime/first';run.mkdir(parents=True);(run/'run.json').write_text(json.dumps({'run_id':'first'}))
            rows={'sequence':[{'run_id':'first'},{'run_id':'next'}]}
            with patch.object(pilot,'ROOT',root),patch.object(pilot.deadline_close,'verify_closed') as gate,patch.object(pilot,'ORIGINAL_NEXT') as old:
                self.assertEqual(pilot.next_allocation(rows),{'run_id':'next'})
                gate.assert_called_once_with(out,{'run_id':'first'});old.assert_not_called()
                gate.side_effect=AssertionError('cleanup unproven')
                with self.assertRaisesRegex(AssertionError,'cleanup unproven'):pilot.next_allocation(rows)

    def test_whole_grade_deadline_includes_private_verification_and_cleanup(self):
        value=pilot.finish_grade_clock({'status':'review_pending','overall_pass':None},100,1299)
        self.assertFalse(value['whole_trajectory_time_limit_exceeded'])
        self.assertEqual(value['status'],'review_pending')
        value=pilot.finish_grade_clock({'status':'review_pending','overall_pass':None},100,1301)
        self.assertEqual(value['status'],'evaluation_error');self.assertIs(value['overall_pass'],False)
        self.assertEqual(value['allocation_through_grade_seconds'],1201)
        value=pilot.finish_grade_clock({'status':'evaluation_error','first_error':{'type':'original'}},100,1301)
        self.assertEqual(value['first_error']['type'],'original')

if __name__=='__main__':unittest.main()
