enum ImportOutcome { applied, forbidden, invalid, failed }
class ConfigurationActor {
  final String workspaceId;
  final bool mayImport;
  const ConfigurationActor(this.workspaceId, this.mayImport);
}
class ConfigurationEntry {
  final String key;
  final String value;
  const ConfigurationEntry(this.key, this.value);
}
abstract class ConfigurationStore {
  // Implementations atomically replace or throw without changing persisted state.
  void replaceAll(String workspaceId, Map<String, String> values);
}
class ImportResult {
  final ImportOutcome outcome;
  final String message;
  final int count;
  const ImportResult(this.outcome, this.message, [this.count = 0]);
}
ImportResult importConfiguration(ConfigurationActor actor, String workspaceId,
    List<ConfigurationEntry> entries, ConfigurationStore store) {
  if (!actor.mayImport || actor.workspaceId != workspaceId) {
    return const ImportResult(ImportOutcome.forbidden, 'Not allowed');
  }
  if (workspaceId.isEmpty || entries.isEmpty || entries.length > 100) {
    return const ImportResult(ImportOutcome.invalid, 'Invalid import');
  }
  final staged = <String, String>{};
  final keyPattern = RegExp(r'^[a-z][a-z0-9_]{0,31}$');
  for (final entry in entries) {
    final key = entry.key.trim().toLowerCase();
    final value = entry.value.trim();
    if (!keyPattern.hasMatch(key) || value.isEmpty || value.length > 120 ||
        value.contains('\n') || value.contains('\r') ||
        staged.containsKey(key)) {
      return const ImportResult(ImportOutcome.invalid, 'Invalid import');
    }
    staged[key] = value;
  }
  try {
    store.replaceAll(workspaceId, Map<String, String>.unmodifiable(staged));
    return ImportResult(ImportOutcome.applied, 'Imported', staged.length);
  } catch (_) {
    return const ImportResult(ImportOutcome.failed, 'Import failed');
  }
}
