from pathlib import Path
import json,hashlib,re,os
B=Path(__file__).resolve().parent.parent
rulemap={
'O01':{'P01':[5,6],'P02':[3,4],'P03':[1,3,4],'P04':[1,7],'P05':[5,6],'P06':[2,6],'P07':[1,2],'P08':[5],'P09':[3,6],'P10':[2],'P11':[1,2],'P12':[3,5], 'R01':[3,4],'R02':[5,6],'R03':[2,6],'R04':[1,3],'R05':[1],'R06':[5,6],'R07':[1,7],'R08':[7],'R09':[5,6],'R10':[6],'R11':[4],'R12':[1,3]},
'O02':{'P01':[2,3,4,8],'P02':[1,2],'P03':[1,3],'P04':[2],'P05':[2],'P06':[5,7],'P07':[5,6],'P08':[3,8],'P09':[6,8],'P10':[3,4],'P11':[6],'P12':[1,2], 'R01':[1,2],'R02':[1,3],'R03':[2,6],'R04':[2],'R05':[3,4,8],'R06':[1,3,4],'R07':[5,7,8],'R08':[5,7],'R09':[5,6],'R10':[8],'R11':[5],'R12':[3,8]}}
for c in ['O01','O02']:
 b=B/c;m=json.loads((b/'metadata.json').read_text());records=[]
 for attempt in sorted((b/'private/host_evidence').glob('attempt-*')):
  record_path=attempt/'commands.json'
  if not record_path.exists():continue
  for record in json.loads(record_path.read_text()):
   record['_attempt']=attempt.name
   records.append(record)
 names={}
 for test_path in [b/'repo/test/contract_test.dart',b/'private/acceptance_test.dart']:
  names.update({name.split(' ')[0]:name for name in re.findall(r'test\(\"([^\"]+)\"',test_path.read_text())})
 for p in m['provenance_mapping']:
  p['purpose']=names[p['check']]
  p['rules']=['R'+str(i) for i in rulemap[c][p['check']]]
  p['public_api_details']='Supplied API details in public/request.md'
 m['verification']='Host-only offline preliminary checks; see private/host_summary.json and immutable per-attempt stdout/stderr/commands. Not container/runtime/model qualification.'
 summary={}
 for r in records:
  label=r['label']
  raw=[]
  for line in (b/'private/host_evidence'/r['_attempt']/(label+'.stdout')).read_text().splitlines():
   try:
    event=json.loads(line)
    if isinstance(event,dict) and event.get('type')=='testDone' and not event.get('hidden',False):raw.append(event)
   except ValueError:pass
  r['failed_test_events']=sum(e.get('result') in ['error','failure'] for e in raw)
  summary[label]={k:r[k] for k in ['exit_status','completed_test_events','successful_test_events','failed_test_events']}
  summary[label]['count_derivation']='Recount from retained original machine stdout; error and failure both count as failures.'
  summary[label]['evidence_attempt']=r['_attempt']
  summary[label]['source_sha256']=r['source_sha256']
  if label.startswith('negative_'):
   events=[]
   for line in (b/'private/host_evidence'/r['_attempt']/(label+'.stdout')).read_text().splitlines():
    try:
     e=json.loads(line)
     if isinstance(e,dict):events.append(e)
    except ValueError:pass
   names={e['test']['id']:e['test']['name'] for e in events if e.get('type')=='testStart'}
   summary[label]['failed_tests']=[names.get(e.get('testID')) for e in events if e.get('type')=='testDone' and e.get('result') in ['error','failure']]
   assert r['exit_status']!=0 and r['completed_test_events']==24 and r['failed_test_events']>0
 (b/'private/host_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 m['host_preliminary_results']=summary;m['remaining_issues']=['Pristine image start/reference/negative qualification and source-bound independent review remain root-owned.','No model behavior, optional runtime, difficulty or superiority claim is established.']
 if c=='O01':m['remaining_issues'].append('Author harness attempt-v1 failed while parsing mixed machine JSON. Original logs/cache retained; test exit status was not persisted in that attempt. Attempt-v2 completed with exact test counts.')
 # Public tree must contain only provided stubs, protected models, config, tests.
 assert not (b/'repo/test/author_acceptance_test.dart').exists()
 for f in m['editable_paths']:assert 'UnimplementedError' in (b/'repo'/f).read_text()
 assert len(re.findall(r'\btest\(', (b/'repo/test/contract_test.dart').read_text()))==12
 assert len(re.findall(r'\btest\(', (b/'private/acceptance_test.dart').read_text()))==12
 # Verify control is exactly one altered file, the other two byte-identical.
 for control in sorted((b/'private/negative_controls').iterdir()):
  differences=[f for f in m['editable_paths'] if (control/f).read_bytes()!=(b/'private/reference'/f).read_bytes()]
  assert len(differences)==1,(c,control,differences)
 # No fixture secrets or generated host cache in actor tree.
 allowed={'analysis_options.yaml','pubspec.yaml','lib/models.dart','test/contract_test.dart',*m['editable_paths']}
 assert {str(p.relative_to(b/'repo')) for p in (b/'repo').rglob('*') if p.is_file()}==allowed
 m['actor_repository_file_count']=len(allowed);m['actor_mount_file_count']=len(allowed)+1
 (b/'metadata.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 # Freeze originals after all preliminary activity and inventory byte hashes plus modes.
 for folder in ['private/host_evidence','private/host_archive']:
  for p in (b/folder).rglob('*'):
   if p.is_file() and not p.is_symlink():p.chmod(0o444)
 entries=[]
 for p in sorted(b.rglob('*')):
  if p.name=='sha256-inventory.json':continue
  if p.is_symlink():entries.append({'path':str(p.relative_to(b)),'type':'symlink','target':os.readlink(p),'mode':oct(p.lstat().st_mode&0o777)})
  elif p.is_file():entries.append({'path':str(p.relative_to(b)),'type':'file','bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mode':oct(p.stat().st_mode&0o777)})
 inv={'version':'current-authored-v1','status':'authored_unqualified','excludes_self_hash':True,'file_and_symlink_count_excluding_inventory':len(entries),'file_and_symlink_count_including_inventory':len(entries)+1,'includes_all_private_archives':True,'entries':entries}
 (b/'sha256-inventory.json').write_text(json.dumps(inv,indent=2)+'\n')
 print(c,json.dumps(summary), 'inventory',len(entries)+1)
