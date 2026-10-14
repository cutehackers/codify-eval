import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/implementation.dart';

class AccessStore implements AccountStore {
  AccessAccount? record = const AccessAccount('u', 'o', AccessRole.editor, 7, 12);
  int reads = 0, writes = 0;
  String? organization, id;
  int? expected;
  bool accepted = true, throwRead = false, throwWrite = false;
  @override
  AccessAccount? load(String organizationId, String accountId) {
    reads++; organization = organizationId; id = accountId;
    if (throwRead) throw StateError('SECRET session account');
    return record;
  }
  @override
  bool compareAndSave(AccessAccount account, int expectedRevision) {
    writes++; expected = expectedRevision;
    if (throwWrite) throw StateError('SECRET session account');
    if (!accepted) return false;
    record = account; return true;
  }
}
const manager = AccessActor('o', true);
void checkAccess(AccessResult r, AccessOutcome o, String msg, [int? revision]) {
  expect(r.outcome, o); expect(r.message, msg); expect(r.revision, revision);
}
void main() {
  test('A1 denial precedes validation and has no store effects', () {
    for (final actor in [const AccessActor('x', true), const AccessActor('o', false)]) {
      final s = AccessStore();
      checkAccess(changeAccountRole(actor, 'o', '', AccessRole.viewer, -1, s),
        AccessOutcome.forbidden, 'Not allowed'); expect([s.reads, s.writes], [0, 0]);
      expect(s.record!.sessionVersion, 12);
    }
  });
  test('A2 invalid request no lookup', () {
    for (final input in [('', 'u', 7), ('o', '', 7), ('o', 'u', -1)]) {
      final s = AccessStore();
      checkAccess(changeAccountRole(AccessActor(input.$1, true), input.$1,
        input.$2, AccessRole.viewer, input.$3, s), AccessOutcome.conflict, 'Access changed');
      expect(s.reads, 0); expect(s.writes, 0);
    }
  });
  test('A2 exact scoped load and missing account', () {
    final s = AccessStore()..record = null;
    checkAccess(changeAccountRole(manager, 'o', 'u', AccessRole.viewer, 7, s),
      AccessOutcome.missing, 'Account unavailable');
    expect([s.organization, s.id], ['o', 'u']); expect(s.writes, 0);
  });
  test('A2 mis-scoped records cannot be written', () {
    for (final record in [const AccessAccount('u', 'x', AccessRole.editor, 7, 12),
                         const AccessAccount('other', 'o', AccessRole.editor, 7, 12)]) {
      final s = AccessStore()..record = record;
      checkAccess(changeAccountRole(manager, 'o', 'u', AccessRole.viewer, 7, s),
        AccessOutcome.forbidden, 'Not allowed'); expect(s.writes, 0);
    }
  });
  test('A3 stale no-op still conflicts', () {
    final s = AccessStore();
    checkAccess(changeAccountRole(manager, 'o', 'u', AccessRole.editor, 6, s),
      AccessOutcome.conflict, 'Access changed'); expect(s.writes, 0);
  });
  test('A3 no-op preserves session and revision without writes', () {
    final s = AccessStore(); final original = s.record;
    checkAccess(changeAccountRole(manager, 'o', 'u', AccessRole.editor, 7, s),
      AccessOutcome.unchanged, 'Unchanged', 7);
    expect(s.writes, 0); expect(identical(s.record, original), true);
  });
  test('A4 resolved downgrade invalidates sessions atomically once', () {
    final s = AccessStore(); final original = s.record;
    checkAccess(changeAccountRole(manager, 'o', 'u', AccessRole.viewer, 7, s),
      AccessOutcome.applied, 'Applied', 8);
    expect([s.reads, s.writes, s.expected], [1, 1, 7]);
    expect(s.record!.role, AccessRole.viewer); expect(s.record!.sessionVersion, 13);
    expect(original!.role, AccessRole.editor); expect(original.sessionVersion, 12);
    expect(original.revision, 7);
  });
  test('A4 promotion preserves sessions', () {
    final s = AccessStore()..record = const AccessAccount('u', 'o', AccessRole.viewer, 2, 40);
    checkAccess(changeAccountRole(manager, 'o', 'u', AccessRole.editor, 2, s),
      AccessOutcome.applied, 'Applied', 3);
    expect(s.writes, 1); expect(s.record!.sessionVersion, 40);
  });
  test('A5 compare failure and exceptions are safe and preserve state', () {
    for (final s in [AccessStore()..accepted = false,
                    AccessStore()..throwRead = true, AccessStore()..throwWrite = true]) {
      checkAccess(changeAccountRole(manager, 'o', 'u', AccessRole.viewer, 7, s),
        AccessOutcome.conflict, 'Access changed');
      expect(s.record!.role, AccessRole.editor); expect(s.record!.sessionVersion, 12);
    }
  });
}
