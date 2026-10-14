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
  test('E1 unauthorized export never reads', () {
    for (final actor in [const ExportActor('x', true, ExportRole.auditor),
                         const ExportActor('t', false, ExportRole.support)]) {
      final s = EventStore([event('a', 1)]); final r = exportAudit(actor, 't', s);
      expect(r.outcome, ExportOutcome.forbidden); expect(r.message, 'Not allowed');
      expect(r.rows, isEmpty); expect(s.reads, 0);
    }
    final s = EventStore([]);
    expect(exportAudit(const ExportActor('', true, ExportRole.auditor), '', s).outcome,
      ExportOutcome.forbidden); expect(s.reads, 0);
  });
  test('E2 mixed tenant data filtered and source order preserved', () {
    final source = [event('b', 2), event('secret', 0, tenant: 'x'),
      event('z', 1), event('a', 2), event('a', 2)];
    final original = List.of(source); final s = EventStore(source);
    final r = exportAudit(auditor, 't', s);
    expect(r.outcome, ExportOutcome.ready); expect(r.message, 'Ready');
    expect(r.rows.map((r) => r.id), ['z', 'a', 'a', 'b']);
    expect(source, original); expect(s.reads, 1); expect(s.tenant, 't');
  });
  test('E3 support explicit allowlist and full email redaction', () {
    final detail = {'resource': 'doc', 'result': 'ok', 'reason': 'private',
      'token': 'SECRET', 'FutureField': 'private', 'Resource': 'private'};
    final source = event('a', 3, details: detail);
    final r = exportAudit(support, 't', EventStore([source])); final row = r.rows.single;
    expect(row.id, 'a'); expect(row.sequence, 3); expect(row.action, 'updated');
    expect(row.email, '[redacted]'); expect(row.details, {'resource': 'doc', 'result': 'ok'});
    expect(source.email, 'person@example.com'); expect(detail['reason'], 'private');
  });
  test('E3 auditor retains approved fields only', () {
    final r = exportAudit(auditor, 't', EventStore([event('a', 1)]));
    expect(r.rows.single.email, 'person@example.com');
    expect(r.rows.single.details, {'resource': 'doc', 'result': 'ok', 'reason': 'policy'});
  });
  test('E3 missing keys are not invented', () {
    final r = exportAudit(support, 't', EventStore([event('a', 1, details: {})]));
    expect(r.rows.single.details, isEmpty);
  });
  test('E4 immutable independent snapshots for both roles', () {
    for (final actor in [auditor, support]) {
      final details = {'resource': 'doc', 'token': 'secret'};
      final source = [event('a', 1, details: details)];
      final r = exportAudit(actor, 't', EventStore(source));
      expect(() => r.rows.clear(), throwsUnsupportedError);
      expect(() => r.rows.single.details['resource'] = 'changed', throwsUnsupportedError);
      details['resource'] = 'later'; source.clear();
      expect(r.rows.single.details, {'resource': 'doc'});
    }
  });
  test('E5 no matching events is successful empty export', () {
    final r = exportAudit(auditor, 't', EventStore([event('x', 1, tenant: 'other')]));
    expect(r.outcome, ExportOutcome.ready); expect(r.message, 'Ready'); expect(r.rows, isEmpty);
  });
  test('E5 safe store error with no returned rows', () {
    final s = EventStore([event('a', 1)])..fail = true;
    final r = exportAudit(auditor, 't', s);
    expect(r.outcome, ExportOutcome.failed); expect(r.message, 'Export failed');
    expect(r.rows, isEmpty); expect(s.reads, 1);
  });
}
