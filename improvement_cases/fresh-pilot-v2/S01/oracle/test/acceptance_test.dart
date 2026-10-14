import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/implementation.dart';

class Store implements DocumentStore {
  Document? record = const Document('d', 'a', 'Original', 4, false);
  int reads = 0, writes = 0;
  bool accepted = true, throwRead = false, throwWrite = false;
  String? loadedTenant, loadedId;
  int? expected;
  @override
  Document? load(String tenantId, String documentId) {
    reads++; loadedTenant = tenantId; loadedId = documentId;
    if (throwRead) throw StateError('SECRET tenant payment key');
    return record;
  }
  @override
  bool compareAndSave(Document document, int expectedRevision) {
    writes++; expected = expectedRevision;
    if (throwWrite) throw StateError('SECRET tenant payment key');
    if (!accepted) return false;
    record = document; return true;
  }
}
const rename = DocumentCommand('a', 'd', 4, DocumentAction.rename, title: ' New ');
DocumentActor get allowed => DocumentActor('a', {'d'});
void checkResult(DocumentResult r, DocumentOutcome o, String msg, [int? revision]) {
  expect(r.outcome, o); expect(r.message, msg); expect(r.revision, revision);
}
void main() {
  test('D1 cross tenant denial precedes malformed validation and reads', () {
    final s = Store(); final grants = {'d'};
    checkResult(executeDocumentCommand(DocumentActor('b', grants),
      const DocumentCommand('a', 'd', -1, DocumentAction.rename), s),
      DocumentOutcome.forbidden, 'Not allowed');
    expect([s.reads, s.writes], [0, 0]); expect(grants, {'d'});
    expect(s.record!.title, 'Original');
  });
  test('D1 missing document grant denies without effects', () {
    final s = Store();
    checkResult(executeDocumentCommand(DocumentActor('a', {}), rename, s),
      DocumentOutcome.forbidden, 'Not allowed');
    expect([s.reads, s.writes], [0, 0]);
  });
  test('D2 invalid titles and revision never touch store', () {
    for (final title in <String?>[null, '  ', List.filled(81, 'x').join()]) {
      final s = Store();
      checkResult(executeDocumentCommand(allowed,
        DocumentCommand('a', 'd', 4, DocumentAction.rename, title: title), s),
        DocumentOutcome.invalid, 'Invalid command');
      expect([s.reads, s.writes], [0, 0]);
    }
    final s = Store();
    checkResult(executeDocumentCommand(allowed,
      const DocumentCommand('a', 'd', -1, DocumentAction.archive), s),
      DocumentOutcome.invalid, 'Invalid command');
    expect(s.reads, 0);
  });
  test('D2 empty authorized IDs are invalid', () {
    final s = Store();
    checkResult(executeDocumentCommand(DocumentActor('', {''}),
      const DocumentCommand('', '', 0, DocumentAction.archive), s),
      DocumentOutcome.invalid, 'Invalid command'); expect(s.reads, 0);
  });
  test('D3 scoped lookup and missing result', () {
    final s = Store()..record = null;
    checkResult(executeDocumentCommand(allowed, rename, s),
      DocumentOutcome.missing, 'Document unavailable');
    expect([s.loadedTenant, s.loadedId], ['a', 'd']); expect(s.writes, 0);
  });
  test('D3 mis-scoped store record never saved', () {
    for (final record in [const Document('d', 'b', 'secret', 4, false),
                         const Document('other', 'a', 'secret', 4, false)]) {
      final s = Store()..record = record;
      checkResult(executeDocumentCommand(allowed, rename, s),
        DocumentOutcome.forbidden, 'Not allowed'); expect(s.writes, 0);
    }
  });
  test('D4 stale and archived commands cannot write', () {
    for (final record in [const Document('d', 'a', 'Original', 5, false),
                         const Document('d', 'a', 'Original', 4, true)]) {
      final s = Store()..record = record;
      checkResult(executeDocumentCommand(allowed, rename, s),
        DocumentOutcome.conflict, 'Document changed'); expect(s.writes, 0);
    }
  });
  test('D4 rename is trimmed revisioned and preserves input', () {
    final s = Store(); final before = s.record; final grants = {'d'};
    checkResult(executeDocumentCommand(DocumentActor('a', grants), rename, s),
      DocumentOutcome.applied, 'Applied', 5);
    expect([s.reads, s.writes, s.expected], [1, 1, 4]);
    expect(s.record!.title, 'New'); expect(s.record!.archived, false);
    expect(before!.title, 'Original'); expect(before.revision, 4);
    expect(rename.title, ' New '); expect(grants, {'d'});
  });
  test('D4 archive ignores title and retains existing title', () {
    final s = Store();
    checkResult(executeDocumentCommand(allowed,
      const DocumentCommand('a', 'd', 4, DocumentAction.archive, title: ''), s),
      DocumentOutcome.applied, 'Applied', 5);
    expect(s.record!.archived, true); expect(s.record!.title, 'Original');
  });
  test('D5 failed compare and exceptions expose no details', () {
    for (final s in [Store()..accepted = false,
                    Store()..throwRead = true, Store()..throwWrite = true]) {
      checkResult(executeDocumentCommand(allowed, rename, s),
        DocumentOutcome.conflict, 'Document changed');
      expect(s.record!.revision, 4);
    }
  });
}
