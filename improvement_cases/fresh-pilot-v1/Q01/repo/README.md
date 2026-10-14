# Managed account role changes

This offline Flutter package contains a service with injected, in-memory-testable
repository interfaces. Public types and API are in `lib/implementation.dart`.
Implement only that file and preserve its declarations. There are no network,
UI, persistence SDK, or clock dependencies.

Run `flutter test test/public_smoke_test.dart`. This public smoke is intentionally
incomplete. The full acceptance contract is in the separately supplied `task.md`.
