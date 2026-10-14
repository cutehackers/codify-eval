import 'dart:convert';
import 'package:crypto/crypto.dart';
import 'package:tenant_inventory_p02/contracts.dart';

class TestIntegrity implements Integrity {
  int verifies = 0;
  int hashes = 0;
  String tag(String text) =>
      sha256.convert(utf8.encode('fixture:$text')).toString();
  @override
  bool verifyManifest(String text, String value) {
    verifies++;
    return tag(text) == value;
  }

  @override
  String sha256Hex(List<int> bytes) {
    hashes++;
    return sha256.convert(bytes).toString();
  }
}

String manifest(TestIntegrity integrity, Map<String, List<int>> files) =>
    jsonEncode({
      'version': 1,
      'files': [
        for (final e in files.entries)
          {
            'path': e.key,
            'size': e.value.length,
            'digest': sha256.convert(e.value).toString()
          }
      ]
    });
Stream<ArchiveEntry> archive(Map<String, List<int>> files) =>
    Stream.fromIterable([
      for (final e in files.entries)
        ArchiveEntry(e.key, 'file', Stream.value(e.value))
    ]);

class MemoryStore implements ImportStore {
  Map<String, List<int>> live = {
    'old.txt': [9]
  };
  final Map<String, Map<String, List<int>>> stages = {};
  final List<String> calls = [];
  final List<List<int>> writeInputs = [];
  String? fail;
  Future<void> Function(String operation)? hook;
  int serial = 0;
  Future<void> before(String op) async {
    calls.add(op);
    if (hook != null) await hook!(op);
    if (fail == op) throw StorageUnavailable();
  }

  @override
  Future<String> begin() async {
    await before('begin');
    final id = 's${serial++}';
    stages[id] = {};
    return id;
  }

  @override
  Future<void> write(String stage, String path, List<int> chunk) async {
    writeInputs.add(chunk);
    await before('write');
    (stages[stage]![path] ??= []).addAll(chunk);
  }

  @override
  Future<void> publish(String stage) async {
    await before('publish');
    live = stages.remove(stage)!;
  }

  @override
  Future<void> rollback(String stage) async {
    calls.add('rollback');
    if (hook != null) await hook!('rollback');
    stages.remove(stage);
  }
}
