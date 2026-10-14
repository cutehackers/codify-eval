import 'package:flutter_test/flutter_test.dart';
import 'package:question_fixture/models.dart';
import 'package:question_fixture/implementation.dart';
MemoryStore fixture() => MemoryStore({
  'w': Warehouse('t', {'A': 7, 'B': 1, 'C': 8}),
  'other': Warehouse('other_t', {'A': 99}),
});
ReservationService service(MemoryStore s) => ReservationService(s, const Identity('t', 'operator'));
void main() {
  test('P01 full allocation and unrelated stock', () {
    final s = fixture(); final r = service(s).reserve(const Request('w', 'o', [Row('A', 3)]));
    expect(r.code, 'ok'); expect(r.reserved.map((r) => [r.skuId, r.quantity]).toList(), [['A', 3]]);
    expect(r.shortages, isEmpty); expect(s.warehouses['w']!.stock, {'A': 4, 'B': 1, 'C': 8});
    expect(s.warehouses['other']!.stock['A'], 99);
  });
  test('P02 inaccessible warehouse before reads or validation', () {
    final s = fixture(); final r = service(s).reserve(const Request('other', 'o', [Row('A', 1)]));
    expect(r.code, 'not_found'); expect(r.reserved, isEmpty); expect(r.shortages, isEmpty);
    expect(s.stockReads, 0); expect(s.commits, 0); expect(s.warehouses['other']!.stock['A'], 99);
  });
  test('P03 missing warehouse', () {
    final s = fixture(); expect(service(s).reserve(const Request('missing', '', [])).code, 'not_found');
    expect(s.stockReads, 0); expect(s.commits, 0);
  });
  test('P04 invalid request shapes', () {
    for (final r in [const Request('w', ' ', [Row('A', 1)]), const Request('w', 'o', []),
      const Request('w', 'o', [Row(' ', 1)]), const Request('w', 'o', [Row('A', 0)]),
      const Request('w', 'o', [Row('A', -1)]), const Request('w', 'o', [Row('A', 1), Row('A', 2)])]) {
      final s = fixture(); expect(service(s).reserve(r).code, 'invalid_request');
      expect(s.stockReads, 0); expect(s.commits, 0);
    }
  });
  test('P05 unknown SKU makes no writes', () {
    final s = fixture(); expect(service(s).reserve(const Request('w', 'o', [Row('A', 1), Row('missing', 1)])).code, 'invalid_request');
    expect(s.commits, 0); expect(s.warehouses['w']!.stock['A'], 7);
  });
  test('P06 identical retry is idempotent including row order', () {
    final s = fixture(); final api = service(s);
    api.reserve(const Request('w', 'o', [Row('A', 2), Row('C', 1)]));
    final r = api.reserve(const Request('w', 'o', [Row('C', 1), Row('A', 2)]));
    expect(r.code, 'ok'); expect(s.commits, 1); expect(s.warehouses['w']!.stock['A'], 5);
    expect(s.warehouses['w']!.stock['C'], 7);
  });
  test('P07 changed retry conflicts', () {
    final s = fixture(); final api = service(s); api.reserve(const Request('w', 'o', [Row('A', 2)]));
    final r = api.reserve(const Request('w', 'o', [Row('A', 3)]));
    expect(r.code, 'conflict'); expect(s.commits, 1); expect(s.warehouses['w']!.stock['A'], 5);
  });
  test('P08 commit failure rolls back and returns safe error', () {
    final s = fixture()..failCommit = true;
    final r = service(s).reserve(const Request('w', 'o', [Row('A', 2)]));
    expect(r.code, 'storage_failure'); expect(r.reserved, isEmpty); expect(r.shortages, isEmpty);
    expect(s.warehouses['w']!.stock['A'], 7); expect(s.warehouses['w']!.orders, isEmpty); expect(s.commits, 0);
  });
}
