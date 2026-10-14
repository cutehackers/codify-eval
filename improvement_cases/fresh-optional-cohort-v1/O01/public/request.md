# Workspace saved-search import

Implement importSavedSearches for an offline workspace app. Support the two published portable formats, build a validated import plan, and apply it atomically using the injected store. Preserve supplied APIs and dependencies. Edit only lib/search_codec.dart, lib/search_plan.dart and lib/search_import_service.dart. Run the published checks.

All business rules below are decided. Implement the task within the three editable files. The provided repository is an offline Flutter package using only Flutter SDK and flutter_test SDK dependencies. Do not edit any other file, public test, model, adapter, manifest or dependency.

## Required behavior

R1: Input is a decoded JSON object with exact version/workspaceId/collection keys. v1 collection searches rows{id,label,query}; v2 collection items rows{id,title,expression}. Versions exactly integer1/2 map label->title/query->expression without normalization. Required field types are exact, unknown fields invalid. Invalid decoder/malformed JSON becomes invalid_import. The supplied protected decoder rejects duplicate JSON object keys and malformed JSON; the service maps its declared decode failure to invalid_import. Codec/service cannot invent normalization or extra schema restrictions.

R2: At most100 rows; each ID ASCII [A-Za-z0-9_-]{1,40}, unique. Title1..80 and expression1..2000 Dart UTF16 code units; ordinary Unicode/whitespace preserved exactly. Empty collection valid no-op. All boundary constants/types public.

R3: Target workspace ID uses the same ASCII ID grammar; expected revision must be a nonnegative integer. After permission denial precedence, invalid target/revision returns invalid_import before storage reads. Results are applied/Applied/new revision, unchanged/Unchanged/current revision, forbidden/Not allowed/null revision, invalid_import/Invalid import/null revision, conflict/Import changed/null revision, storage_failure/Import unavailable/null revision. Reports are empty on failures; success/no-op report canonical rows in input order. No extra error details.

R4: Permission provider current identity must have edit access to target workspace. Denial returns forbidden before store content reads/writes. After authorization, payload workspace must equal target, else invalid_import before store reads. Schema validation then precedes store reads; malformed plus unauthorized follows forbidden precedence. Never use payload identity for access.

R5: Store reads only target workspace. Any returned record with wrong workspace or ID returns forbidden/no writes. New IDs insert; equal title/expression remain unchanged/no rewrite; differing IDs replace title/expression but retain existing createdAt metadata. Imported rows cannot set metadata. Report inserted/updated/unchanged IDs once in input order. Unlisted records and other workspaces unchanged.

R6: Load target revision, compare expected request revision before no-op. Mismatch returns conflict without writes. Nonempty effects use exactly one atomic compareAndApply with original revision; success increments workspace revision once, no-op returns unchanged current revision and no transaction. False compare returns conflict/no effects. Store exceptions return storage_failure/no raw text; injected transaction owns rollback.

R7: v1 and equivalent v2 produce identical canonical effects/reports. Encode exported canonical data using v2, fixed key order version/workspaceId/items then row id/title/expression, Dart jsonEncode semantics plus one LF. Integration round-trip preserves content and stable ordering.

## Supplied API details

Call `importSavedSearches(targetWorkspaceId: ..., expectedRevision: ..., jsonText: ..., permissions: ..., store: ...)`. Requests use Object? for target/revision so invalid dynamic values can be rejected. `decodeSearchImport(Object?)` returns null for invalid schema, `encodeSearchExport(ImportData)` exports valid canonical data, and `planSearchImport(ImportData, SearchSnapshot)` is pure. Service handles protected `DecodeFailure`. Preserve every supplied public signature, immutable model, adapter, helper, and dependency.

The ID grammar also applies to payload workspaceId. JSON null, array roots, boolean/double version or revision, extra/missing keys and metadata fields are invalid. Exactly the published key sets are permitted. JSON key order on input is irrelevant. Dart String.length measures UTF16 units. New rows get createdAt exactly `imported`; updates keep prior createdAt. Reports contain exactly maps `{id: <id>, action: inserted|updated|unchanged}`. A no-op may have nonempty unchanged-row reports. A failed import has no report and no revision.

PermissionProvider represents the current identity's edit access and is queried exactly once with the request target string. If the target is not a String, pass the empty string to the provider and apply denial precedence before invalid_import. Provider itself is a total nonthrowing dependency. After permission, validate target/revision, then decode/validate payload scope/schema, then load the target snapshot. Check all returned snapshot entries, including unlisted ones, for workspace mismatch, record-ID/map-key mismatch or invalid map-key grammar. Such foreign entries produce forbidden before the revision check. Snapshot revisions supplied by adapters are nonnegative integers. Only imported IDs participate in effects.

SearchStore.load is read-only. compareAndApply owns an atomic transaction: on false or throw, it leaves the entire prior snapshot untouched. MemorySearchStore can reject CAS or throw after staging to exercise this contract. Plan effects omit unchanged rows and preserve input order. Service does not retry false CAS, does not bypass it, and calls exactly once for nonempty effects. Unexpected store exceptions produce storage_failure. No normalization, trimming, sorting, or Unicode code-point length restriction is allowed. Encode uses Dart jsonEncode and exactly one appended LF. The exported text can be imported without loss.

## Checks

Run `flutter pub get --offline`, `flutter analyze --no-pub`, and `flutter test --no-pub --machine test/contract_test.dart`. The protected public suite has exactly 12 declared tests, P01 through P12. All must complete successfully. No network/package installation or dependency changes are needed. Host preliminary evidence is separate from runtime qualification.
