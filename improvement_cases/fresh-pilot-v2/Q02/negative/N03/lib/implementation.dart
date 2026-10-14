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
  if (!actor.mayExport || actor.tenantId != tenantId || tenantId.isEmpty) {
    return const ExportResult(ExportOutcome.forbidden, 'Not allowed', []);
  }
  try {
    final events = store.readEvents(tenantId)
        .where((event) => event.tenantId == tenantId).toList();
    events.sort((a, b) {
      final order = a.sequence.compareTo(b.sequence);
      return order != 0 ? order : a.id.compareTo(b.id);
    });
    final rows = <ExportRow>[];
    for (final event in events) {
      final details = <String, String>{};
      for (final entry in event.details.entries) {
        if (entry.key == 'resource' || entry.key == 'result' ||
            entry.key == 'reason') {
          details[entry.key] = entry.value;
        }
      }
      rows.add(ExportRow(event.id, event.sequence, event.action,
          actor.role == ExportRole.auditor ? event.email : '[redacted]',
          Map<String, String>.unmodifiable(details)));
    }
    return ExportResult(ExportOutcome.ready, 'Ready', List<ExportRow>.unmodifiable(rows));
  } catch (_) {
    return const ExportResult(ExportOutcome.failed, 'Export failed', []);
  }
}
