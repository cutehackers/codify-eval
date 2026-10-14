Development data only. No C1 candidate or prior failures informed this contract. Formatting/parser validation ran locally. Runtime qualification is pending with the root evaluator, which should use the pinned Flutter image and disabled network.

In a throwaway copy of repo, overlay either reference/lib or negative/<variant>/lib, then install oracle/test/acceptance_test.dart as test/acceptance_test.dart. Preserve public smoke tests. Run:

```sh
flutter pub get --offline
flutter test test/smoke_test.dart --reporter expanded
flutter test test/acceptance_test.dart --reporter expanded
flutter analyze --no-pub
```

Expected oracle outcomes: baseline semantic failure, reference pass, each negative semantic failure. Analyzer warnings in deliberately defective negative implementations do not replace behavioral failure evidence.

| Public requirement | Oracle assertions |
| --- | --- |
| Fresh independent permission decisions and denied calls with zero file work | permission is fresh; authorized queued calls |
| Identifiers and path rejection before policy/IO | invalid identifiers; file adapter rejects paths |
| Owner isolation, exact JSON identity/schema, body preservation, fresh disk reads | owner isolation; strict corrupt data |
| Invocation order, await persistence, queue recovery after errors | operations serialize; authorized queued calls |
| Real disk reopening, no temporary residue, missing-root error | disk roundtrip |
| UTF-8 decoding and non-file destination rejection | local adapter rejects invalid UTF-8 |
| Leaf symlink protection and existing protected target preservation | file adapter rejects paths and never follows symlink |
| Existing contents survive temporary write/flush errors, cleanup after errors, safe local exception text | temporary write and flush failures preserve destination |
| Rename failure cleanup and redaction | rename failure cleans temporary file |
| Safe fixed error strings for storage and access failures | permission is fresh; strict corrupt data; operations serialize; disk roundtrip |

Negative variants: no_authorization bypasses policy, no_identity_validation accepts cross-owner/cross-id content, unordered_operations bypasses sequencing, follow_symlinks follows leaf symbolic links. no_temporary_cleanup leaves failed-operation residue and delete_destination_early deletes the destination before a failing temporary write. Each contains the full lib tree.

Limitations: Linux/macOS filesystem and in-process repository ordering only. Atomic replacement is implemented as flushed temporary write plus same-directory rename. The public DocumentFileOperations seam fault-injects partial writes, flush errors and rename errors. The oracle checks destination preservation, same-root temporary paths, flush requests, cleanup and fixed error text without depending on temporary filename spelling. No concurrent hostile filesystem actor, cross-process locking, GUI, device, production storage or crash/power-loss durability claim is made. No runtime pass is claimed before root qualification.
