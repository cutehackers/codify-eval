import 'package:flutter_test/flutter_test.dart';
import '../lib/contracts.dart';
import 'test_support.dart';

void main() {
  test(
    'public lifecycle, exact replay, atomic rejection and restart',
    () async {
      final store = MemoryStore();
      final p = processor(store);
      expect((await p.restore()).code, ProcessorCode.ok);
      expect(p.current!.revision, 0);
      final first = await p.ingest(batch([event('one', delta: 5)]));
      expect(first.code, ProcessorCode.ok);
      expect(first.accepted, 1);
      final replay = await p.ingest(batch([event('one', delta: 5)]));
      expect(replay.replayed, 1);
      expect(store.writes, 1);
      final before = store.records['tenant_a'];
      expect(
        (await p.ingest(batch([event('two'), event('one', delta: 6)]))).code,
        ProcessorCode.replayConflict,
      );
      expect(identical(store.records['tenant_a'], before), isTrue);
      expect(p.current!.stock, {'SKU': 5});
      final restarted = processor(store);
      expect((await restarted.restore()).code, ProcessorCode.ok);
      expect(
        (await restarted.ingest(batch([event('one', delta: 5)]))).replayed,
        1,
      );
    },
  );
  test('public single-copy current-revision recovery', () async {
    final store = MemoryStore();
    final p = processor(store);
    await p.restore();
    await p.ingest(batch([event('one')]));
    final saved = store.records['tenant_a']!;
    store.records['tenant_a'] = StoreRecord(
      revision: saved.revision,
      primary: 'damaged',
      recovery: saved.recovery,
    );
    final restored = await processor(store).restore();
    expect(restored.code, ProcessorCode.ok);
    expect(restored.recovered, isTrue);
    expect(restored.view!.stock, {'SKU': 1});
    expect(store.writes, 1);
  });
}
