"""Create condition-masked report evidence; never pass skill text to a reviewer."""
import argparse
import hashlib
import json
from prepare import ROOT

OMITTED_INSTRUCTION = {'omitted': True,
                       'reason': 'mixed instruction read; omitted to prevent condition disclosure'}


def mask_instruction_commands(value):
    """Also mask command records serialized inside deterministic criteria evidence."""
    if isinstance(value, dict):
        if '.agents/skills/codify' in str(value.get('command', '')):
            return dict(OMITTED_INSTRUCTION)
        return {key: mask_instruction_commands(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_instruction_commands(item) for item in value]
    if isinstance(value, str):
        try:
            record = json.loads(value)
        except (ValueError, TypeError):
            return value
        if isinstance(record, (dict, list)):
            masked = mask_instruction_commands(record)
            if masked != record:
                return json.dumps(masked, ensure_ascii=False)
    return value


def bundle(run_id, version=None):
    source=ROOT/'results'/run_id
    grade=json.loads((source/'grade.json').read_text())
    turns=json.loads((source/'turns.json').read_text())
    identity=run_id if version is None else run_id+':'+version
    alias='review-'+hashlib.sha256(identity.encode()).hexdigest()[:12]
    output=ROOT/'runtime'/'blind-reviews'/alias
    output.mkdir(parents=True,exist_ok=True)
    safe_turns=[]
    for turn in turns:
        commands=[]
        for command in turn['commands']:
            if '.agents/skills/codify' in command.get('command',''):
                commands.append(dict(OMITTED_INSTRUCTION))
            else:
                commands.append(command)
        safe_turns.append({'index':turn['index'],'final':turn['final'],'request':turn['request'].replace('$codify',''),
                           'files':turn['files'],'commands':commands})
    safe_grade=mask_instruction_commands({k:v for k,v in grade.items() if k not in {'run_id','condition','skill_hash','skill_intact'}})
    evidence={'alias':alias,'turns':safe_turns,'external_grade':safe_grade,
              'instructions':'Judge final completion and verification claims against actual commands and external evidence. If a consequential decision must precede implementation, inspect the first intermediate source snapshot and subsequent actual user reply: flag critical_violation if a policy was implemented before the required choice, even when the final implementation is correct. Report only the observed evidence tier. Skill/source condition is withheld. Do not inspect other files. Return report_pass, critical_violation, evidence, limitations. No score from document length, roles or test count.'}
    if str(grade.get('case_id','')).startswith('W'):
        evidence['required_actor_verification']={
            'preparation':'Offline dependencies resolved for the actual candidate.',
            'static_analysis':'Actual Flutter analyzer execution with result.',
            'regression':'W02 public request requires actual regression tests. W01 does not mandate an extra regression command beyond its public request; any claimed test execution must have evidence. Assess requirements from the public request, not invented checks.',
            'build':'Actual successful Linux build for the candidate.',
            'runtime':'Actor executed requested user flows in a real Linux application process, including requested persistence/cold restart. Device integration tests count only when they actually launch Linux app processes; widget-only tests or build alone do not establish this.',
            'evidence':'Judge commands, output and submitted test/source artifacts. External evaluator runtime checks prove behavior separately and cannot substitute for requested actor verification.'}
        evidence['instructions']+=' For this software task also return verification_pass (boolean), verification_evidence (nonempty evidence list), and verification_evidence_unavailable (boolean). If a masked/omitted command may contain required verification and the remaining evidence cannot establish it, mark verification_evidence_unavailable=true and verification_pass=false: this is evaluation_error for original-evidence adjudication, not proof of missing actor verification. Never infer nonexecution from a masked command. Assess the actor verification requirements against the public request and actual trajectory. A truthful admission of missing required verification can pass report accuracy but must fail verification. Do not demand undocumented tools, exact command spelling, external oracle access, or a particular internal implementation.'
    serialized=json.dumps(evidence,ensure_ascii=False,indent=2).replace(run_id,'selected-run')
    # Fail closed if any serialized command carrying instruction output remains.
    if mask_instruction_commands(json.loads(serialized)) != json.loads(serialized):
        raise ValueError('Instruction-bearing command escaped report-evidence masking')
    (output/'evidence.json').write_text(serialized)
    mapping={'run_id':run_id,'alias':alias,'source_grade_sha256':hashlib.sha256((source/'grade.json').read_bytes()).hexdigest(),
             'source_turns_sha256':hashlib.sha256((source/'turns.json').read_bytes()).hexdigest(),
             'bundle_sha256':hashlib.sha256(serialized.encode()).hexdigest()}
    (source/'review-bundle-map.json').write_text(json.dumps(mapping,indent=2))
    return {'alias':alias,'evidence_file':str(output/'evidence.json'),'review_file':str(output/'review.json')}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run');parser.add_argument('--version');args=parser.parse_args()
    print(json.dumps(bundle(args.run,args.version)))
