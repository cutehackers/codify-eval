import 'package:flutter_test/flutter_test.dart';
import 'package:question_fixture/models.dart';
import 'package:question_fixture/implementation.dart';
void main() {
  test('A01 mixed shortage consumes no stock', () {
    final s = MemoryStore({'w': Warehouse('t', {'A': 7, 'B': 1, 'C': 0})});
    final r = ReservationService(s, const Identity('t', 'op')).reserve(const Request('w', 'o', [Row('A', 3), Row('B', 2), Row('C', 4)]));
    expect(r.code, 'ok'); expect(r.reserved, isEmpty);
    expect(r.shortages.map((x) => [x.skuId, x.requested, x.available]).toList(), [['B', 2, 1], ['C', 4, 0]]);
    expect(s.warehouses['w']!.stock, {'A': 7, 'B': 1, 'C': 0}); expect(s.commits, 1);
  });
  test('A02 shortage outcome persists across replenishment and changed retry conflicts', () {
    final s = MemoryStore({'w': Warehouse('t', {'A': 7, 'B': 1})});
    final api = ReservationService(s, const Identity('t', 'op'));
    const q = Request('w', 'o', [Row('A', 3), Row('B', 2)]); api.reserve(q);
    s.warehouses['w']!.stock['B'] = 20;
    final retry = api.reserve(q); expect(retry.reserved, isEmpty);
    expect(retry.shortages.single.available, 1); expect(s.commits, 1); expect(s.warehouses['w']!.stock['A'], 7);
    expect(s.warehouses['w']!.stock['B'], 20);
    expect(api.reserve(const Request('w', 'o', [Row('A', 1)])).code, 'conflict');
  });
  test('A03 shortage record write failure rolls back', () {
    final s = MemoryStore({'w': Warehouse('t', {'A': 7, 'B': 1})})..failCommit = true;
    final r = ReservationService(s, const Identity('t', 'op')).reserve(const Request('w', 'o', [Row('A', 3), Row('B', 2)]));
    expect(r.code, 'storage_failure'); expect(s.warehouses['w']!.orders, isEmpty);
    expect(s.warehouses['w']!.stock, {'A': 7, 'B': 1}); expect(s.commits, 0);
  });
}
