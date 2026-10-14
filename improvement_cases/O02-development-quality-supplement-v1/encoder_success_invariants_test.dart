import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:o02_fixture/export_service.dart';
import 'package:o02_fixture/models.dart';

const _documents = [
  Document('w', 'z', 'Z', '한글😀\r\n'),
  Document('w', 'a', 'A', 'hello'),
];

// Expected bytes come from the public format, never the implementation encoder.
TextBundle _publishedBundle() {
  final files = <String, List<int>>{};
  final entries = <Map<String, Object>>[];
  final report = <Map<String, Object>>[];
  for (final document in _documents) {
    final path = 'documents/${document.id}.txt';
    final bytes = utf8.encode(document.body);
    files[path] = bytes;
    entries.add({
      'id': document.id,
      'title': document.title,
      'path': path,
      'byteLength': bytes.length,
    });
    report.add({'id': document.id, 'path': path, 'byteLength': bytes.length});
  }
  return TextBundle(
    utf8.encode('${jsonEncode({
      'version': 1,
      'workspaceId': 'w',
      'documents': entries,
    })}\n'),
    files,
    report,
  );
}

MemoryDocumentReader _reader() {
  final reader = MemoryDocumentReader();
  for (final document in _documents) {
    reader.data['w/${document.id}'] = document;
  }
  return reader;
}

Outcome _export(MemoryBundleStore store, TextBundle candidate, int revision) {
  return exportTextBundle(
    request: ExportRequest('w', 'b', revision, ['z', 'a']),
    permissions: PermissionProvider(true),
    reader: _reader(),
    store: store,
    encoder: (workspace, documents) => candidate,
  );
}

void _expectStoredFormat(TextBundle actual, TextBundle expected) {
  expect(actual.manifest, expected.manifest);
  expect(actual.files.keys.toList(), expected.files.keys.toList());
  for (final path in expected.files.keys) {
    expect(actual.files[path], expected.files[path]);
  }
}

// Malformed non-null return handling is unspecified. A documented rejection
// or a correct canonical success is accepted. No load-order requirement.
void _expectRejectOrCanonicalSuccess(
  Outcome result,
  MemoryBundleStore store,
  TextBundle expected, {
  required bool existing,
}) {
  if (result.code == 'applied' || result.code == 'unchanged') {
    expect(result.code, existing ? 'unchanged' : 'applied');
    expect(result.message, existing ? 'Unchanged' : 'Applied');
    expect(result.revision, existing ? 7 : 1);
    expect(result.report, expected.report);
    final snapshot = store.data['w/b'];
    expect(snapshot, isNotNull);
    expect(snapshot!.revision, result.revision);
    _expectStoredFormat(snapshot.bundle!, expected);
    expect(store.commits, existing ? 0 : 1);
  } else {
    const messages = {
      'forbidden': 'Not allowed',
      'invalid_request': 'Invalid export',
      'not_found': 'Document unavailable',
      'conflict': 'Export changed',
      'storage_failure': 'Export unavailable',
    };
    expect(messages.containsKey(result.code), isTrue);
    expect(result.message, messages[result.code]);
    expect(result.revision, isNull);
    expect(result.report, isEmpty);
  }
}

void main() {
  test('S01 valid injected bundle retains applied and unchanged behavior', () {
    final expected = _publishedBundle();
    final store = MemoryBundleStore();
    final applied = _export(store, expected, 0);
    expect(applied.code, 'applied');
    _expectRejectOrCanonicalSuccess(applied, store, expected, existing: false);
    final unchanged = _export(store, expected, 1);
    expect(unchanged.code, 'unchanged');
    expect(unchanged.revision, 1);
    expect(unchanged.report, expected.report);
    _expectStoredFormat(store.data['w/b']!.bundle!, expected);
    expect(store.commits, 1);
  });

  test('S02 malformed injected manifest cannot accompany success', () {
    final expected = _publishedBundle();
    final candidate = TextBundle([0], expected.files, expected.report);
    final store = MemoryBundleStore();
    _expectRejectOrCanonicalSuccess(
      _export(store, candidate, 0), store, expected, existing: false,
    );
  });

  test('S03 injected traversal path cannot accompany success', () {
    final expected = _publishedBundle();
    final candidate = TextBundle(expected.manifest, {
      '../escape': expected.files['documents/z.txt']!,
      'documents/a.txt': expected.files['documents/a.txt']!,
    }, expected.report);
    final store = MemoryBundleStore();
    _expectRejectOrCanonicalSuccess(
      _export(store, candidate, 0), store, expected, existing: false,
    );
  });

  test('S04 injected invalid file byte cannot accompany success', () {
    final expected = _publishedBundle();
    final candidate = TextBundle(expected.manifest, {
      'documents/z.txt': [300],
      'documents/a.txt': expected.files['documents/a.txt']!,
    }, expected.report);
    final store = MemoryBundleStore();
    _expectRejectOrCanonicalSuccess(
      _export(store, candidate, 0), store, expected, existing: false,
    );
  });

  test('S05 applied result cannot use incomplete injected report', () {
    final expected = _publishedBundle();
    final candidate = TextBundle(expected.manifest, expected.files, []);
    final store = MemoryBundleStore();
    _expectRejectOrCanonicalSuccess(
      _export(store, candidate, 0), store, expected, existing: false,
    );
  });

  test('S06 unchanged result cannot use incomplete injected report', () {
    final expected = _publishedBundle();
    final candidate = TextBundle(expected.manifest, expected.files, []);
    final store = MemoryBundleStore();
    store.data['w/b'] = BundleSnapshot(7, expected);
    _expectRejectOrCanonicalSuccess(
      _export(store, candidate, 7), store, expected, existing: true,
    );
  });
}
