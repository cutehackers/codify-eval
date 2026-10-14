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
| Initial state, trim, loading/ready transitions, empty result, immutable snapshots | initial, normalized request, exact transitions and defensive snapshot |
| Newest request, same-query overlap, stale success/failure | newest invocation wins; different-query stale success |
| Error redaction, retry target and no-op retry | different-query stale success; empty input |
| Empty query invalidation | empty input invalidates pending work |
| Exact failed/retry-failed transitions and redaction | current failure and retry failure each notify exactly once |
| Dispose idempotence, no notifications/state writes/service calls, consumed errors | dispose blocks state writes |

Negative variants: no_generation removes request ordering, retry_noop disables failure retry, dispose_state_write allows disposed completions to publish. empty_without_notification omits the empty-input notification and noop_retry_notification emits during a no-op retry. Each contains the full lib tree.

Limitations: service/controller behavior only. No actual GUI, navigation, device, accessibility or production-provider validation. No runtime pass is claimed before root qualification.

No-op tests inspect service calls/state/notification counts before awaiting futures. Completion waits are bounded separately, and Controlled requests are released on teardown. A timeout alone is not semantic negative qualification evidence.
