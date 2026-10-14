import json,re,hashlib,tarfile,shutil
from pathlib import Path
root=Path('improvement_cases/fresh-question-cohort-v2')
for case in ['Q05','Q06']:
 base=root/case; repo=base/'repo'; logs=base/'private/preliminary-logs'
 generated=[repo/name for name in ['.dart_tool','build','pubspec.lock'] if (repo/name).exists()]
 if generated:
  archive=base/'private/preliminary-host-artifacts.tar.gz'
  with tarfile.open(archive,'w:gz',dereference=False) as tar:
   for p in generated: tar.add(p,arcname=p.name)
  for p in generated:
   if p.is_dir(): shutil.rmtree(p)
   else: p.unlink()
 summary=json.loads((logs/'summary.json').read_text())
 for record in summary['records']:
  if record['label'].endswith('-full') or record['label']=='starting-public':
   s=(base/record['log']).read_text()
   record['failed_test_ids']=re.findall(r': ((?:P|A)\d\d) [^\n]*\[E\]',s)
   totals=re.findall(r'\+(\d+)(?: -(\d+))?: (?:All tests passed!|Some tests failed\.)',s)
   if totals:
    passed,failed=totals[-1];record['passed_count']=int(passed);record['failed_count']=int(failed or 0);record['executed_count']=int(passed)+int(failed or 0)
 (logs/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 provenance=json.loads((base/'authoring-provenance.json').read_text())
 provenance['host_dependency_resolution']='flutter pub get --offline succeeded using locally available SDK/cache dependencies. The CLI printed its generic Downloading packages status, but offline resolution prohibits network package retrieval. Exact output preserved.'
 provenance['generated_artifacts']='Host lockfile, .dart_tool and build preserved in private/preliminary-host-artifacts.tar.gz and removed from the public repo to prevent compiled reference/control or host configuration from reaching evaluated agents.'
 (base/'authoring-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 metadata=json.loads((base/'metadata.json').read_text())
 metadata['host_preliminary']={'qualification':False,'starting_stub_public_failures':metadata['public_test_count'],'reference_full_pass_count':metadata['full_test_count'],'all_reference_and_negative_analyzer_exit_codes':0,'negative_controls_fail_behaviorally':4,'summary':'private/preliminary-logs/summary.json','retained_failures':'Starting stub and all negative controls are expected failures. No unexpected compiler/analyzer/reference test failure observed.'}
 for record in summary['records']:
  if record['label'].endswith('-full') and record['label']!='reference-full':
   n=record['label'].split('-')[0]; metadata['negative_controls'][n]['observed_host_failed_test_ids']=record.get('failed_test_ids',[])
 metadata['inventory_rule']='SHA-256 of every fixture file other than metadata.json itself. Private compressed host artifacts are included by archive hash; they are evidence only and never mounted. This is authoring inventory, not a frozen qualification claim.'
 metadata['sha256_inventory']={str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(base.rglob('*')) if p.is_file() and p.name!='metadata.json'}
 (base/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
 print(case,[(r['label'],r.get('executed_count'),r.get('failed_count'),r['exit_code']) for r in summary['records'] if r['label'].endswith('-full') or r['label']=='starting-public'])
 print(case,'inventory files',len(metadata['sha256_inventory']))
