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
  throw UnimplementedError('Implement the task contract');
}
