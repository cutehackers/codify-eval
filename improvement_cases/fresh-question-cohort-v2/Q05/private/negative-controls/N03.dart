import 'dart:convert';
import 'models.dart';
class ReservationService {
  final MemoryStore store;
  final Identity identity;
  ReservationService(this.store, this.identity);
  Outcome reserve(Request request) {
    if (!store.accessible(request.warehouseId, identity.tenantId)) {
      return const Outcome('not_found');
    }
    final ids = <String>{};
    if (request.orderId.trim().isEmpty || request.rows.isEmpty ||
        request.rows.any((r) => r.skuId.trim().isEmpty || r.quantity <= 0 || !ids.add(r.skuId))) {
      return const Outcome('invalid_request');
    }
    final stock = store.snapshot(request.warehouseId);
    if (request.rows.any((r) => !stock.containsKey(r.skuId))) {
      return const Outcome('invalid_request');
    }
    final signature = jsonEncode(request.rows.map((r) => [r.skuId, r.quantity]).toList()
      ..sort((a, b) => (a[0] as String).compareTo(b[0] as String)));
    final shortages = request.rows.where((r) => stock[r.skuId]! < r.quantity)
      .map((r) => Shortage(r.skuId, r.quantity, stock[r.skuId]!)).toList();
    final reserved = shortages.isEmpty ? List<Row>.of(request.rows) : <Row>[];
    final next = Map<String, int>.of(stock);
    for (final row in reserved) { next[row.skuId] = next[row.skuId]! - row.quantity; }
    final outcome = Outcome('ok', reserved: reserved, shortages: shortages);
    try {
      store.commit(request.warehouseId, request.orderId, Recorded(signature, outcome), next);
      return outcome;
    } catch (_) { return const Outcome('storage_failure'); }
  }
}
