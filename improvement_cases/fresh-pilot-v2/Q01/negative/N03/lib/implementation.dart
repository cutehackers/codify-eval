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
  if (!actor.mayManageAccess) {
    return const AccessResult(AccessOutcome.forbidden, 'Not allowed');
  }
  if (organizationId.isEmpty || accountId.isEmpty || expectedRevision < 0) {
    return const AccessResult(AccessOutcome.conflict, 'Access changed');
  }
  try {
    final current = store.load(organizationId, accountId);
    if (current == null) {
      return const AccessResult(AccessOutcome.missing, 'Account unavailable');
    }
    if (current.id != accountId || current.organizationId != organizationId) {
      return const AccessResult(AccessOutcome.forbidden, 'Not allowed');
    }
    if (current.revision != expectedRevision) {
      return const AccessResult(AccessOutcome.conflict, 'Access changed');
    }
    if (current.role == newRole) {
      return AccessResult(AccessOutcome.unchanged, 'Unchanged', current.revision);
    }
    final downgrade = current.role == AccessRole.editor && newRole == AccessRole.viewer;
    final next = AccessAccount(current.id, current.organizationId, newRole,
        current.revision + 1, current.sessionVersion + (downgrade ? 1 : 0));
    if (!store.compareAndSave(next, expectedRevision)) {
      return const AccessResult(AccessOutcome.conflict, 'Access changed');
    }
    return AccessResult(AccessOutcome.applied, 'Applied', next.revision);
  } catch (_) {
    return const AccessResult(AccessOutcome.conflict, 'Access changed');
  }
}
