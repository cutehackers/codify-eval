"""Prospective exposed-case DEVELOPMENT comparison, never final confirmation."""
import ast
import json
import random
from pathlib import Path
import improvement_question_pilot_v6 as pilot
import improvement_question_runtime_control_v10 as formats
from improvement_software_artifacts_v3 import atomic_json, encoded
import improvement_optional_source_v2 as source

ROOT=pilot.ROOT
BASE=ROOT/'results/improvement-v1'
FREEZE=pilot.FREEZE
REVIEW=BASE/'fresh-development-question-comparison-prelaunch-review-v6.json'
ADMISSION=BASE/'fresh-natural-question-normal-controls-outcome-review-v5-r1.json'
QUALITY=BASE/'fresh-question-cohort-v2-qualification-outcome-review-v2.json'
SEED=610612
CONDITIONS=['A','C0','C16']
CASES=['Q05','Q06']


def sequence():
    rng=random.Random(SEED);rows=[]
    for repeat in range(1,4):
        cases=list(CASES);rng.shuffle(cases)
        for case in cases:
            conditions=list(CONDITIONS);rng.shuffle(conditions)
            rows.extend({'case_id':case,'condition':condition,'repeat':repeat,'run_id':f'{pilot.PHASE}-{case}-{condition}-{repeat}'} for condition in conditions)
    return rows


def closure():
    pending=[Path(__file__).resolve()];found=set()
    while pending:
        p=pending.pop()
        if p in found:continue
        found.add(p)
        for node in ast.walk(ast.parse(p.read_bytes())):
            names=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) else []
            for name in names:
                local=ROOT/'tools'/((name or '').split('.')[0]+'.py')
                if local.is_file() and local not in found:pending.append(local)
    return found


def case_entities(case):
    # Same full entity contract, but explicitly selects this comparison's cases.
    return formats.case_entities(case)


def reviewed_sources():
    names=closure()|{ROOT/'AGENTS.md',ROOT/'docs/improvement-spec-v1.md',ROOT/'runtime/image.json'}
    formats.check_review(REVIEW,names,closure())
    for p in (ADMISSION,QUALITY,BASE/'fresh-natural-question-normal-controls-root-verification-v5-r1.json',BASE/'fresh-natural-question-normal-control-outcome-v5-Q05.json',BASE/'fresh-natural-question-normal-control-outcome-v5-Q06.json'):
        names.add(p)
    admission=pilot.legacy.read(ADMISSION);quality=pilot.legacy.read(QUALITY)
    assert admission['verdict']=='pass' and not admission['issues'] and admission['qualification_recommendation']['prospective_development_comparison_admissible'] is True
    assert quality['qualification_pass'] is True and quality['all_owned_controls_removed'] is True
    root_verification=pilot.legacy.read(BASE/'fresh-natural-question-normal-controls-root-verification-v5-r1.json')
    assert root_verification['verdict']=='pass' and root_verification['review_sha256']==pilot.legacy.sha(ADMISSION)
    q05=pilot.legacy.read(BASE/'fresh-natural-question-normal-control-outcome-v5-Q05.json');q06=pilot.legacy.read(BASE/'fresh-natural-question-normal-control-outcome-v5-Q06.json')
    assert q05['native_control_dimension_pass'] is True and q06['native_control_dimension_pass'] is False and q06['failure_class']=='actor_transport_violation'
    registration=pilot.old.collector.verify();names.add(pilot.old.collector.MANIFEST)
    for key,digest in registration.get('source_hashes',{}).items():
        p=ROOT/key;assert pilot.legacy.sha(p)==digest;names.add(p)
    return names


def freeze():
    assert not FREEZE.exists(),'Never overwrite a prospective comparison'
    names=reviewed_sources()
    rows=sequence();assert all(not (ROOT/'runtime'/r['run_id']).exists() and not (ROOT/'results'/r['run_id']).exists() for r in rows)
    value={'status':'frozen','stage':'exposed development comparison','allocation_mode':'development_comparison','model':'gpt-6.1-sol','effort':'medium','trajectory_seconds':1200,'actor_cap':1,'concurrency':1,'retries':0,'conditions':CONDITIONS,'cases':CASES,'repeats':3,'allocation_seed':SEED,'sequence':rows,'adaptive_runtime_qualified':True,'runtime_qualification_scope':'Shared positive Q05 normal-policy path and negative Q06 route enforcement; Q06 actor failure retained','primary_confirmation_reuse_allowed':False,'superiority_proven':False,'image_id':pilot.legacy.read(ROOT/'runtime/image.json')['image_id'],'case_hashes':{case:pilot.preparation.tree_hash(pilot.case_directory(case)) for case in CASES},'case_entities':{case:case_entities(case) for case in CASES},'skill_hashes':{condition:pilot.preparation.tree_hash(ROOT/'snapshots'/condition) for condition in ('C0','C16')},'skill_entities':{condition:source.inventory(ROOT/'snapshots'/condition) for condition in ('C0','C16')},'source_entities':{formats.source_key(p):formats.entity(p) for p in sorted(names)},'source_hashes':{formats.source_key(p):pilot.legacy.sha(p) for p in sorted(names)},'failure_retention':'All18 original allocations retained; non-infrastructure failures never rerun or excluded','limits':['Exposed Q05/Q06 development evidence only; no untouched confirmation or superiority declaration.','Original phase4/phase5 failures and costs remain separate and unchanged.','Same model/effort/transport/deadline/one conditional reply; source, native origin, all costs and final results require actual evidence.']}
    atomic_json(FREEZE,value,exclusive=True);return value


def policy(value):
    expected={'model':'gpt-6.1-sol','effort':'medium','trajectory_seconds':1200,'actor_cap':1,'concurrency':1,'retries':0,'conditions':CONDITIONS,'cases':CASES,'repeats':3,'allocation_seed':SEED,'sequence':sequence(),'allocation_mode':'development_comparison','adaptive_runtime_qualified':True,'primary_confirmation_reuse_allowed':False,'superiority_proven':False}
    assert encoded({k:value[k] for k in expected})==encoded(expected),'Frozen exact comparison policy changed'


def checked(value=None):
    value=pilot.legacy.read(FREEZE) if value is None else value
    policy(value)
    assert set(value['case_entities'])==set(CASES) and set(value['case_hashes'])==set(CASES)
    assert set(value['skill_entities'])=={'C0','C16'} and set(value['skill_hashes'])=={'C0','C16'}
    assert set(value['source_entities'])==set(value['source_hashes'])
    required={formats.source_key(p) for p in reviewed_sources()}
    assert required==set(value['source_entities']),'Frozen complete reviewed source set changed'
    assert value['status']=='frozen' and value['stage']=='exposed development comparison'
    assert value['image_id']==pilot.legacy.read(ROOT/'runtime/image.json')['image_id']
    assert value['failure_retention']=='All18 original allocations retained; non-infrastructure failures never rerun or excluded'
    for key,row in value['source_entities'].items():
        assert encoded(formats.entity(ROOT/key))==encoded(row),key
        assert row['sha256']==value['source_hashes'][key],key
    for case,row in value['case_entities'].items():assert encoded(case_entities(case))==encoded(row),case
    for condition,row in value['skill_entities'].items():assert encoded(source.inventory(ROOT/'snapshots'/condition))==encoded(row),condition
    return value

if __name__=='__main__':print(json.dumps(freeze()))
