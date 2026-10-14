# Workspace text export bundle

Implement exportTextBundle for the offline document app. Resolve the selected documents, produce the published deterministic text bundle and manifest, and commit the bundle with the injected atomic store. Preserve APIs and dependencies. Edit only lib/export_selection.dart, lib/export_encoding.dart and lib/export_service.dart. Run published checks.

All business rules below are decided. Implement the task within the three editable files. The provided repository is an offline Flutter package using only Flutter SDK and flutter_test SDK dependencies. Do not edit any other file, public test, model, adapter, manifest or dependency.

## Required behavior

R1: Request target workspace, bundleId, expected revision and ordered document IDs. Bundle/document IDs ASCII [A-Za-z0-9_-]{1,40}; selected IDs unique, count1..100, expected revision nonnegative integer. Invalid returns invalid_request/no document reads or writes after authorization; permission denial has precedence.

R2: Current identity requires export permission for target workspace; denial forbidden before any document content reads/writes. Load only exact requested IDs in target workspace and input order. Missing document returns not_found and creates no bundle. A reader returning wrong workspace/ID returns forbidden/no writes. Error messages are fixed public outcome strings without IDs, content or raw errors.

R3: Each exported document title0..80 and body0..100000 Dart UTF16 code units, ordinary Unicode and CR/LF preserved exactly. Encoding validates all selected records before any commit. New ID-derived path is exactly documents/<id>.txt, so no incoming filename/path is trusted. Invalid IDs including separators/dot paths/encoded traversal spellings are rejected by public ASCII grammar.

R4: File bytes are UTF8(body) exactly with no normalization or added LF. Manifest is UTF8 Dart jsonEncode of an insertion-ordered object with keys version=1, workspaceId, documents; each document keys id,title,path,byteLength in input order, followed by exactly one LF. byteLength means UTF8 bytes, not code units. No timestamps/randomness in serialized bytes.

R5: Bundle store snapshot uses request bundleId scoped to workspace. Its current revision is0 when absent. Compare expected revision before any no-op; mismatch conflict. If complete proposed manifest/files bytes equal current bundle, unchanged/current revision/no writes. Otherwise exactly one atomic compareAndReplace records entire bundle and revision+1 using original revision.

R6: False compare returns conflict and preserves old bundle; any reader/store/encoder exception maps documented storage_failure without raw text, with no partial commit. Atomic adapter rolls back failures. Existing different bundle IDs, unselected documents and other workspace data unchanged.

R7: An existing version1 bundle can be replaced/read by the published format; repeated same request on current revision is no-op, stale revision remains conflict. Deterministic complete public manifest/file compatibility checks are part of acceptance.

R8: Results are applied/Applied/new revision, unchanged/Unchanged/current revision, forbidden/Not allowed/null revision, invalid_request/Invalid export/null revision, not_found/Document unavailable/null revision, conflict/Export changed/null revision, storage_failure/Export unavailable/null revision. Normal record length/shape validation returns invalid_request before commit; unexpected encoder exceptions return storage_failure. Failure reports contain no document paths/content/identifiers. Successful report lists exported IDs/paths/byteLength in input order and matches stored bytes.

## Supplied API details

Call `exportTextBundle(request: ExportRequest(...), permissions: ..., reader: ..., store: ..., encoder: ...)`. The optional encoder is a synchronous injected function with the exact encodeTextBundle signature, defaulting to that function. Preserve supplied public signatures, immutable models, adapters/helpers and dependencies. `validExportRequest` is pure. `selectDocuments` resolves valid requests. `encodeTextBundle` returns null on normal shape/length validation failures and otherwise a deterministic TextBundle. PermissionProvider is a total nonthrowing dependency for the current identity's export access.

Workspace ID uses the same ASCII grammar as bundle/document IDs. Request workspace, bundle, revision and IDs are Object? to exercise dynamic invalid values. Permission is queried exactly once with the request workspace string, or empty string for a non-string target. Denial precedes request validation. Then validate the entire request before reader/store calls. Read requested documents sequentially in input order and stop at the first missing or foreign record: missing is not_found, wrong workspace or ID is forbidden. No store read follows these failures. Every selected record must pass title/body UTF16 length checks before the injected encoder is called. The encoder's null result means invalid_request and unexpected exceptions mean storage_failure. Empty title/body are valid.

Encoding uses requested order and derives paths exactly from validated IDs. Reports contain exactly `{id: <id>, path: documents/<id>.txt, byteLength: <UTF8 length>}`. Only successful applied/unchanged results have reports and revisions. The TextBundle files map has one file per selected ID, in request order, and exactly the manifest bytes described in R4. Null snapshot.bundle means absent and revision 0. Non-null snapshots have nonnegative revisions. Compare expected revision before byte equality, even when no bytes changed. Equality means exact manifest bytes and exact complete file path set and file bytes, independent of map insertion order. Ignore prior report fields when deciding byte equality. Unchanged reports are generated from the current proposed bundle. An old version1 bundle with byte-compatible data is supported directly.

Store load uses exactly request workspace/bundle. compareAndReplace is exactly one atomic whole-bundle CAS for changes, using snapshot revision, never retried after false. Its false or exception preserves all old bytes/revision. MemoryBundleStore throws only before staged data is published, exercising rollback. No document is mutated. Unselected documents, other bundle IDs and other workspaces are preserved. All error result strings and reports use the fixed published mapping. Plain body bytes have no added LF, manifest has exactly one added LF, and there are no generated clocks/random fields.

## Checks

Run `flutter pub get --offline`, `flutter analyze --no-pub`, and `flutter test --no-pub --machine test/contract_test.dart`. The protected public suite has exactly 12 declared tests, P01 through P12. All must complete successfully. No network/package installation or dependency changes are needed. Host preliminary evidence is separate from runtime qualification.
