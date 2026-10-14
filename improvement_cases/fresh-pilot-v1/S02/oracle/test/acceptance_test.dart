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
  test('C1 denied malformed imports have no effects', () {
    for (final actor in [const ConfigurationActor('other', true),
                         const ConfigurationActor('w', false)]) {
      final s = ConfigStore();
      checkImport(importConfiguration(actor, 'w', [], s),
        ImportOutcome.forbidden, 'Not allowed');
      expect(s.calls, 0); expect(s.persisted, {'existing': 'keep'});
    }
  });
  test('C2 batch bounds and empty workspace', () {
    for (final entries in <List<ConfigurationEntry>>[[],
      List.generate(101, (i) => ConfigurationEntry('k$i', 'v'))]) {
      final s = ConfigStore();
      checkImport(importConfiguration(importer, 'w', entries, s),
        ImportOutcome.invalid, 'Invalid import'); expect(s.calls, 0);
    }
    final s = ConfigStore();
    checkImport(importConfiguration(const ConfigurationActor('', true), '',
      [const ConfigurationEntry('k', 'v')], s), ImportOutcome.invalid, 'Invalid import');
    expect(s.calls, 0);
  });
  test('C2 invalid key or late invalid value aborts whole batch', () {
    final badEntries = [const ConfigurationEntry('9bad', 'v'),
      const ConfigurationEntry('a-b', 'v'), const ConfigurationEntry('a.b', 'v'),
      const ConfigurationEntry('', 'v'),
      ConfigurationEntry(List.filled(33, 'a').join(), 'v'),
      const ConfigurationEntry('valid', '  '),
      const ConfigurationEntry('valid', 'x\ny'),
      const ConfigurationEntry('valid', 'x\ry'),
      ConfigurationEntry('valid', List.filled(121, 'x').join())];
    for (final bad in badEntries) {
      final s = ConfigStore();
      checkImport(importConfiguration(importer, 'w',
        [const ConfigurationEntry('good', 'v'), bad], s),
        ImportOutcome.invalid, 'Invalid import');
      expect(s.calls, 0); expect(s.persisted, {'existing': 'keep'});
    }
  });
  test('C3 normalized duplicates reject including same value', () {
    for (final value in ['first', 'second']) {
      final s = ConfigStore();
      checkImport(importConfiguration(importer, 'w',
        [const ConfigurationEntry(' Feature_A ', 'first'),
         ConfigurationEntry('feature_a', value)], s),
        ImportOutcome.invalid, 'Invalid import'); expect(s.calls, 0);
    }
  });
  test('C4 valid replacement normalizes and preserves inputs', () {
    final entries = [const ConfigurationEntry(' Feature_A ', '  One  '),
      const ConfigurationEntry('b', 'Case Sensitive')];
    final original = List.of(entries); final s = ConfigStore();
    checkImport(importConfiguration(importer, 'w', entries, s),
      ImportOutcome.applied, 'Imported', 2);
    expect(s.calls, 1); expect(s.workspace, 'w');
    expect(s.persisted, {'feature_a': 'One', 'b': 'Case Sensitive'});
    expect(entries, original); expect(entries.first.key, ' Feature_A ');
    expect(entries.first.value, '  One  ');
    expect(() => s.received!['injected'] = 'x', throwsUnsupportedError);
  });
  test('C2 inclusive maximums accepted', () {
    final entries = List.generate(100, (i) => ConfigurationEntry(
      'k$i', List.filled(120, 'v').join())); final s = ConfigStore();
    checkImport(importConfiguration(importer, 'w', entries, s),
      ImportOutcome.applied, 'Imported', 100);
    final s2 = ConfigStore();
    checkImport(importConfiguration(importer, 'w',
      [ConfigurationEntry(List.filled(32, 'a').join(), 'v')], s2),
      ImportOutcome.applied, 'Imported', 1);
  });
  test('C5 atomic store failure retains prior configuration and safe error', () {
    final s = ConfigStore()..fail = true;
    checkImport(importConfiguration(importer, 'w',
      [const ConfigurationEntry('api_key', 'secret')], s),
      ImportOutcome.failed, 'Import failed');
    expect(s.calls, 1); expect(s.persisted, {'existing': 'keep'});
  });
}
