"""Deterministic complete comparison schedule, without inferring missing runs as success."""
import argparse
import json
import random
from pathlib import Path
from prepare import ROOT

SEED=20261010
def schedule(candidate='C0'):
    rows=[]
    groups=[('primary',[f'E{i:02}' for i in range(1,13)],['A','B',candidate]),
            ('auxiliary',[f'S{i:02}' for i in range(1,7)],['B',candidate]),
            ('software',['W01','W02'],['A','B',candidate]),
            ('heldout',[f'H{i:02}' for i in range(1,5)],['A',candidate])]
    for phase,cases,conditions in groups:
        group=[]
        for case in cases:
            for condition in conditions:
                for repeat in range(1,4):
                    group.append({'run_id':f'{phase}-{case}-{condition}-{repeat}',
                                 'phase':phase,'case':case,'condition':condition,'repeat':repeat})
        random.Random(str(SEED)+':'+phase).shuffle(group)
        rows.extend(group)
    return {'seed':SEED,'candidate':candidate,'count':len(rows),'runs':rows}

def progress(plan):
    counts={}
    for row in plan['runs']:
        grade=ROOT/'results'/row['run_id']/'grade.json'
        state=json.loads(grade.read_text()).get('status','unknown') if grade.exists() else 'not_evaluated'
        counts[state]=counts.get(state,0)+1
    return {'candidate':plan['candidate'],'planned':plan['count'],'statuses':counts}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',default='C0');parser.add_argument('--write',action='store_true')
    args=parser.parse_args();plan=schedule(args.candidate)
    if args.write:
        destination=ROOT/'results'/f'schedule-{args.candidate}.json'
        if destination.exists() and json.loads(destination.read_text())!=plan:
            raise ValueError('Refusing to overwrite an existing different schedule')
        destination.write_text(json.dumps(plan,indent=2))
    print(json.dumps(progress(plan),indent=2))
