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
  test('public unchanged role does not write', () {
    final s = AccessStore();
    final r = changeAccountRole(manager, 'o', 'u', AccessRole.editor, 7, s);
    expect(r.outcome, AccessOutcome.unchanged); expect(s.writes, 0);
  });
}
