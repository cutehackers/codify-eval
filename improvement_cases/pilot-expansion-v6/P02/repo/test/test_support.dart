import 'dart:async';
import 'dart:convert';
import '../lib/contracts.dart';
import '../lib/trusted_integrity.dart';
import '../lib/event_processor.dart';

class MemoryStore implements CheckpointStore {
  final Map<String, StoreRecord> records = {};
  int reads = 0, writes = 0;
  bool failRead = false, failWrite = false;
  Completer<void>? readGate, writeGate;
  @override
  Future<StoreRecord> read(String tenantId) async {
    reads++;
    final gate = readGate;
    if (gate != null) await gate.future;
    if (failRead) throw StoreUnavailable();
    return records[tenantId] ?? StoreRecord(revision: 0);
  }

  @override
  Future<bool> compareAndSwap(
    String tenantId,
    int expectedRevision,
    StoreRecord replacement,
  ) async {
    writes++;
    final gate = writeGate;
    if (gate != null) await gate.future;
    if (failWrite) throw StoreUnavailable();
    if ((records[tenantId]?.revision ?? 0) != expectedRevision) return false;
    records[tenantId] = replacement;
    return true;
  }
}

class CountingIntegrity implements IntegrityService {
  final TrustedIntegrity delegate = TrustedIntegrity();
  int hashes = 0, signs = 0, verifies = 0;
  int get calls => hashes + signs + verifies;
  @override
  String sha256Hex(List<int> bytes) {
    hashes++;
    return delegate.sha256Hex(bytes);
  }

  @override
  String signCheckpoint(List<int> bytes) {
    signs++;
    return delegate.signCheckpoint(bytes);
  }

  @override
  bool verifyCheckpoint(List<int> bytes, String tag) {
    verifies++;
    return delegate.verifyCheckpoint(bytes, tag);
  }
}

Map<String, Object> event(
  String id, {
  String sku = 'SKU',
  int delta = 1,
  String at = '2024-02-29T23:59:59.999Z',
}) => {'id': id, 'sku': sku, 'delta': delta, 'occurredAt': at};
String batch(List<Object?> events) => jsonEncode({'events': events});
EventProcessor processor(
  MemoryStore store, {
  String tenant = 'tenant_a',
  CountingIntegrity? integrity,
  Set<String>? allowed,
}) => EventProcessor(
  tenantId: tenant,
  context: AccessContext(allowedTenants: allowed ?? {tenant}),
  store: store,
  integrity: integrity ?? CountingIntegrity(),
);
String signedPayload(Object payload, {String? raw, List<int>? bytes}) {
  final body = bytes ?? utf8.encode(raw ?? jsonEncode(payload));
  return jsonEncode({
    'payload': base64Encode(body),
    'tag': TrustedIntegrity().signCheckpoint(body),
  });
}

Map<String, Object> payload({
  String tenant = 'tenant_a',
  int revision = 1,
  Map<String, Object>? stock,
  Map<String, Object>? replays,
}) => {
  'schema': 1,
  'tenant': tenant,
  'revision': revision,
  'stock': stock ?? {'SKU': 1},
  'replays': replays ?? {},
};
