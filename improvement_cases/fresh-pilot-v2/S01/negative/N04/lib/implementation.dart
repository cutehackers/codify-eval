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
  if (actor.tenantId != command.tenantId ||
      !actor.writableDocumentIds.contains(command.documentId)) {
    return const DocumentResult(DocumentOutcome.forbidden, 'Not allowed');
  }
  final normalizedTitle = command.title?.trim();
  if (command.tenantId.isEmpty || command.documentId.isEmpty ||
      command.expectedRevision < 0 ||
      (command.action == DocumentAction.rename &&
       (normalizedTitle == null || normalizedTitle.isEmpty ||
        normalizedTitle.length > 80))) {
    return const DocumentResult(DocumentOutcome.invalid, 'Invalid command');
  }
  try {
    final current = store.load(command.tenantId, command.documentId);
    if (current == null) {
      return const DocumentResult(DocumentOutcome.missing, 'Document unavailable');
    }
    if (current.tenantId != command.tenantId || current.id != command.documentId) {
      return const DocumentResult(DocumentOutcome.forbidden, 'Not allowed');
    }
    if (current.revision != command.expectedRevision || current.archived) {
      return const DocumentResult(DocumentOutcome.conflict, 'Document changed');
    }
    final next = Document(current.id, current.tenantId,
        command.action == DocumentAction.rename ? command.title! : current.title,
        current.revision + 1, command.action == DocumentAction.archive);
    if (!store.compareAndSave(next, command.expectedRevision)) {
      return const DocumentResult(DocumentOutcome.conflict, 'Document changed');
    }
    return DocumentResult(DocumentOutcome.applied, 'Applied', next.revision);
  } catch (_) {
    return const DocumentResult(DocumentOutcome.conflict, 'Document changed');
  }
}
