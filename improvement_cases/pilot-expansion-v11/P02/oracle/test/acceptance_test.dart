import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import '../lib/contracts.dart';
import '../lib/checkpoint_codec.dart';
import '../lib/trusted_integrity.dart';
import 'test_support.dart';

T requiredNoError<T>(T Function() operation, String requirement) {
  try {
    return operation();
  } catch (cause, trace) {
    // A positive contract requires successful completion, not blanket rejection.
    // Preserve the original exception and stack for diagnosis inside the assertion.
    fail(
        '$requirement must complete without throwing.\nOriginal cause: $cause\nOriginal stack: $trace');
  }
}

Future<T> requiredFutureCompletion<T>(
    Future<T> operation, String requirement) async {
  try {
    return await operation;
  } catch (cause, trace) {
    fail(
        '$requirement must complete without throwing.\nOriginal cause: $cause\nOriginal stack: $trace');
  }
}

Future<ProcessorResult> requiredSuccess(
    Future<ProcessorResult> Function() operation, String requirement) async {
  late ProcessorResult result;
  try {
    result = await operation();
  } catch (cause, trace) {
    fail(
        '$requirement must complete without throwing.\nOriginal cause: $cause\nOriginal stack: $trace');
  }
  expect(result.code, ProcessorCode.ok, reason: requirement);
  requiredView(result.view, '$requirement must return its committed view');
  return result;
}

TenantView requiredView(TenantView? view, String requirement) {
  expect(view, isNotNull, reason: requirement);
  return view!;
}

StoreRecord requiredRecord(StoreRecord? record) {
  expect(record, isNotNull,
      reason: 'Successful novel ingest must persist a complete record');
  return record!;
}

String requiredCheckpoint(String? checkpoint) {
  expect(checkpoint, isNotNull,
      reason: 'Successful novel ingest must persist a checkpoint');
  expect(checkpoint, isNotEmpty,
      reason: 'Persisted checkpoint must have encoded content');
  return checkpoint!;
}

String encodeSuccess(CheckpointCodec codec, CheckpointState state) =>
    requiredNoError(
        () => codec.encode(state), 'Encoding a valid CheckpointState');
CheckpointState decodeSuccess(CheckpointCodec codec, String checkpoint,
        {required String expectedTenant, required int expectedRevision}) =>
    requiredNoError(
        () => codec.decode(checkpoint,
            expectedTenant: expectedTenant, expectedRevision: expectedRevision),
        'Decoding a valid authenticated canonical checkpoint');

void safeFailure(ProcessorResult r, ProcessorCode code, TenantView? before) {
  expect(r.code, code);
  expect(r.accepted, 0);
  expect(r.replayed, 0);
  expect(r.recovered, isFalse);
  expect(r.view?.stock, before?.stock);
  expect(r.view?.revision, before?.revision);
  expect(r.view?.processedCount, before?.processedCount);
}

CheckpointState state({
  int revision = 1,
  Map<String, int>? stock,
  Map<String, String>? replays,
  String tenant = 'tenant_a',
}) =>
    CheckpointState(
      tenantId: tenant,
      revision: revision,
      stock: stock ?? {'SKU': 1},
      replays: replays ?? {},
    );
String checkpoint({
  int revision = 1,
  Map<String, int>? stock,
  Map<String, String>? replays,
  String tenant = 'tenant_a',
}) =>
    encodeSuccess(
      CheckpointCodec(TrustedIntegrity()),
      state(revision: revision, stock: stock, replays: replays, tenant: tenant),
    );
void seed(MemoryStore store, String encoded, {int revision = 1}) {
  store.records['tenant_a'] = StoreRecord(
    revision: revision,
    primary: encoded,
    recovery: encoded,
  );
}

/// A store-controlled barrier observes the interval before CAS decides or commits.
/// No sleeps determine the winning schedule.
class PendingCasStore extends MemoryStore {
  bool gated = false;
  final entered = Completer<void>();
  final release = Completer<void>();
  @override
  Future<bool> compareAndSwap(
      String tenantId, int expectedRevision, StoreRecord replacement) async {
    if (!gated)
      return super.compareAndSwap(tenantId, expectedRevision, replacement);
    writes++;
    entered.complete();
    await release.future;
    if (failWrite) throw StoreUnavailable();
    if ((records[tenantId]?.revision ?? 0) != expectedRevision) return false;
    records[tenantId] = replacement;
    return true;
  }
}

