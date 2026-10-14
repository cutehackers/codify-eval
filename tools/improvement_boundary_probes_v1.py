"""Real host filesystem abuse cases for the development boundary guard."""
import hashlib,json,os,pathlib,tempfile
from improvement_boundary_v1 import inspect_repo
from improvement_qualify_v2 import failed_tests
ROOT=pathlib.Path(__file__).resolve().parents[1];rows=[]
with tempfile.TemporaryDirectory(prefix='codify-boundary-') as temp:
 base=pathlib.Path(temp);outside=base/'outside';outside.mkdir();secret=outside/'sentinel.txt';secret.write_text('must not be copied or exported');before=hashlib.sha256(secret.read_bytes()).hexdigest()
 def attempt(name,build,allowed):
  repo=base/name;repo.mkdir();(repo/'lib').mkdir();build(repo)
  try:inspect_repo(repo);accepted=True
  except ValueError:accepted=False
  rows.append({'id':name,'pass':accepted==allowed,'accepted':accepted})
 attempt('ordinary',lambda p:(p/'lib/main.dart').write_text('void main() {}'),True)
 attempt('absolute_escape',lambda p:(p/'lib/leak.dart').symlink_to(secret),False)
 attempt('relative_escape',lambda p:(p/'lib/leak.dart').symlink_to('../../../outside/sentinel.txt'),False)
 attempt('broken_link',lambda p:(p/'lib/leak.dart').symlink_to(outside/'missing'),False)
 attempt('directory_escape',lambda p:(p/'lib/exports').symlink_to(outside,target_is_directory=True),False)
 attempt('cycle',lambda p:(p/'lib/cycle').symlink_to(p,target_is_directory=True),False)
 attempt('fifo',lambda p:os.mkfifo(p/'lib/pipe'),False)
 attempt('ignored_build',lambda p:(p/'build').symlink_to(outside,target_is_directory=True),True)
 linked=base/'linkedroot';linked.symlink_to(base/'ordinary',target_is_directory=True)
 try:inspect_repo(linked);accepted=True
 except ValueError:accepted=False
 rows.append({'id':'linked_root','pass':not accepted})
 rows.append({'id':'external_sentinel_unchanged','pass':hashlib.sha256(secret.read_bytes()).hexdigest()==before})
 for name,test,kind,expected_compile in [('semantic_exception','dispose blocks state writes','error',False),('assertion','preserves previous data','failure',False),('compile_error','loading /test/acceptance_test.dart','error',True)]:
  events=[{'type':'testStart','test':{'id':4,'name':test}},{'type':'testDone','testID':4,'result':kind}]
  names,compile_fault=failed_tests('\n'.join(json.dumps(e) for e in events));rows.append({'id':name,'pass':names==[test] and compile_fault==expected_compile})
 names,compile_fault=failed_tests('timeout: killed process');rows.append({'id':'timeout_not_behavior','pass':names==[]})
receipt={'status':'pass' if all(x['pass'] for x in rows) else 'fail','checks':rows,'source_hashes':{n:hashlib.sha256((ROOT/'tools'/n).read_bytes()).hexdigest() for n in ('improvement_boundary_v1.py','improvement_qualify_v2.py','improvement_boundary_probes_v1.py')}}
out=ROOT/'results/improvement-v1/boundary-probes-v1.json'
if out.exists():raise ValueError('Do not replace prior probe evidence')
out.write_text(json.dumps(receipt,indent=2));print(receipt['status'],len(rows));raise SystemExit(0 if receipt['status']=='pass' else 1)
