enum ExportRole { auditor, support }
enum ExportOutcome { ready, forbidden, failed }
class ExportActor {
  final String tenantId;
  final bool mayExport;
  final ExportRole role;
  const ExportActor(this.tenantId, this.mayExport, this.role);
}
class AuditEvent {
  final String id;
  final String tenantId;
  final int sequence;
  final String action;
  final String email;
  final Map<String, String> details;
  const AuditEvent(this.id, this.tenantId, this.sequence, this.action, this.email, this.details);
}
abstract class AuditStore {
  List<AuditEvent> readEvents(String tenantId);
}
class ExportRow {
  final String id;
  final int sequence;
  final String action;
  final String email;
  final Map<String, String> details;
  const ExportRow(this.id, this.sequence, this.action, this.email, this.details);
}
class ExportResult {
  final ExportOutcome outcome;
  final String message;
  final List<ExportRow> rows;
  const ExportResult(this.outcome, this.message, this.rows);
}
ExportResult exportAudit(ExportActor actor, String tenantId, AuditStore store) {
  throw UnimplementedError('Implement the task contract');
}