void main() {
  group('A01 authorization and tenant isolation', () {
    test(
      'authorized positive and denied precedence with no collaborator calls',
      () async {
        for (final tenant in ['tenant_a', 'BadTenant', '', 'a' * 33, 'a/b']) {
          final store = MemoryStore();
          final integrity = CountingIntegrity();
          final p = processor(
            store,
            tenant: tenant,
            allowed: {},
            integrity: integrity,
          );
          safeFailure(await p.ingest('{'), ProcessorCode.unauthorized, null);
          safeFailure(await p.restore(), ProcessorCode.unauthorized, null);
          expect(p.current, isNull);
          expect(store.reads + store.writes, 0);
          expect(integrity.calls, 0);
        }
        final invalidAllowed = processor(
          MemoryStore(),
          tenant: 'Invalid',
          allowed: {'Invalid'},
        );
        expect(
          (await invalidAllowed.restore()).code,
          ProcessorCode.unauthorized,
        );
        final store = MemoryStore();
        final a = processor(store);
        final b = processor(store, tenant: 'tenant_b');
        expect(
            (await requiredSuccess(() => a.restore(),
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok);
        expect(
            (await requiredSuccess(() => b.restore(),
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok);
        expect(
            (await requiredSuccess(
                    () => a.ingest(batch([event('same', delta: 2)])),
                    'Successful operation must return ok and a view'))
                .accepted,
            1);
        expect(
            (await requiredSuccess(
                    () => b.ingest(batch([event('same', delta: 3)])),
                    'Successful operation must return ok and a view'))
                .accepted,
            1);
        expect(
            requiredView(
                    a.current, 'Successful restore/ingest must expose current')
                .stock['SKU'],
            2);
        expect(
            requiredView(
                    b.current, 'Successful restore/ingest must expose current')
                .stock['SKU'],
            3);
        safeFailure(
          await a.ingest(
            jsonEncode({
              'events': [event('next')],
              'tenant': 'tenant_b',
            }),
          ),
          ProcessorCode.invalidBatch,
          a.current,
        );
      },
    );
  });
  group('A02 complete input validation', () {
    test(
      'calendar bounds, grammar, type and effective duplicate key policy',
      () async {
        final store = MemoryStore();
        final p = processor(store);
        await requiredSuccess(() => p.restore(), 'Successful restore setup');
        final valid = [
          '2000-02-29T00:00:00.000Z',
          '2099-12-31T23:59:59.999Z',
          '2024-02-29T23:59:59.999Z',
        ];
        for (var i = 0; i < valid.length; i++) {
          expect(
            (await requiredSuccess(
                    () => p.ingest(batch([event('valid$i', at: valid[i])])),
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok,
          );
        }
        final badTimes = [
          '2001-02-29T00:00:00.000Z',
          '2024-02-30T00:00:00.000Z',
          '2024-04-31T00:00:00.000Z',
          '1999-12-31T23:59:59.999Z',
          '2100-01-01T00:00:00.000Z',
          '2024-01-01T24:00:00.000Z',
          '2024-01-01T00:60:00.000Z',
          '2024-01-01T00:00:60.000Z',
          '2024-01-01T00:00:00Z',
          '2024-01-01T00:00:00.00Z',
          '2024-01-01T00:00:00.000+00:00',
          ' 2024-01-01T00:00:00.000Z',
          '2024-00-01T00:00:00.000Z',
        ];
        for (final time in badTimes) {
          safeFailure(
            await p.ingest(batch([event('bad', at: time)])),
            ProcessorCode.invalidBatch,
            p.current,
          );
        }
        final invalidEvents = <Object?>[
          null,
          [],
          'event',
          {...event('bad'), 'delta': 1.0},
          {...event('bad'), 'delta': 0},
          {...event('bad'), 'delta': 1000001},
          {...event('bad'), 'delta': -1000001},
          {...event('bad'), 'delta': true},
          {...event('bad'), 'extra': 1},
          {'id': 'bad', 'sku': 'SKU', 'delta': 1},
          event('_bad'),
          event('a' * 65),
          event('bad', sku: 'å'),
          event(' bad'),
          event('bad', sku: ''),
        ];
        final writes = store.writes;
        for (final e in invalidEvents) {
          safeFailure(
            await p.ingest(batch([e])),
            ProcessorCode.invalidBatch,
            p.current,
          );
        }
        for (final raw in [
          '{',
          'null',
          '[]',
          '{}',
          '{"events":null}',
          batch([]),
          batch(List.generate(101, (i) => event('e$i'))),
          jsonEncode({
            'events': [event('x')],
            'other': 1,
          }),
          '${' ' * 65536}${batch([event('x')])}',
          '${'é' * 32768}${batch([event('x')])}',
        ]) {
          safeFailure(
            await p.ingest(raw),
            ProcessorCode.invalidBatch,
            p.current,
          );
        }
        expect(store.writes, writes);
        final atLimit = batch([event('byte_limit')]);
        final padded = '${' ' * (65536 - utf8.encode(atLimit).length)}$atLimit';
        expect(utf8.encode(padded).length, 65536);
        expect(
            (await requiredSuccess(() => p.ingest(padded),
                    'Successful operation must return ok and a view'))
                .accepted,
            1);
        expect(
          (await p.ingest(
            batch([event('A' * 64, sku: 'z' * 64, delta: 1000000)]),
          ))
              .accepted,
          1,
        );
        expect(
          (await p.ingest(
            batch([event('minus', sku: 'z' * 64, delta: -1000000)]),
          ))
              .accepted,
          1,
        );
        // Last effective field wins for caller JSON, including duplicate root keys.
        final raw =
            '{"events":null,"events":[{"id":"wrong","id":"last","sku":"SKU","delta":0,"delta":1,"occurredAt":"2024-02-29T23:59:59.999Z"}]}';
        expect(
            (await requiredSuccess(() => p.ingest(raw),
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok);
        expect(
            (await requiredSuccess(() => p.ingest(batch([event('last')])),
                    'Successful operation must return ok and a view'))
                .replayed,
            1);
        expect(
          (await p.ingest(
            batch(List.generate(100, (i) => event('hundred$i'))),
          ))
              .accepted,
          100,
        );
      },
    );
    test(
      'later invalid event precedes earlier semantic conflict or underflow and no read',
      () async {
        final store = MemoryStore();
        final p = processor(store);
        await requiredSuccess(() => p.restore(), 'Successful restore setup');
        await requiredSuccess(
            () => p.ingest(batch([event('known')])), 'Successful ingest setup');
        final reads = store.reads, writes = store.writes;
        for (final first in [
          event('known', delta: 2),
          event('new', delta: -2),
        ]) {
          safeFailure(
            await p.ingest(
              batch([
                first,
                {...event('invalid'), 'delta': 0},
              ]),
            ),
            ProcessorCode.invalidBatch,
            p.current,
          );
        }
        expect(store.reads, reads);
        expect(store.writes, writes);
      },
    );
  });
  group('A03 content replay identity', () {
    test(
      'canonical fingerprint and every content field, duplicates, case sensitivity',
      () async {
        final store = MemoryStore();
        final p = processor(store);
        await requiredSuccess(() => p.restore(), 'Successful restore setup');
        final original = event('id', delta: 5);
        final first = await requiredSuccess(
            () => p.ingest(batch([original, original])),
            'Successful ingest result');
        expect(first.accepted, 1);
        expect(first.replayed, 1);
        final reordered = {
          'occurredAt': original['occurredAt'],
          'delta': 5,
          'sku': 'SKU',
          'id': 'id',
        };
        expect(
            (await requiredSuccess(() => p.ingest('  ${batch([reordered])}  '),
                    'Successful operation must return ok and a view'))
                .replayed,
            1);
        for (final changed in [
          event('id', sku: 'OTHER', delta: 5),
          event('id', delta: 6),
          event('id', delta: 5, at: '2024-02-29T23:59:59.998Z'),
        ]) {
          safeFailure(
            await p.ingest(batch([changed])),
            ProcessorCode.replayConflict,
            p.current,
          );
        }
        final saved = decodeSuccess(
          CheckpointCodec(TrustedIntegrity()),
          requiredCheckpoint(requiredRecord(store.records['tenant_a']).primary),
          expectedTenant: 'tenant_a',
          expectedRevision: 1,
        );
        expect(
          saved.replays['id'],
          TrustedIntegrity().sha256Hex(
            utf8.encode(
              jsonEncode(['id', 'SKU', 5, '2024-02-29T23:59:59.999Z']),
            ),
          ),
        );
        safeFailure(
          await p.ingest(
            batch([event('duplicate'), event('duplicate', delta: 2)]),
          ),
          ProcessorCode.replayConflict,
          p.current,
        );
        expect(
            (await requiredSuccess(
                    () => p.ingest(batch([event('ID', sku: 'sku')])),
                    'Successful operation must return ok and a view'))
                .accepted,
            1);
        expect(
            requiredView(
                    p.current, 'Successful restore/ingest must expose current')
                .stock,
            {'SKU': 5, 'sku': 1});
      },
    );
  });
  group('A04 ordered stock and capacity', () {
    test(
      'ordered transitions, zero deletion, chronological freedom, upper bound',
      () async {
        final store = MemoryStore();
        final p = processor(store);
        await requiredSuccess(() => p.restore(), 'Successful restore setup');
        safeFailure(
          await p.ingest(batch([event('remove', delta: -1), event('add')])),
          ProcessorCode.stockOutOfRange,
          p.current,
        );
        expect(
          (await p.ingest(
            batch([
              event('add', at: '2099-01-01T00:00:00.000Z'),
              event('remove', delta: -1, at: '2000-01-01T00:00:00.000Z'),
            ]),
          ))
              .accepted,
          2,
        );
        expect(
            requiredView(
                    p.current, 'Successful restore/ingest must expose current')
                .stock,
            isEmpty);
        seed(store, checkpoint(stock: {'SKU': 2147483647}));
        await requiredSuccess(() => p.restore(), 'Successful restore setup');
        safeFailure(
          await p.ingest(batch([event('overflow')])),
          ProcessorCode.stockOutOfRange,
          p.current,
        );
        expect(
          (await requiredSuccess(
                  () => p.ingest(batch([event('down', delta: -1000000)])),
                  'Successful operation must return ok and a view'))
              .code,
          ProcessorCode.ok,
        );
      },
    );
    test(
      'first semantic error, replay at capacity and stock before capacity',
      () async {
        final store = MemoryStore();
        final integrity = TrustedIntegrity();
        final fp = integrity.sha256Hex(
          utf8.encode(
            jsonEncode(['known', 'SKU', 1, '2024-02-29T23:59:59.999Z']),
          ),
        );
        final replays = <String, String>{'known': fp};
        for (var i = 0; i < 9999; i++) {
          replays['r$i'] = 'a' * 64;
        }
        seed(store, checkpoint(replays: replays));
        final p = processor(store);
        await requiredSuccess(() => p.restore(), 'Successful restore setup');
        expect(
            (await requiredSuccess(() => p.ingest(batch([event('known')])),
                    'Successful operation must return ok and a view'))
                .replayed,
            1);
        expect(store.writes, 0);
        safeFailure(
          await p.ingest(batch([event('novel')])),
          ProcessorCode.capacityExceeded,
          p.current,
        );
        safeFailure(
          await p.ingest(batch([event('novel', delta: -2)])),
          ProcessorCode.stockOutOfRange,
          p.current,
        );
        safeFailure(
          await p.ingest(
            batch([event('known', delta: 2), event('novel', delta: -2)]),
          ),
          ProcessorCode.replayConflict,
          p.current,
        );
        safeFailure(
          await p.ingest(
            batch([event('novel', delta: -2), event('known', delta: 2)]),
          ),
          ProcessorCode.stockOutOfRange,
          p.current,
        );
        // Exactly 9,999 -> 10,000 is allowed, then the next new event fails atomically.
        replays.remove('r0');
        seed(store, checkpoint(replays: replays));
        await requiredSuccess(() => p.restore(), 'Successful restore setup');
        safeFailure(
          await p.ingest(batch([event('last'), event('excess')])),
          ProcessorCode.capacityExceeded,
          p.current,
        );
        expect(
            (await requiredSuccess(() => p.ingest(batch([event('last')])),
                    'Successful operation must return ok and a view'))
                .accepted,
            1);
      },
    );
  });
  group('A05 atomic batch and revision semantics', () {
    test(
      'late failure leaves ledger, stock, bytes and counts unchanged without encoding',
      () async {
        final store = MemoryStore();
        final integrity = CountingIntegrity();
        final p = processor(store, integrity: integrity);
        await requiredSuccess(() => p.restore(), 'Successful restore setup');
        await requiredSuccess(() => p.ingest(batch([event('known', delta: 5)])),
            'Successful ingest setup');
        final before = requiredView(
                p.current, 'Successful restore/ingest must expose current'),
            record = store.records['tenant_a'];
        final signs = integrity.signs;
        for (final last in [
          event('known', delta: 6),
          event('under', delta: -100),
        ]) {
          final code = last['id'] == 'known'
              ? ProcessorCode.replayConflict
              : ProcessorCode.stockOutOfRange;
          safeFailure(
            await p.ingest(batch([event('staged'), last])),
            code,
            before,
          );
          expect(identical(store.records['tenant_a'], record), isTrue);
          expect(integrity.signs, signs);
          expect(store.writes, 1);
        }
        final accepted = await requiredSuccess(
            () => p.ingest(
                  batch([
                    event('staged'),
                    event('more'),
                    event('known', delta: 5)
                  ]),
                ),
            'Successful ingest result');
        expect(accepted.accepted, 2);
        expect(accepted.replayed, 1);
        expect(
            requiredView(accepted.view,
                    'Operation must preserve or return the required view')
                .revision,
            2);
        expect(store.writes, 2);
        expect(store.reads, 1);
        expect(
          requiredRecord(store.records['tenant_a']).primary,
          requiredRecord(store.records['tenant_a']).recovery,
        );
        final bytes = store.records['tenant_a'];
        expect(
          (await requiredSuccess(
                  () => p.ingest(batch([event('staged'), event('more')])),
                  'Successful operation must return ok and a view'))
              .replayed,
          2,
        );
        expect(identical(store.records['tenant_a'], bytes), isTrue);
        expect(store.writes, 2);
      },
    );
    test(
      'maximum revision staging precedence, replay succeeds without encode',
      () async {
        final store = MemoryStore();
        final integrity = CountingIntegrity();
        final fingerprint = TrustedIntegrity().sha256Hex(
          utf8.encode(
            jsonEncode(['known', 'SKU', 1, '2024-02-29T23:59:59.999Z']),
          ),
        );
        seed(
          store,
          checkpoint(revision: 2147483647, replays: {'known': fingerprint}),
          revision: 2147483647,
        );
        final p = processor(store, integrity: integrity);
        await requiredSuccess(() => p.restore(), 'Successful restore setup');
        final signs = integrity.signs;
        expect(
            (await requiredSuccess(() => p.ingest(batch([event('known')])),
                    'Successful operation must return ok and a view'))
                .replayed,
            1);
        safeFailure(
          await p.ingest(batch([event('under', delta: -2)])),
          ProcessorCode.stockOutOfRange,
          p.current,
        );
        safeFailure(
          await p.ingest(batch([event('new')])),
          ProcessorCode.capacityExceeded,
          p.current,
        );
        expect(integrity.signs, signs);
        expect(store.writes, 0);
      },
    );
  });
  group('A06 deterministic optimistic concurrency', () {
    test(
      'scheduled winner, unchanged loser, explicit refresh and retry',
      () async {
        final store = MemoryStore();
        final a = processor(store), b = processor(store);
        await requiredSuccess(() => a.restore(), 'Successful restore setup');
        await requiredSuccess(() => b.restore(), 'Successful restore setup');
        final before = requiredView(
            b.current, 'Successful restore/ingest must expose current');
        store.writeGate = Completer<void>();
        final losing = b.ingest(batch([event('shared'), event('only_b')]));
        final losingGate = store.writeGate!;
        addTearDown(() async {
          if (!losingGate.isCompleted) losingGate.complete();
          await requiredFutureCompletion(
              losing, 'Concurrent ingest settlement');
        });
        await Future<void>.delayed(Duration.zero);
        expect(store.writes, 1);
        final gate = store.writeGate!;
        store.writeGate = null;
        expect(
          (await requiredSuccess(
                  () => a.ingest(batch([event('shared'), event('only_a')])),
                  'Successful operation must return ok and a view'))
              .accepted,
          2,
        );
        gate.complete();
        safeFailure(await losing, ProcessorCode.concurrentCommit, before);
        expect(store.writes, 2);
        expect(store.reads, 2);
        expect(
            requiredView(
                    b.current, 'Successful restore/ingest must expose current')
                .revision,
            0);
        expect(
            (await requiredSuccess(() => b.restore(),
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok);
        final retried = await requiredSuccess(
            () => b.ingest(
                  batch([event('shared'), event('only_b')]),
                ),
            'Successful ingest result');
        expect(retried.code, ProcessorCode.ok);
        expect(retried.accepted, 1);
        expect(retried.replayed, 1);
        expect(
            requiredView(
                    b.current, 'Successful restore/ingest must expose current')
                .stock['SKU'],
            3);
        expect(
            requiredView(
                    b.current, 'Successful restore/ingest must expose current')
                .processedCount,
            3);
        expect(
            requiredView(
                    b.current, 'Successful restore/ingest must expose current')
                .revision,
            2);
      },
    );
  });
  group('A07 failures and busy lifecycle', () {
    test('read/CAS exceptions preserve state and release busy', () async {
      final store = MemoryStore();
      final p = processor(store);
      await requiredSuccess(() => p.restore(), 'Successful restore setup');
      await requiredSuccess(
          () => p.ingest(batch([event('one')])), 'Successful ingest setup');
      final before = requiredView(
          p.current, 'Successful restore/ingest must expose current');
      store.failRead = true;
      safeFailure(await p.restore(), ProcessorCode.storageUnavailable, before);
      store.failRead = false;
      store.failWrite = true;
      final bytes = store.records['tenant_a'];
      safeFailure(
        await p.ingest(batch([event('two')])),
        ProcessorCode.storageUnavailable,
        before,
      );
      expect(identical(store.records['tenant_a'], bytes), isTrue);
      store.failWrite = false;
      expect(
          (await requiredSuccess(() => p.ingest(batch([event('two')])),
                  'Successful operation must return ok and a view'))
              .accepted,
          1);
      store.records['tenant_a'] = StoreRecord(
        revision: 3,
        primary: 'bad',
        recovery: 'bad',
      );
      final newer = requiredView(
          p.current, 'Successful restore/ingest must expose current');
      safeFailure(await p.restore(), ProcessorCode.corruptCheckpoint, newer);
      safeFailure(
        await p.ingest(batch([event('three')])),
        ProcessorCode.concurrentCommit,
        newer,
      );
    });
    test(
      'same-instance overlapping restore/ingest returns immediately busy without work',
      () async {
        final store = MemoryStore();
        final integrity = CountingIntegrity();
        final p = processor(store, integrity: integrity);
        store.readGate = Completer<void>();
        final pending = p.restore();
        final readGate = store.readGate!;
        addTearDown(() async {
          if (!readGate.isCompleted) readGate.complete();
          await requiredFutureCompletion(
              pending, 'Pending operation settlement');
        });
        await Future<void>.delayed(Duration.zero);
        safeFailure(await p.ingest('{'), ProcessorCode.busy, null);
        safeFailure(await p.restore(), ProcessorCode.busy, null);
        expect(store.reads, 1);
        expect(integrity.calls, 0);
        store.readGate!.complete();
        store.readGate = null;
        expect(
            (await requiredSuccess(() => pending,
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok);
        store.writeGate = Completer<void>();
        final ingesting = p.ingest(batch([event('one')]));
        final writeGate = store.writeGate!;
        addTearDown(() async {
          if (!writeGate.isCompleted) writeGate.complete();
          await requiredFutureCompletion(
              ingesting, 'Pending ingest settlement');
        });
        await Future<void>.delayed(Duration.zero);
        final calls = integrity.calls;
        safeFailure(await p.ingest('{'), ProcessorCode.busy, p.current);
        safeFailure(await p.restore(), ProcessorCode.busy, p.current);
        expect(store.reads, 1);
        expect(store.writes, 1);
        expect(integrity.calls, calls);
        store.writeGate!.complete();
        store.writeGate = null;
        expect(
            (await requiredSuccess(() => ingesting,
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok);
        expect(
            (await requiredSuccess(() => p.restore(),
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok);
      },
    );
  });
  group('A08 authenticated canonical checkpoint codec', () {
    test(
      'deterministic sorted canonical roundtrip and trusted integrity use',
      () {
        final integrity = CountingIntegrity();
        final codec = CheckpointCodec(integrity);
        final first = state(
          stock: {'z': 9, 'A': 1},
          replays: {'z': 'b' * 64, 'A': 'a' * 64},
        );
        final second = state(
          stock: {'A': 1, 'z': 9},
          replays: {'A': 'a' * 64, 'z': 'b' * 64},
        );
        final encoded = encodeSuccess(codec, first);
        expect(encoded, encodeSuccess(codec, second));
        expect(integrity.signs, 2);
        final canonical = jsonEncode({
          'schema': 1,
          'tenant': 'tenant_a',
          'revision': 1,
          'stock': {'A': 1, 'z': 9},
          'replays': {'A': 'a' * 64, 'z': 'b' * 64},
        });
        expect(encoded, signedPayload({}, raw: canonical));
        final restored = decodeSuccess(
          codec,
          encoded,
          expectedTenant: 'tenant_a',
          expectedRevision: 1,
        );
        expect(restored.stock, first.stock);
        expect(restored.replays, first.replays);
        expect(integrity.verifies, 1);
        expect(
          decodeSuccess(
            codec,
            encodeSuccess(codec, state(revision: 0, stock: {}, replays: {})),
            expectedTenant: 'tenant_a',
            expectedRevision: 0,
          ).stock,
          isEmpty,
        );
        expect(
          decodeSuccess(
            codec,
            encodeSuccess(codec, state(stock: {}, replays: {'id': 'a' * 64})),
            expectedTenant: 'tenant_a',
            expectedRevision: 1,
          ).replays.length,
          1,
        );
      },
    );
    test('all invalid encode state domains reject', () {
      final codec = CheckpointCodec(TrustedIntegrity());
      final invalid = [
        state(tenant: 'UPPER'),
        state(tenant: ''),
        state(revision: -1),
        state(revision: 2147483648),
        state(stock: {'SKU': 0}),
        state(stock: {'SKU': -1}),
        state(stock: {'SKU': 2147483648}),
        state(stock: {'_bad': 1}),
        state(stock: {'a' * 65: 1}),
        state(replays: {'': 'a' * 64}),
        state(replays: {'_bad': 'a' * 64}),
        state(replays: {'id': 'A' * 64}),
        state(replays: {'id': 'g' * 64}),
        state(replays: {'id': 'a' * 63}),
        state(replays: {for (var i = 0; i < 10001; i++) 'id$i': 'a' * 64}),
      ];
      for (final value in invalid) {
        expect(() => codec.encode(value), throwsA(isA<InvalidCheckpoint>()));
      }
    });
    test('bad MAC, byte tamper, noncanonical outer and base64 reject', () {
      final integrity = CountingIntegrity();
      final codec = CheckpointCodec(integrity);
      final good = checkpoint();
      final outer = jsonDecode(good) as Map<String, dynamic>;
      final zeroTag = jsonEncode({
        'payload': outer['payload'],
        'tag': '0' * 64,
      });
      final tampered = jsonEncode({
        'payload': base64Encode(
          utf8.encode(jsonEncode(payload(stock: {'SKU': 2}))),
        ),
        'tag': outer['tag'],
      });
      final invalid = [
        jsonEncode({
          'payload': (outer['payload'] as String).replaceAll('=', ''),
          'tag': outer['tag'],
        }),
        zeroTag,
        tampered,
        '{',
        'null',
        '[]',
        jsonEncode({'payload': outer['payload']}),
        jsonEncode({...outer, 'extra': 1}),
        jsonEncode({'tag': outer['tag'], 'payload': outer['payload']}),
        ' $good',
        '$good\n',
        jsonEncode({
          'payload': outer['payload'],
          'tag': (outer['tag'] as String).toUpperCase(),
        }),
        jsonEncode({'payload': outer['payload'], 'tag': 'a' * 63}),
        jsonEncode({'payload': '*', 'tag': outer['tag']}),
        jsonEncode({'payload': '${outer['payload']}\n', 'tag': outer['tag']}),
        '{"payload":"bad","payload":${jsonEncode(outer['payload'])},"tag":${jsonEncode(outer['tag'])}}',
      ];
      for (final raw in invalid) {
        expect(
          () => codec.decode(
            raw,
            expectedTenant: 'tenant_a',
            expectedRevision: 1,
          ),
          throwsA(isA<InvalidCheckpoint>()),
        );
      }
      // Invalid UTF8 is properly authenticated but never a valid payload.
      expect(
        () => codec.decode(
          signedPayload({}, bytes: [0xff]),
          expectedTenant: 'tenant_a',
          expectedRevision: 1,
        ),
        throwsA(isA<InvalidCheckpoint>()),
      );
      expect(integrity.verifies, greaterThanOrEqualTo(3));
    });
    test('authenticated malformed states and noncanonical payloads reject', () {
      final codec = CheckpointCodec(TrustedIntegrity());
      final malformed = <Object?>[
        null,
        [],
        {...payload(), 'schema': 2},
        {...payload(), 'schema': 1.0},
        {...payload(), 'schema': '1'},
        {...payload(), 'extra': 1},
        {'schema': 1, 'tenant': 'tenant_a', 'revision': 1, 'stock': {}},
        payload(tenant: 'tenant_b'),
        payload(tenant: 'Invalid'),
        payload(revision: 0),
        payload(revision: -1),
        payload(revision: 2147483648),
        {...payload(), 'revision': 1.0},
        {...payload(), 'stock': []},
        {...payload(), 'replays': []},
        payload(stock: {'SKU': 0}),
        payload(stock: {'SKU': -1}),
        payload(stock: {'SKU': 2147483648}),
        payload(stock: {'SKU': 1.0}),
        payload(stock: {'SKU': true}),
        payload(stock: {'_bad': 1}),
        payload(replays: {'id': 1}),
        payload(replays: {'': 'a' * 64}),
        payload(replays: {'id': 'A' * 64}),
        payload(replays: {'id': 'a' * 63}),
        payload(replays: {'id': 'g' * 64}),
        payload(replays: {for (var i = 0; i < 10001; i++) 'id$i': 'a' * 64}),
      ];
      for (final value in malformed) {
        final bytes = utf8.encode(jsonEncode(value));
        expect(
          () => codec.decode(
            signedPayload({}, bytes: bytes),
            expectedTenant: 'tenant_a',
            expectedRevision: 1,
          ),
          throwsA(isA<InvalidCheckpoint>()),
        );
      }
      final rawPayloads = [
        ' ${jsonEncode(payload())}',
        '{"tenant":"tenant_a","schema":1,"revision":1,"stock":{"SKU":1},"replays":{}}',
        '{"schema":1,"tenant":"tenant_a","revision":1,"stock":{"z":1,"A":1},"replays":{}}',
        '{"schema":1,"tenant":"tenant_a","revision":1,"stock":{},"replays":{"z":"${'a' * 64}","A":"${'a' * 64}"}}',
        '{"schema":2,"schema":1,"tenant":"tenant_a","revision":1,"stock":{"SKU":1},"replays":{}}',
        '{"schema":1,"tenant":"tenant_a","revision":1,"stock":{"SKU":2,"SKU":1},"replays":{}}',
        '{"schema":1,"tenant":"tenant_a","revision":1,"stock":{},"replays":{"id":"${'b' * 64}","id":"${'a' * 64}"}}',
      ];
      for (final raw in rawPayloads) {
        expect(
          () => codec.decode(
            signedPayload({}, raw: raw),
            expectedTenant: 'tenant_a',
            expectedRevision: 1,
          ),
          throwsA(isA<InvalidCheckpoint>()),
        );
      }
      // Wrong caller expectations bind even an otherwise valid authenticated state.
      expect(
        () => codec.decode(
          checkpoint(),
          expectedTenant: 'tenant_b',
          expectedRevision: 1,
        ),
        throwsA(isA<InvalidCheckpoint>()),
      );
      expect(
        () => codec.decode(
          checkpoint(),
          expectedTenant: 'tenant_a',
          expectedRevision: 2,
        ),
        throwsA(isA<InvalidCheckpoint>()),
      );
    });
  });
  group('A09 restore and current-revision recovery', () {
    test(
      'each copy independently recoverable, no repair until novel ingest',
      () async {
        final store = MemoryStore();
        final p = processor(store);
        expect(
            (await requiredSuccess(() => p.restore(),
                    'Successful operation must return ok and a view'))
                .recovered,
            isFalse);
        expect(
            requiredView(
                    p.current, 'Successful restore/ingest must expose current')
                .stock,
            isEmpty);
        expect(
            requiredView(
                    p.current, 'Successful restore/ingest must expose current')
                .processedCount,
            0);
        await requiredSuccess(
            () => p.ingest(batch([event('one')])), 'Successful ingest setup');
        final original = requiredRecord(store.records['tenant_a']);
        for (final bad in <String?>[
          null,
          'bad',
          checkpoint(tenant: 'tenant_b'),
          checkpoint(revision: 0),
        ]) {
          for (final primaryBad in [true, false]) {
            store.records['tenant_a'] = StoreRecord(
              revision: 1,
              primary: primaryBad ? bad : original.primary,
              recovery: primaryBad ? original.recovery : bad,
            );
            final recovered = processor(store);
            final readBefore = store.reads, writesBefore = store.writes;
            final result = await requiredSuccess(
                () => recovered.restore(), 'Successful restore result');
            expect(result.code, ProcessorCode.ok);
            expect(result.recovered, isTrue);
            expect(
                requiredView(result.view,
                        'Operation must preserve or return the required view')
                    .stock,
                {'SKU': 1});
            expect(
                requiredView(result.view,
                        'Operation must preserve or return the required view')
                    .revision,
                1);
            expect(store.reads, readBefore + 1);
            expect(store.writes, writesBefore);
            final record = store.records['tenant_a'];
            expect(
                (await requiredSuccess(
                        () => recovered.ingest(batch([event('one')])),
                        'Successful operation must return ok and a view'))
                    .replayed,
                1);
            expect(identical(store.records['tenant_a'], record), isTrue);
            expect(store.writes, writesBefore);
          }
        }
        final restored = processor(store);
        await requiredSuccess(
            () => restored.restore(), 'Successful restore setup');
        expect(
            (await requiredSuccess(() => restored.ingest(batch([event('two')])),
                    'Successful operation must return ok and a view'))
                .accepted,
            1);
        expect(
          requiredRecord(store.records['tenant_a']).primary,
          requiredRecord(store.records['tenant_a']).recovery,
        );
        expect(requiredRecord(store.records['tenant_a']).revision, 2);
        expect(
            (await requiredSuccess(() => processor(store).restore(),
                    'Successful operation must return ok and a view'))
                .recovered,
            isFalse);
      },
    );
    test(
      'invalid record, contradictory valid copies, stale recovery and preservation',
      () async {
        final store = MemoryStore();
        final p = processor(store);
        await requiredSuccess(() => p.restore(), 'Successful restore setup');
        await requiredSuccess(
            () => p.ingest(batch([event('one')])), 'Successful ingest setup');
        final before = requiredView(
                p.current, 'Successful restore/ingest must expose current'),
            good = requiredCheckpoint(
                requiredRecord(store.records['tenant_a']).primary);
        final invalid = [
          StoreRecord(revision: -1),
          StoreRecord(revision: 2147483648),
          StoreRecord(revision: 1),
          StoreRecord(revision: 0, primary: 'bad'),
          StoreRecord(revision: 1, primary: 'bad', recovery: 'bad'),
          StoreRecord(
            revision: 1,
            primary: good,
            recovery: checkpoint(stock: {'SKU': 2}),
          ),
          StoreRecord(revision: 2, primary: 'bad', recovery: good),
          StoreRecord(
            revision: 1,
            primary: checkpoint(tenant: 'tenant_b'),
            recovery: checkpoint(tenant: 'tenant_b'),
          ),
        ];
        for (final record in invalid) {
          store.records['tenant_a'] = record;
          safeFailure(
            await p.restore(),
            ProcessorCode.corruptCheckpoint,
            before,
          );
          expect(
              requiredView(p.current,
                      'Successful restore/ingest must expose current')
                  .stock,
              before.stock);
          expect(store.writes, 1);
        }
        // Both-null at revision zero and signed nonempty revision-zero are separate valid forms.
        store.records['tenant_a'] = StoreRecord(revision: 0);
        expect(
            (await requiredSuccess(() => p.restore(),
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok);
        expect(
            requiredView(
                    p.current, 'Successful restore/ingest must expose current')
                .revision,
            0);
        seed(store, checkpoint(revision: 0), revision: 0);
        expect(
            (await requiredSuccess(() => p.restore(),
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok);
        expect(
            requiredView(
                    p.current, 'Successful restore/ingest must expose current')
                .stock,
            {'SKU': 1});
      },
    );
  });
  group('A10 immutable views, initialization and durable ledger', () {
    test(
      'defensive constructors, frozen captured views, checkpoint immutability',
      () async {
        final allowed = {'tenant_a'};
        final context = AccessContext(allowedTenants: allowed);
        allowed.clear();
        expect(context.allowedTenants, {'tenant_a'});
        expect(
          () => context.allowedTenants.add('other'),
          throwsUnsupportedError,
        );
        final stocks = {'SKU': 2}, replays = {'id': 'a' * 64};
        final s = CheckpointState(
          tenantId: 'tenant_a',
          revision: 1,
          stock: stocks,
          replays: replays,
        );
        final view = TenantView(
          tenantId: 'tenant_a',
          revision: 1,
          stock: stocks,
          processedCount: 1,
        );
        stocks.clear();
        replays.clear();
        expect(s.stock, {'SKU': 2});
        expect(s.replays.length, 1);
        expect(view.stock, {'SKU': 2});
        expect(() => s.stock['SKU'] = 0, throwsUnsupportedError);
        expect(() => s.replays.clear(), throwsUnsupportedError);
        expect(() => view.stock.clear(), throwsUnsupportedError);
        final decoded = decodeSuccess(
            CheckpointCodec(TrustedIntegrity()), checkpoint(),
            expectedTenant: 'tenant_a', expectedRevision: 1);
        expect(() => decoded.stock.clear(), throwsUnsupportedError);
        expect(() => decoded.replays['new'] = 'a' * 64, throwsUnsupportedError);
        final store = MemoryStore();
        final p = processor(store);
        await requiredSuccess(() => p.restore(), 'Successful restore setup');
        final empty = requiredView(
            p.current, 'Successful restore/ingest must expose current');
        final first = await requiredSuccess(
            () => p.ingest(batch([event('one')])), 'Successful ingest result');
        final captured = requiredView(
            first.view, 'Operation must preserve or return the required view');
        expect(() => captured.stock['SKU'] = 99, throwsUnsupportedError);
        await requiredSuccess(
            () => p.ingest(batch([event('two')])), 'Successful ingest setup');
        expect(empty.stock, isEmpty);
        expect(empty.revision, 0);
        expect(captured.stock, {'SKU': 1});
        expect(captured.processedCount, 1);
        expect(captured.revision, 1);
        final restart = processor(store);
        await requiredSuccess(
            () => restart.restore(), 'Successful restore setup');
        expect(
          (await requiredSuccess(
                  () => restart.ingest(batch([event('one'), event('two')])),
                  'Successful operation must return ok and a view'))
              .replayed,
          2,
        );
        expect(
            requiredView(restart.current,
                    'Successful restore/ingest must expose current')
                .processedCount,
            2);
        expect(store.writes, 2);
      },
    );
    test(
      'first failed restore stays uninitialized before caller input or crypto work',
      () async {
        final store = MemoryStore();
        final integrity = CountingIntegrity();
        final p = processor(store, integrity: integrity);
        safeFailure(await p.ingest('{'), ProcessorCode.notInitialized, null);
        expect(store.reads + store.writes, 0);
        expect(integrity.calls, 0);
        store.failRead = true;
        safeFailure(await p.restore(), ProcessorCode.storageUnavailable, null);
        store.failRead = false;
        store.records['tenant_a'] = StoreRecord(
          revision: 1,
          primary: 'bad',
          recovery: 'bad',
        );
        safeFailure(await p.restore(), ProcessorCode.corruptCheckpoint, null);
        final calls = integrity.calls;
        safeFailure(await p.ingest('{'), ProcessorCode.notInitialized, null);
        expect(p.current, isNull);
        expect(integrity.calls, calls);
        store.records.clear();
        expect(
            (await requiredSuccess(() => p.restore(),
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok);
        expect(
            (await requiredSuccess(() => p.ingest(batch([event('success')])),
                    'Successful operation must return ok and a view'))
                .accepted,
            1);
      },
    );
  });

  group('A05 atomic batch and revision semantics', () {
    test('C20 current and busy view preserve captured state while CAS pending',
        () async {
      for (final outcome in [
        'success',
        'concurrentCommit',
        'storageUnavailable'
      ]) {
        final store = PendingCasStore();
        final integrity = CountingIntegrity();
        final p = processor(store, integrity: integrity);
        expect(
            (await requiredSuccess(() => p.restore(),
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok);
        expect(
            (await requiredSuccess(
                    () => p.ingest(batch([event('existing', delta: 5)])),
                    'Successful operation must return ok and a view'))
                .code,
            ProcessorCode.ok);
        final before = requiredView(
            p.current, 'Successful restore/ingest must expose current');
        // Freeze values independently, so mutation of a captured view cannot mask publication.
        final priorStock = Map<String, int>.of(before.stock);
        final priorRevision = before.revision;
        final priorCount = before.processedCount;
        final durableBefore = store.records['tenant_a'];
        store.gated = true;
        final pending = p.ingest(batch([event('staged', delta: 2)]));
        addTearDown(() async {
          if (!store.release.isCompleted) store.release.complete();
          await requiredFutureCompletion(
              pending, 'Pending operation settlement');
        });
        // Timeout only bounds a broken implementation that never invokes the boundary.
        await store.entered.future.timeout(const Duration(seconds: 2));
        final calls = integrity.calls;
        final reads = store.reads;
        expect(
            requiredView(
                    p.current, 'Successful restore/ingest must expose current')
                .stock,
            priorStock);
        expect(
            requiredView(
                    p.current, 'Successful restore/ingest must expose current')
                .revision,
            priorRevision);
        expect(
            requiredView(
                    p.current, 'Successful restore/ingest must expose current')
                .processedCount,
            priorCount);
        expect(before.stock, priorStock);
        expect(identical(store.records['tenant_a'], durableBefore), isTrue);
        final busyIngest = await p.ingest('{');
        final busyRestore = await p.restore();
        for (final busy in [busyIngest, busyRestore]) {
          safeFailure(busy, ProcessorCode.busy, before);
          expect(
              requiredView(busy.view,
                      'Operation must preserve or return the required view')
                  .stock,
              priorStock);
          expect(
              requiredView(busy.view,
                      'Operation must preserve or return the required view')
                  .revision,
              priorRevision);
          expect(
              requiredView(busy.view,
                      'Operation must preserve or return the required view')
                  .processedCount,
              priorCount);
        }
        expect(integrity.calls, calls);
        expect(store.reads, reads);
        expect(store.writes, 2);
        if (outcome == 'concurrentCommit') {
          // An external writer installs revision 2 before this CAS checks its expectation.
          seed(store, checkpoint(revision: 2, stock: {'SKU': 9}), revision: 2);
        } else if (outcome == 'storageUnavailable') {
          store.failWrite = true;
        }
        final recordAtDecision = store.records['tenant_a'];
        store.release.complete();
        final settled = await requiredFutureCompletion(
            pending, 'Pending operation settlement');
        if (outcome == 'success') {
          expect(settled.code, ProcessorCode.ok);
          expect(settled.accepted, 1);
          expect(
              requiredView(p.current,
                      'Successful restore/ingest must expose current')
                  .stock,
              {'SKU': 7});
          expect(
              requiredView(p.current,
                      'Successful restore/ingest must expose current')
                  .revision,
              priorRevision + 1);
          expect(
              requiredView(p.current,
                      'Successful restore/ingest must expose current')
                  .processedCount,
              priorCount + 1);
        } else {
          safeFailure(
              settled,
              outcome == 'concurrentCommit'
                  ? ProcessorCode.concurrentCommit
                  : ProcessorCode.storageUnavailable,
              before);
          expect(
              requiredView(p.current,
                      'Successful restore/ingest must expose current')
                  .stock,
              priorStock);
          expect(
              requiredView(p.current,
                      'Successful restore/ingest must expose current')
                  .revision,
              priorRevision);
          expect(
              requiredView(p.current,
                      'Successful restore/ingest must expose current')
                  .processedCount,
              priorCount);
          expect(
              identical(store.records['tenant_a'], recordAtDecision), isTrue);
          if (outcome == 'storageUnavailable') {
            store.gated = false;
            store.failWrite = false;
            final retry = await requiredSuccess(
                () => p.ingest(batch([event('staged', delta: 2)])),
                'Successful ingest result');
            expect(retry.accepted, 1);
            expect(retry.replayed, 0);
          }
        }
        expect(before.stock, priorStock);
        expect(before.revision, priorRevision);
        expect(before.processedCount, priorCount);
      }
    });
  });
  group('A08 authenticated canonical checkpoint codec', () {
    test(
        'C21 verify boundary is called once before malformed payload rejection',
        () {
      final invalidPayloads = <List<int>>[
        [0xff],
        utf8.encode('{')
      ];
      for (final bytes in invalidPayloads) {
        for (final authentic in [true, false]) {
          final integrity = CountingIntegrity();
          final tag =
              authentic ? TrustedIntegrity().signCheckpoint(bytes) : '0' * 64;
          final canonicalOuter =
              jsonEncode({'payload': base64Encode(bytes), 'tag': tag});
          final codec = CheckpointCodec(integrity);
          expect(
              () => codec.decode(canonicalOuter,
                  expectedTenant: 'tenant_a', expectedRevision: 1),
              throwsA(isA<InvalidCheckpoint>()));
          // Payload-first rejection cannot satisfy this individual boundary observation.
          expect(integrity.verifies, 1,
              reason: 'MAC boundary precedes strict UTF8/JSON interpretation');
        }
      }
      final integrity = CountingIntegrity();
      final bytes = utf8.encode(jsonEncode(payload()));
      final wrongTag =
          jsonEncode({'payload': base64Encode(bytes), 'tag': '0' * 64});
      expect(
          () => CheckpointCodec(integrity).decode(wrongTag,
              expectedTenant: 'tenant_a', expectedRevision: 1),
          throwsA(isA<InvalidCheckpoint>()));
      expect(integrity.verifies, 1);
    });
  });
  group('A02 complete input validation', () {
    test('C22 valid effective JSON exceeds UTF8 bytes but not character limit',
        () async {
      final store = MemoryStore();
      final p = processor(store);
      expect(
          (await requiredSuccess(() => p.restore(),
                  'Successful operation must return ok and a view'))
              .code,
          ProcessorCode.ok);
      String duplicateInput(String ignored, String id) =>
          '{"events":${jsonEncode(ignored)},"events":${jsonEncode([
                event(id)
              ])}}';
      final ordinary = duplicateInput('é' * 100, 'ordinary_multibyte');
      expect((jsonDecode(ordinary) as Map)['events'],
          [event('ordinary_multibyte')]);
      expect(
          (await requiredSuccess(() => p.ingest(ordinary),
                  'Successful operation must return ok and a view'))
              .accepted,
          1);
      final oversize = duplicateInput('é' * 33000, 'over_byte_limit');
      // These observations establish valid JSON and effective valid content independently.
      expect(
          (jsonDecode(oversize) as Map)['events'], [event('over_byte_limit')]);
      expect(oversize.length, lessThan(65536));
      expect(utf8.encode(oversize).length, greaterThan(65536));
      final reads = store.reads, writes = store.writes;
      final before = requiredView(
          p.current, 'Successful restore/ingest must expose current');
      final durableBefore = store.records['tenant_a'];
      safeFailure(await p.ingest(oversize), ProcessorCode.invalidBatch, before);
      expect(store.reads, reads);
      expect(store.writes, writes);
      expect(identical(store.records['tenant_a'], durableBefore), isTrue);
    });
  });
}
