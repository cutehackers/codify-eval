"""Closed positive and negative test lifecycle probes; no grading of actors."""
import copy
import hashlib
import json
from prepare import ROOT
from improvement_q04_verifier_v5 import machine


def main():
    start={'type':'testStart','test':{'id':1,'name':'contract test'}}
    error={'type':'error','testID':1,'error':'Expected: 1\nActual: 2','isFailure':True}
    end={'type':'testDone','testID':1,'result':'failure','skipped':False}
    done={'type':'done','success':False}
    negative=[start,error,end,done]
    rows=[]
    def check(name, events, expected, passed=False):
        log='\n'.join(json.dumps(e) for e in events)
        result=machine(log,1)
        assert result['well_formed'] is expected and result['pass'] is passed, (name,result)
        rows.append({'name':name,'well_formed':result['well_formed'],'pass':True})
    check('genuine matcher failure',negative,True)
    positive=[start,{**end,'result':'success'},{**done,'success':True}]
    check('positive',positive,True,True)
    for name,key,value in [('object_error','error',{'Expected:':'Actual:'}),('missing_error','error',None),
                           ('number_error','error',1),('string_isFailure','isFailure','true'),
                           ('int_isFailure','isFailure',1),('missing_isFailure','isFailure',None),
                           ('bool_testID','testID',True),('unknown_testID','testID',4)]:
        events=copy.deepcopy(negative);events[1][key]=value
        check(name,events,False)
    check('missing_end',[start,error,done],False)
    check('error_after_end',[start,end,error,done],False)
    check('error_success_end',[start,error,{**end,'result':'success'},done],False)
    check('duplicate_end',[start,error,end,end,done],False)
    check('duplicate_start',[start,start,error,end,done],False)
    check('duplicate_done',negative+[done],False)
    check('false_terminal_positive',[start,{**end,'result':'success'},done],False)
    check('true_terminal_negative',[start,error,end,{**done,'success':True}],False)
    check('skipped',[start,error,{**end,'skipped':True},done],False)
    check('unknown_result',[start,error,{**end,'result':'partial'},done],False)
    result=machine('{"type":"done","type":"done","success":false}',1)
    assert not result['well_formed'];rows.append({'name':'duplicate_JSON_key','pass':True})
    for rel, count, expected in [
        ('runtime/protocol-probes/q04-verifier-v3-positive/receipt.json',1,True),
        ('runtime/protocol-probes/q04-verifier-v3-negative/receipt.json',2,False),
        ('runtime/protocol-probes/p02-v8-controls-check-v1/N01_authorization_empty_allowlist-execution/receipt.json',24,False)]:
        path=ROOT/rel;receipt=json.loads(path.read_text());got=machine(receipt['checks'][1]['stdout'],count)
        assert got['well_formed'] and got['pass'] is expected,got
        rows.append({'name':rel,'pass':True,'receipt_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'actual_v5_execution':False})
    value={'status':'pass','count':len(rows),'checks':rows,'actual_v5_execution':False,
           'source_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                            [ROOT/'tools/improvement_q04_verifier_v5.py',ROOT/'tools/improvement_p02_verifier_v3.py',ROOT/'tools/improvement_q04_machine_v5_probes.py']}}
    with (ROOT/'results/improvement-v1/P02-closed-negative-trace-parser-probes-v3.json').open('x') as f:
        json.dump(value,f,indent=2)
    print(json.dumps({'status':'pass','count':len(rows)}))


if __name__=='__main__':
    main()
