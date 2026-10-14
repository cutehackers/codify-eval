import 'package:flutter_test/flutter_test.dart';
import 'package:tenant_inventory_p02/archive_importer.dart';
import 'package:tenant_inventory_p02/contracts.dart';
import 'test_support.dart';

void main() {
  test('PUBLIC01 publishes complete files atomically', () async {
    final i = TestIntegrity();
    final s = MemoryStore();
    final files = {
      'docs/a.txt': [65, 66],
      'empty.txt': <int>[]
    };
    final text = manifest(i, files);
    final result = await ArchiveImporter(store: s, integrity: i)
        .import(text, i.tag(text), archive(files), Cancellation());
    expect(result.code, ImportCode.ok);
    expect(result.files, 2);
    expect(result.bytes, 2);
    expect(s.live, files);
    expect(s.stages, isEmpty);
  });
  test('PUBLIC02 invalid tag leaves existing publication intact', () async {
    final i = TestIntegrity();
    final s = MemoryStore();
    final text = manifest(i, {
      'a.txt': [1]
    });
    final result = await ArchiveImporter(store: s, integrity: i).import(
        text,
        'bad',
        archive({
          'a.txt': [1]
        }),
        Cancellation());
    expect(result.code, ImportCode.invalidManifest);
    expect(s.calls, isEmpty);
    expect(s.live, {
      'old.txt': [9]
    });
  });
}
