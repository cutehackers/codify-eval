import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/implementation.dart';

class ConfigStore implements ConfigurationStore {
  int calls = 0;
  String? workspace;
  Map<String, String> persisted = {'existing': 'keep'};
  Map<String, String>? received;
  bool fail = false;
  @override
  void replaceAll(String workspaceId, Map<String, String> values) {
    calls++; workspace = workspaceId; received = values;
    if (fail) throw StateError('SECRET api_key tenant');
    persisted = Map.of(values);
  }
}
const importer = ConfigurationActor('w', true);
void checkImport(ImportResult r, ImportOutcome o, String message, [int count = 0]) {
  expect(r.outcome, o); expect(r.message, message); expect(r.count, count);
}
void main() {
  test('public single-entry import', () {
    final s = ConfigStore();
    final r = importConfiguration(importer, 'w',
      [const ConfigurationEntry('mode', 'safe')], s);
    expect(r.outcome, ImportOutcome.applied); expect(s.persisted, {'mode': 'safe'});
  });
}
