"""Derivative lexical replay of preserved v5 calls, never actor rerun or outcome promotion."""
import hashlib,json,shlex,subprocess
from pathlib import Path
import improvement_software_broker_native_v6 as native
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'results/improvement-v1/software-broker-v5-actual-1'
REPORT=ROOT/'results/improvement-v1/software-broker-native-v6-observed-quotes.json'
if __name__=='__main__':
    assert not REPORT.exists()
    reg=json.loads((ROOT/'runtime/protocol-probes/software-broker-v5-actual-1/protocol.json').read_bytes())
    reg['run_name']='software-broker-v6-actual-1'
    checks=[]
    for job in native.MODEL and ('label','quantity','root'):
        events,_=native.parse((BASE/(job+'-native.jsonl')).read_bytes())
        for event in events:
            p=event.get('payload',{})
            if p.get('type')!='custom_tool_call' or p.get('name')!='exec':continue
            code=p.get('input','')
            if '--data ' not in code:continue
            if 'write_stdin' in code:continue
            updated=code.replace('broker_v5.py','broker_v6.py').replace('software-broker-v5-actual-1','software-broker-v6-actual-1')
            request=native.wrapper(updated,ROOT,reg,job)
            # Independently exercise both POSIX literal encodings, printing bytes only.
            payload=json.dumps(request['data'])
            for quoted in (shlex.quote(payload),"'"+payload.replace("'","'\\''")+"'"):
                receipt=subprocess.run(['/bin/sh','-c',"printf '%s' "+quoted],capture_output=True,check=True,timeout=5)
                assert receipt.stdout==payload.encode() and not receipt.stderr
            checks.append({'job':job,'call_id':p['call_id'],'op':request['op'],'literal_shell_roundtrip':True})
    assert len(checks)==11
    pins=[Path(__file__),ROOT/'tools/improvement_software_broker_native_v6.py',BASE/'terminal-evidence.json']+[BASE/(j+'-native.jsonl') for j in ('label','quantity','root')]
    with REPORT.open('x') as f:json.dump({'status':'pass','observed_calls':checks,'derivative_route_names_only':True,'original_attempt_status':'incomplete','actor_reruns':0,'original_grade_promoted':False,'superiority_proven':False,'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in pins}},f,indent=2)
    print(json.dumps({'status':'pass','calls':len(checks),'actual_models_rerun':0}))
