# Tenant document commands

This is an offline Flutter service package for a collaborative document workspace. The public API is in
`lib/implementation.dart`. Implement only that file and preserve its declarations.
There is no network, UI, persistence SDK, or clock dependency. Injected repository
interfaces expose observable effects. Tests use in-memory fakes.

Run `flutter test test/public_smoke_test.dart` for the public smoke test.
The complete acceptance contract is supplied in `task.md` outside this repository.
The smoke test is intentionally incomplete and is not proof of task completion.
