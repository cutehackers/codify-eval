Implement the offline atomic transfer batch feature described in repo/README.md.
Only lib/batch_service.dart and lib/batch_validator.dart may change. All other
starting files are protected. Keep the public signatures and use the supplied
store and authorization interfaces. The two starting modules compile but do not
implement the feature. Public smoke tests establish API compatibility, not completion.

Complete the documented behavior across validation, asynchronous authorization,
atomic persistence, repeat requests, conflicting request keys, concurrent calls,
and retries after uncertain store outcomes. Add no dependencies, UI, devices,
network calls, production integration, or changes outside the two allowed files.
