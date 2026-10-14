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
  test('public authorized rename', () {
    final s = Store(); final r = executeDocumentCommand(allowed, rename, s);
    expect(r.outcome, DocumentOutcome.applied); expect(s.record!.title, 'New');
  });
}
