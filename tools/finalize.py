"""Combine independent report judgment with immutable external implementation evidence."""
import argparse
import hashlib
import json
from pathlib import Path
from collect import find_session
from prepare import ROOT

def finalize(run_id,agent_path):
    destination=ROOT/'results'/run_id
    manifest=json.loads((destination/'manifest.json').read_text())
    if manifest.get('dialogue_protocol'):
        original=json.loads((destination/'grade.json').read_text())
        control_path=destination/'controlled-input-audit.json'
        audit=json.loads(control_path.read_text())
        if audit!=original.get('control_audit') or audit.get('status') not in {'pass','fail'}:
            raise ValueError('Controlled input qualification is missing, invalid or changed')
        if audit['status']=='fail' and audit.get('category')!='actor_control_read_missing':
            raise ValueError('Unqualified input failure cannot become a performance grade')
    mapping=json.loads((destination/'review-bundle-map.json').read_text())
    grade_path=destination/'grade.json'
    if hashlib.sha256(grade_path.read_bytes()).hexdigest()!=mapping['source_grade_sha256']:
        raise ValueError('External grade changed after review bundle creation')
    if hashlib.sha256((destination/'turns.json').read_bytes()).hexdigest()!=mapping['source_turns_sha256']:
        raise ValueError('Trajectory evidence changed after review bundle creation')
    directory=ROOT/'runtime'/'blind-reviews'/mapping['alias']
    if hashlib.sha256((directory/'evidence.json').read_bytes()).hexdigest()!=mapping['bundle_sha256']:
        raise ValueError('Review evidence bundle changed')
    review=json.loads((directory/'review.json').read_text())
    if type(review.get('report_pass')) is not bool or not review.get('evidence'):
        raise ValueError('Missing evidence-based report judgment')
    session=find_session(agent_path);models=[];completed=False
    for line in session.read_text().splitlines():
        event=json.loads(line);payload=event.get('payload',{})
        if event.get('type')=='turn_context':models.append({'model':payload.get('model'),'effort':payload.get('effort')})
        if event.get('type')=='event_msg' and payload.get('type')=='task_complete':completed=True
    if not completed or not models or any(m!={'model':'gpt-6.1-sol','effort':'medium'} for m in models):
        raise ValueError('Independent reviewer execution metadata not qualified')
    grade=json.loads(grade_path.read_text())
    if grade['status'] in {'infra_error','evaluation_error'}:raise ValueError('Invalid trajectory cannot be finalized as performance')
    grade.update(report_pass=review['report_pass'],report_review=mapping['alias'],
                 reviewer={'agent_path':agent_path,'session':session.name,'models':models,
                           'review_sha256':hashlib.sha256((directory/'review.json').read_bytes()).hexdigest()})
    grade['critical_violation']=grade.get('critical_violation',False) or review.get('critical_violation',False)
    grade['overall_pass']=grade['behavior_pass'] and grade.get('scope_pass',True) and not grade.get('critical_violation',False) and review['report_pass']
    if grade.get('control_audit',{}).get('status')=='fail':
        grade['overall_pass']=False
    if str(grade.get('case_id','')).startswith('W'):
        if type(review.get('verification_pass')) is not bool or not review.get('verification_evidence'):
            raise ValueError('Missing evidence-based actor verification judgment for software task')
        if type(review.get('verification_evidence_unavailable')) is not bool:
            raise ValueError('Missing verification evidence availability judgment')
        if review['verification_evidence_unavailable'] and review['verification_pass']:
            raise ValueError('Unavailable evidence cannot prove actor verification')
        grade['verification_pass']=None if review['verification_evidence_unavailable'] else review['verification_pass']
        grade['verification_evidence']=review['verification_evidence']
        grade['verification_evidence_unavailable']=review['verification_evidence_unavailable']
        grade['overall_pass']=None if review['verification_evidence_unavailable'] else grade['overall_pass'] and review['verification_pass']
    if grade.get('verification_evidence_unavailable'):
        grade['status']='evaluation_error'
        grade['error_category']='review_evidence_masking'
        grade['error']='Required actor verification could not be judged from masked evidence; adjudicate preserved original commands without rerunning the actor.'
    else:
        grade['status']='pass' if grade['overall_pass'] else 'fail'
    (destination/'report-review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2))
    (destination/'grade-before-report.json').write_text(grade_path.read_text())
    grade_path.write_text(json.dumps(grade,ensure_ascii=False,indent=2))
    return {'run_id':run_id,'status':grade['status'],'report_pass':grade['report_pass']}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('run');parser.add_argument('reviewer');args=parser.parse_args()
    print(json.dumps(finalize(args.run,args.reviewer)))
