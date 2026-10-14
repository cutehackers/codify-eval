enum AccessRole { viewer, editor }
enum AccessOutcome { applied, unchanged, forbidden, missing, conflict }
class AccessActor {
  final String organizationId;
  final bool mayManageAccess;
  const AccessActor(this.organizationId, this.mayManageAccess);
}
class AccessAccount {
  final String id;
  final String organizationId;
  final AccessRole role;
  final int revision;
  final int sessionVersion;
  const AccessAccount(this.id, this.organizationId, this.role,
      this.revision, this.sessionVersion);
}
abstract class AccountStore {
  AccessAccount? load(String organizationId, String accountId);
  // An accepted write atomically updates role, revision and sessionVersion.
  bool compareAndSave(AccessAccount account, int expectedRevision);
}
class AccessResult {
  final AccessOutcome outcome;
  final String message;
  final int? revision;
  const AccessResult(this.outcome, this.message, [this.revision]);
}
AccessResult changeAccountRole(AccessActor actor, String organizationId,
    String accountId, AccessRole newRole, int expectedRevision, AccountStore store) {
  throw UnimplementedError('Implement the task contract');
}
