import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/implementation.dart';

class EventStore implements AuditStore {
  final List<AuditEvent> events;
  int reads = 0;
  String? tenant;
  bool fail = false;
  EventStore(this.events);
  @override
  List<AuditEvent> readEvents(String tenantId) {
    reads++; tenant = tenantId;
    if (fail) throw StateError('SECRET email@example.com token');
    return events;
  }
}
const auditor = ExportActor('t', true, ExportRole.auditor);
const support = ExportActor('t', true, ExportRole.support);
AuditEvent event(String id, int sequence, {String tenant = 't', Map<String,String>? details}) =>
  AuditEvent(id, tenant, sequence, 'updated', 'person@example.com', details ?? {'resource': 'doc', 'result': 'ok', 'reason': 'policy', 'token': 'SECRET'});
void main() {
  test('public auditor exports approved event', () {
    final r = exportAudit(auditor, 't', EventStore([event('a', 1)]));
    expect(r.outcome, ExportOutcome.ready); expect(r.rows.single.id, 'a');
  });
}
