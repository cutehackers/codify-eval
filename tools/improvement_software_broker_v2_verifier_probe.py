"""Actual pristine verification of toy start/reference, no model allocation."""
import hashlib
import json
from pathlib import Path
import shutil
import time

from improvement_software_broker_v2 import fresh_verify, ROOT, runtime

OUT = ROOT/'results/improvement-v1/software-broker-v2-verifier-probe.json'
FOLDER = ROOT/'runtime/protocol-probes/software-broker-v2-verifier-probe'
FIXTURE = ROOT/'runtime/protocol-probes/software-broker-fixture-v3'


def main():
    assert not OUT.exists() and not FOLDER.exists()
    if shutil.disk_usage(FOLDER.parent).free < 3*1024**3:
        raise ValueError('Disk floor before probe')
    FOLDER.mkdir()
    variants=[]
    for variant in ('starting','reference'):
        folder=FOLDER/variant;folder.mkdir()
        shutil.copytree(FIXTURE/'starting',folder/'root/repo')
        if variant=='reference':
            shutil.copytree(FIXTURE/'reference',folder/'root/repo',dirs_exist_ok=True)
        runtime.persist(folder,{'deadline':time.time()+180,'started_at':time.time()})
        try:
            result=fresh_verify(folder,{'run_name':'software-broker-v2-verifier-probe-'+variant,'image_id':runtime.IMAGE})
            receipt=json.loads(Path(result['verifier_receipt']).read_bytes())
            text=result['stdout']+result['stderr']
            good=(result['exit_code']==1 and 'FAILED (failures=37)' in text and 'ERROR' not in text if variant=='starting' else result['exit_code']==0 and 'Ran 10 tests' in text and text.rstrip().endswith('OK'))
            variants.append({'variant':variant,'qualified':bool(good and receipt.get('removed') is True),'result':result,'receipt_sha256':hashlib.sha256(Path(result['verifier_receipt']).read_bytes()).hexdigest()})
        except Exception as error:
            variants.append({'variant':variant,'qualified':False,'error':type(error).__name__+': '+str(error)})
    paths=[Path(__file__), ROOT/'tools/improvement_software_broker_v2.py',ROOT/'tools/improvement_software_broker_native_v2.py']
    paths+=list((FIXTURE/'starting').rglob('*'))+list((FIXTURE/'reference').rglob('*'))
    report={'status':'pass' if len(variants)==2 and all(v['qualified'] for v in variants) else 'fail',
            'variants':variants,'model_actors_allocated':0,'full_broker_qualified':False,'superiority_proven':False,
            'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}}
    with OUT.open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps({'status':report['status'],'variants':[{k:v for k,v in x.items() if k!='result'} for x in variants]}))
    if report['status']!='pass':raise SystemExit(1)

if __name__=='__main__':main()
