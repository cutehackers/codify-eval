import 'models.dart';
import 'search_codec.dart';
import 'search_plan.dart';

Outcome importSavedSearches({required Object? targetWorkspaceId, required Object? expectedRevision,
    required String jsonText, required PermissionProvider permissions, required SearchStore store}) {
  // Permission identity comes from the injected provider, never the payload.
  permissions.canAccess(targetWorkspaceId is String ? targetWorkspaceId : '');
  if (!validId(targetWorkspaceId) || !validRevision(expectedRevision)) return Outcome('invalid_import', null);
  ImportData? data;
  try { data = decodeSearchImport(decodePortableJson(jsonText)); }
  on DecodeFailure { return Outcome('invalid_import', null); }
  if (data == null || data.workspaceId != targetWorkspaceId) return Outcome('invalid_import', null);
  try {
    final snapshot = store.load(targetWorkspaceId as String);
    for (final entry in snapshot.records.entries) {
      if (entry.value.workspaceId != targetWorkspaceId || entry.value.id != entry.key || !validId(entry.key)) return Outcome('forbidden', null);
    }
    if (snapshot.revision != expectedRevision) return Outcome('conflict', null);
    final plan = planSearchImport(data, snapshot);
    if (plan.effects.isEmpty) return Outcome('unchanged', snapshot.revision, plan.report);
    if (!store.compareAndApply(targetWorkspaceId, snapshot.revision, plan.effects)) return Outcome('conflict', null);
    return Outcome('applied', snapshot.revision + 1, plan.report);
  } catch (_) { return Outcome('storage_failure', null); }
}
