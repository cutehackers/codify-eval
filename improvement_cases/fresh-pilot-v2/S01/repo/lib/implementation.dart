enum DocumentOutcome { applied, forbidden, invalid, missing, conflict }
enum DocumentAction { rename, archive }
class DocumentActor {
  final String tenantId;
  final Set<String> writableDocumentIds;
  const DocumentActor(this.tenantId, this.writableDocumentIds);
}
class Document {
  final String id;
  final String tenantId;
  final String title;
  final int revision;
  final bool archived;
  const Document(this.id, this.tenantId, this.title, this.revision, this.archived);
}
class DocumentCommand {
  final String tenantId;
  final String documentId;
  final int expectedRevision;
  final DocumentAction action;
  final String? title;
  const DocumentCommand(this.tenantId, this.documentId, this.expectedRevision,
      this.action, {this.title});
}
abstract class DocumentStore {
  Document? load(String tenantId, String documentId);
  bool compareAndSave(Document document, int expectedRevision);
}
class DocumentResult {
  final DocumentOutcome outcome;
  final String message;
  final int? revision;
  const DocumentResult(this.outcome, this.message, [this.revision]);
}
DocumentResult executeDocumentCommand(
    DocumentActor actor, DocumentCommand command, DocumentStore store) {
  throw UnimplementedError('Implement the task contract');
}
