from pathlib import Path
import json,hashlib
B=Path(__file__).resolve().parent.parent
root=B.parent.parent
sources=['AGENTS.md','docs/improvement-spec-v1.md','results/improvement-v1/fresh-optional-orchestration-design-v1.json']
design=json.loads((root/sources[2]).read_text())
source_hash={s:hashlib.sha256((root/s).read_bytes()).hexdigest() for s in sources}
for c,n in [('O01',0),('O02',1)]:
 base=B/c;proposal=design['software_task_proposals'][n]
 editable=['lib/'+f.name for f in sorted((base/'private/reference/lib').iterdir())]
 rules='\n\n'.join('R'+str(i+1)+': '+r for i,r in enumerate(proposal['public_acceptance']))
 if c=='O01':
  detail='''Call `importSavedSearches(targetWorkspaceId: ..., expectedRevision: ..., jsonText: ..., permissions: ..., store: ...)`. Requests use Object? for target/revision so invalid dynamic values can be rejected. `decodeSearchImport(Object?)` returns null for invalid schema, `encodeSearchExport(ImportData)` exports valid canonical data, and `planSearchImport(ImportData, SearchSnapshot)` is pure. Service handles protected `DecodeFailure`. Preserve every supplied public signature, immutable model, adapter, helper, and dependency.

The ID grammar also applies to payload workspaceId. JSON null, array roots, boolean/double version or revision, extra/missing keys and metadata fields are invalid. Exactly the published key sets are permitted. JSON key order on input is irrelevant. Dart String.length measures UTF16 units. New rows get createdAt exactly `imported`; updates keep prior createdAt. Reports contain exactly maps `{id: <id>, action: inserted|updated|unchanged}`. A no-op may have nonempty unchanged-row reports. A failed import has no report and no revision.

PermissionProvider represents the current identity's edit access and is queried exactly once with the request target string. If the target is not a String, pass the empty string to the provider and apply denial precedence before invalid_import. Provider itself is a total nonthrowing dependency. After permission, validate target/revision, then decode/validate payload scope/schema, then load the target snapshot. Check all returned snapshot entries, including unlisted ones, for workspace mismatch, record-ID/map-key mismatch or invalid map-key grammar. Such foreign entries produce forbidden before the revision check. Snapshot revisions supplied by adapters are nonnegative integers. Only imported IDs participate in effects.

SearchStore.load is read-only. compareAndApply owns an atomic transaction: on false or throw, it leaves the entire prior snapshot untouched. MemorySearchStore can reject CAS or throw after staging to exercise this contract. Plan effects omit unchanged rows and preserve input order. Service does not retry false CAS, does not bypass it, and calls exactly once for nonempty effects. Unexpected store exceptions produce storage_failure. No normalization, trimming, sorting, or Unicode code-point length restriction is allowed. Encode uses Dart jsonEncode and exactly one appended LF. The exported text can be imported without loss.'''
 else:
  detail='''Call `exportTextBundle(request: ExportRequest(...), permissions: ..., reader: ..., store: ..., encoder: ...)`. The optional encoder is a synchronous injected function with the exact encodeTextBundle signature, defaulting to that function. Preserve supplied public signatures, immutable models, adapters/helpers and dependencies. `validExportRequest` is pure. `selectDocuments` resolves valid requests. `encodeTextBundle` returns null on normal shape/length validation failures and otherwise a deterministic TextBundle. PermissionProvider is a total nonthrowing dependency for the current identity's export access.

Workspace ID uses the same ASCII grammar as bundle/document IDs. Request workspace, bundle, revision and IDs are Object? to exercise dynamic invalid values. Permission is queried exactly once with the request workspace string, or empty string for a non-string target. Denial precedes request validation. Then validate the entire request before reader/store calls. Read requested documents sequentially in input order and stop at the first missing or foreign record: missing is not_found, wrong workspace or ID is forbidden. No store read follows these failures. Every selected record must pass title/body UTF16 length checks before the injected encoder is called. The encoder's null result means invalid_request and unexpected exceptions mean storage_failure. Empty title/body are valid.

Encoding uses requested order and derives paths exactly from validated IDs. Reports contain exactly `{id: <id>, path: documents/<id>.txt, byteLength: <UTF8 length>}`. Only successful applied/unchanged results have reports and revisions. The TextBundle files map has one file per selected ID, in request order, and exactly the manifest bytes described in R4. Null snapshot.bundle means absent and revision 0. Non-null snapshots have nonnegative revisions. Compare expected revision before byte equality, even when no bytes changed. Equality means exact manifest bytes and exact complete file path set and file bytes, independent of map insertion order. Ignore prior report fields when deciding byte equality. Unchanged reports are generated from the current proposed bundle. An old version1 bundle with byte-compatible data is supported directly.

Store load uses exactly request workspace/bundle. compareAndReplace is exactly one atomic whole-bundle CAS for changes, using snapshot revision, never retried after false. Its false or exception preserves all old bytes/revision. MemoryBundleStore throws only before staged data is published, exercising rollback. No document is mutated. Unselected documents, other bundle IDs and other workspaces are preserved. All error result strings and reports use the fixed published mapping. Plain body bytes have no added LF, manifest has exactly one added LF, and there are no generated clocks/random fields.'''
 public=base/'public';public.mkdir(parents=True,exist_ok=True)
 (public/'request.md').write_text(f'''# {proposal['title']}

{proposal['public_request']}

All business rules below are decided. Implement the task within the three editable files. The provided repository is an offline Flutter package using only Flutter SDK and flutter_test SDK dependencies. Do not edit any other file, public test, model, adapter, manifest or dependency.

## Required behavior

{rules}

## Supplied API details

{detail}

## Checks

Run `flutter pub get --offline`, `flutter analyze --no-pub`, and `flutter test --no-pub --machine test/contract_test.dart`. The protected public suite has exactly 12 declared tests, P01 through P12. All must complete successfully. No network/package installation or dependency changes are needed. Host preliminary evidence is separate from runtime qualification.
''')
 mappings=[]
 # Explicit fully public contract is source of each check; test names retained for provenance.
 tests={'public':base/'repo/test/contract_test.dart','private':base/'private/acceptance_test.dart'}
 import re
 for visibility,path in tests.items():
  for i,name in enumerate(re.findall(r'test\("([^"]+)"',path.read_text()),1):
   mappings.append({'check':name.split(' ')[0],'visibility':visibility,'purpose':name,'public_source':'public/request.md','rules':'R1-R'+str(len(proposal['public_acceptance']))+' and Supplied API details','assertions_source':str(path.relative_to(base))})
 metadata={'version':'fresh-optional-cohort-v1','case_id':c,'title':proposal['title'],'status':'authored_unqualified','design_proposal_id':proposal['id'],'retained_regardless_of_baseline_outcome':True,'editable_paths':editable,'public_test_count':12,'private_test_count':12,'combined_test_count':24,'reference_implementation_file_count':3,'negative_control_count':4,'negative_implementation_files_per_control':3,'negative_controls':sorted(p.name for p in (base/'private/negative_controls').iterdir()),'source_hashes':source_hash,'source_access':sources,'actor_mount_allowlist':['public/request.md','repo/'],'private_mount_forbidden':['private/','metadata.json','authoring-provenance.json'],'qualification':{'qualified':False,'frozen':False,'difficulty_established':False,'model_run_performed':False,'superiority_claimed':False},'provenance_mapping':mappings,'public_contract_clarifications_are_published':True,'verification':'Host preliminary only, final evidence is in private/host_evidence/commands.json. No pristine container/model qualification performed.'}
 (base/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
 provenance={'author_context':'source_blind_independent_optional_orchestration_fixture_author','read_sources':source_hash,'read_other_fixture_or_reference_or_model_answers':False,'business_rules_source':proposal['id'],'generated_owned_files_only':True,'private_test_policies':'Every assertion maps to public/request.md, including supplied API details; no unpublished business judgment.','controls':'Each whole three-file negative equals reference except one independent category fault documented in fault.json.','preservation':'Initial failures and all preliminary logs are immutable evidence. Both proposals retained; runtime implementation owned by root.','runtime_limits':'No Docker, models, network, installation or runtime implementation.'}
 (base/'authoring-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
