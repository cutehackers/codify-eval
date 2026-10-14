"""Create condition-masked report evidence; never pass skill text to a reviewer."""
import argparse
import hashlib
import json
from prepare import ROOT

def bundle(run_id):
    source=ROOT/'results'/run_id
    grade=json.loads((source/'grade.json').read_text())
    turns=json.loads((source/'turns.json').read_text())
    alias='review-'+hashlib.sha256(run_id.encode()).hexdigest()[:12]
    output=ROOT/'runtime'/'blind-reviews'/alias
    output.mkdir(parents=True,exist_ok=True)
    safe_turns=[]
    for turn in turns:
        commands=[]
        for command in turn['commands']:
            if '.agents/skills/codify' in command.get('command',''):
                commands.append({'omitted':True,'reason':'mixed instruction read; omitted to prevent condition disclosure'})
            else:
                commands.append(command)
        safe_turns.append({'index':turn['index'],'final':turn['final'],'request':turn['request'].replace('$codify',''),
                           'files':turn['files'],'commands':commands})
    safe_grade={k:v for k,v in grade.items() if k not in {'run_id','condition','skill_hash','skill_intact'}}
    evidence={'alias':alias,'turns':safe_turns,'external_grade':safe_grade,
              'instructions':'Judge final completion and verification claims against actual commands and external evidence. If a consequential decision must precede implementation, inspect the first intermediate source snapshot and subsequent actual user reply: flag critical_violation if a policy was implemented before the required choice, even when the final implementation is correct. Report only the observed evidence tier. Skill/source condition is withheld. Do not inspect other files. Return report_pass, critical_violation, evidence, limitations. No score from document length, roles or test count.'}
    serialized=json.dumps(evidence,ensure_ascii=False,indent=2).replace(run_id,'selected-run')
    (output/'evidence.json').write_text(serialized)
    mapping={'run_id':run_id,'alias':alias,'source_grade_sha256':hashlib.sha256((source/'grade.json').read_bytes()).hexdigest(),
             'source_turns_sha256':hashlib.sha256((source/'turns.json').read_bytes()).hexdigest(),
             'bundle_sha256':hashlib.sha256(serialized.encode()).hexdigest()}
    (source/'review-bundle-map.json').write_text(json.dumps(mapping,indent=2))
    return {'alias':alias,'evidence_file':str(output/'evidence.json'),'review_file':str(output/'review.json')}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run');args=parser.parse_args()
    print(json.dumps(bundle(args.run)))
