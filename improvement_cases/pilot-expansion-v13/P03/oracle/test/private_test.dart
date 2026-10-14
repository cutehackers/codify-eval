import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:tenant_inventory_p02/archive_importer.dart';
import 'package:tenant_inventory_p02/manifest_codec.dart';
import 'package:tenant_inventory_p02/contracts.dart';
import 'test_support.dart';

const lifecycleLimit = Duration(seconds: 3);
Future<T> bounded<T>(Future<T> operation) => operation.timeout(lifecycleLimit);
Future<T> observed<T>(Future<T> operation) {
  operation.then<void>((_) {}, onError: (Object error, StackTrace stack) {});
  return operation;
}

Future<void> settle(Future<dynamic> operation) async {
  try {
    await bounded(operation);
  } catch (_) {
    // Cleanup consumes secondary errors while preserving the test's first failure.
  }
}

void release(Completer<void> gate) {
  if (!gate.isCompleted) gate.complete();
}

class Harness {
  final i = TestIntegrity();
  final s = MemoryStore();
  final c = Cancellation();
  late final importer = ArchiveImporter(store: s, integrity: i);
  Future<ImportResult> run(Map<String, List<int>> files,
      {Stream<ArchiveEntry>? source, String? text, String? tag}) {
    final m = text ?? manifest(i, files);
    return bounded(
        importer.import(m, tag ?? i.tag(m), source ?? archive(files), c));
  }

  void failed(ImportResult r, ImportCode code, {bool stage = true}) {
    expect(r.code, code);
    expect(r.files, 0);
    expect(r.bytes, 0);
    expect(s.live, {
      'old.txt': [9]
    });
    expect(s.stages, isEmpty);
    expect(s.calls.where((x) => x == 'rollback').length, stage ? 1 : 0);
    expect(s.calls, isNot(contains('publish')));
  }
}

void main() {
  test('A01 path containment grammar', () async {
    final bad = [
      '../x',
      'a/../x',
      '/x',
      'a//x',
      r'a\x',
      'C:/x',
      'a/%2e',
      'a/é',
      'a/',
      'a/' + List.filled(41, 'b').join()
    ];
    for (final path in bad) {
      expect(ManifestCodec.validPath(path), false, reason: path);
    }
    expect(ManifestCodec.validPath('v1.2/a-b_0.txt'), true);
    final h = Harness();
    h.failed(
        await h.run({
          'a/../x': [1]
        }),
        ImportCode.invalidManifest,
        stage: false);
  });
  test('A02 manifest shape integer and digest validation', () async {
    for (final row in [
      {'path': 'a', 'size': 1.0, 'digest': List.filled(64, '0').join()},
      {'path': 'a', 'size': -1, 'digest': List.filled(64, '0').join()},
      {'path': 'a', 'size': 65537, 'digest': List.filled(64, '0').join()},
      {'path': 'a', 'size': 0, 'digest': List.filled(64, 'A').join()},
      {
        'path': 'a',
        'size': 0,
        'digest': List.filled(64, '0').join(),
        'extra': 0
      }
    ]) {
      final h = Harness();
      h.failed(
          await h.run({'a': []},
              text: jsonEncode({
                'version': 1,
                'files': [row]
              })),
          ImportCode.invalidManifest,
          stage: false);
    }
    final h = Harness();
    h.failed(
        await h.run({'a': []},
            text: jsonEncode({
              'version': 1.0,
              'files': [
                {'path': 'a', 'size': 0, 'digest': h.i.sha256Hex(const [])}
              ]
            })),
        ImportCode.invalidManifest,
        stage: false);
  });
  test('A03 manifest duplicate prefix and aggregate limits', () async {
    for (final files in [
      [
        {'path': 'a', 'size': 0, 'digest': List.filled(64, '0').join()},
        {'path': 'a', 'size': 0, 'digest': List.filled(64, '0').join()}
      ],
      [
        {'path': 'a', 'size': 0, 'digest': List.filled(64, '0').join()},
        {'path': 'a/b', 'size': 0, 'digest': List.filled(64, '0').join()}
      ],
      [
        for (var n = 0; n < 5; n++)
          {'path': 'a$n', 'size': 65536, 'digest': List.filled(64, '0').join()}
      ],
      [
        for (var n = 0; n < 65; n++)
          {'path': 'a$n', 'size': 0, 'digest': List.filled(64, '0').join()}
      ],
      <Object>[]
    ]) {
      final h = Harness();
      h.failed(
          await h
              .run({'a': []}, text: jsonEncode({'version': 1, 'files': files})),
          ImportCode.invalidManifest,
          stage: false);
    }
  });
  test('A04 manifest byte cap and trusted integrity boundary', () async {
    final h = Harness();
    final text = List.filled(16385, ' ').join();
    h.failed(await h.run({'a': []}, text: text), ImportCode.invalidManifest,
        stage: false);
    expect(h.i.verifies, 0);
    final q = Harness();
    q.failed(await q.run({'a': []}, text: '{', tag: 'bad'),
        ImportCode.invalidManifest,
        stage: false);
    expect(q.i.verifies, 1);
  });
  test('A05 reject unexpected symlink before body subscription', () async {
    for (final e in [
      ArchiveEntry('../a', 'file', Stream.error(SourceUnavailable())),
      ArchiveEntry('a', 'symlink', Stream.error(SourceUnavailable())),
      ArchiveEntry('z', 'file', Stream.error(SourceUnavailable()))
    ]) {
      final h = Harness();
      h.failed(
          await h.run({
            'a': [1]
          }, source: Stream.value(e)),
          ImportCode.invalidEntry);
    }
  });
  test('A06 duplicate archive entry rejection', () async {
    final h = Harness();
    final e = ArchiveEntry('a', 'file', Stream.value([1]));
    h.failed(
        await h.run({
          'a': [1]
        },
            source: Stream.fromIterable([
              e,
              ArchiveEntry('a', 'file', Stream.value([1]))
            ])),
        ImportCode.invalidEntry);
    expect(h.s.calls.where((x) => x == 'write').length, 1);
  });
  test('A07 missing and empty archive rollback', () async {
    for (final source in [
      Stream<ArchiveEntry>.empty(),
      archive({
        'a': [1]
      })
    ]) {
      final h = Harness();
      h.failed(
          await h.run({
            'a': [1],
            'b': [2]
          }, source: source),
          ImportCode.invalidEntry);
    }
  });
  test('A08 over declared bound rejected before write', () async {
    final h = Harness();
    h.failed(
        await h.run({
          'a': [1]
        },
            source: Stream.value(ArchiveEntry(
                'a',
                'file',
                Stream.fromIterable([
                  [1],
                  [2]
                ])))),
        ImportCode.limitExceeded);
    expect(h.s.calls.where((x) => x == 'write').length, 1);
  });
  test('A09 byte validation precedes bound write', () async {
    final h = Harness();
    h.failed(
        await h.run({'a': []},
            source:
                Stream.value(ArchiveEntry('a', 'file', Stream.value([256])))),
        ImportCode.invalidEntry);
    expect(h.s.calls, ['begin', 'rollback']);
  });
  test('A10 short and corrupted content integrity', () async {
    for (final bytes in [
      [1],
      [1, 9]
    ]) {
      final h = Harness();
      h.failed(
          await h.run({
            'a': [1, 2]
          }, source: archive({'a': bytes})),
          ImportCode.integrityMismatch);
      expect(h.i.hashes, bytes.length == 2 ? 1 : 0);
    }
  });
  test('A11 cancellation initial and after begin', () async {
    final h = Harness();
    h.c.cancelled = true;
    h.failed(
        await h.run({
          'a': [1]
        }),
        ImportCode.cancelled,
        stage: false);
    expect(h.i.verifies, 0);
    final q = Harness();
    q.s.hook = (op) async {
      if (op == 'begin') q.c.cancelled = true;
    };
    q.failed(
        await q.run({
          'a': [1]
        }),
        ImportCode.cancelled);
    expect(q.s.calls, ['begin', 'rollback']);
  });
  test('A12 cancellation after write prevents publication', () async {
    final h = Harness();
    h.s.hook = (op) async {
      if (op == 'write') h.c.cancelled = true;
    };
    h.failed(
        await h.run({
          'a': [1]
        }),
        ImportCode.cancelled);
    expect(h.i.hashes, 0);
  });
  test('A13 atomic publish only after source complete', () async {
    final h = Harness();
    final listening = Completer<void>();
    final wrote = Completer<void>();
    final controller =
        StreamController<ArchiveEntry>(onListen: () => release(listening));
    h.s.hook = (op) async {
      if (op == 'write') release(wrote);
    };
    final pending = observed(h.run({
      'a': [1]
    }, source: controller.stream));
    Future<void>? closing;
    Future<void> closeSource() => closing ??= observed(controller.close());
    try {
      await bounded(listening.future);
      controller.add(ArchiveEntry('a', 'file', Stream.value([1])));
      await bounded(wrote.future);
      await bounded(Future<void>.delayed(Duration.zero));
      expect(h.s.live, {
        'old.txt': [9]
      });
      expect(h.s.calls, isNot(contains('publish')));
      await bounded(closeSource());
      final r = await bounded(pending);
      expect(r.code, ImportCode.ok);
      expect(h.s.live, {
        'a': [1]
      });
    } finally {
      h.c.cancelled = true;
      h.s.hook = null;
      await settle(closeSource());
      await settle(pending);
    }
  });
  test('A14 storage failure rollback and reusable importer', () async {
    for (final op in ['begin', 'write', 'publish']) {
      final h = Harness();
      h.s.fail = op;
      final r = await h.run({
        'a': [1]
      });
      expect(r.code, ImportCode.storageUnavailable);
      expect(r.files, 0);
      expect(r.bytes, 0);
      expect(h.s.live, {
        'old.txt': [9]
      });
      expect(h.s.stages, isEmpty);
      expect(h.s.calls.where((x) => x == 'rollback').length,
          op == 'begin' ? 0 : 1);
      h.s.fail = null;
      final next = await h.run({
        'b': [2]
      });
      expect(next.code, ImportCode.ok);
      expect(h.s.live, {
        'b': [2]
      });
    }
  });
  test('A15 source entry and chunk failures rollback', () async {
    for (final source in [
      Stream<ArchiveEntry>.error(SourceUnavailable()),
      Stream.value(ArchiveEntry(
          'a', 'file', Stream<List<int>>.error(SourceUnavailable())))
    ]) {
      final h = Harness();
      h.failed(
          await h.run({
            'a': [1]
          }, source: source),
          ImportCode.sourceUnavailable);
    }
  });
  test('A16 busy holds across rollback and then releases', () async {
    final h = Harness();
    final hold = Completer<void>();
    final entered = Completer<void>();
    h.s.hook = (op) async {
      if (op == 'begin') {
        release(entered);
        await bounded(hold.future);
      }
    };
    final pending = observed(h.run({
      'a': [1]
    }));
    try {
      await bounded(entered.future);
      final token = Cancellation()..cancelled = true;
      final text = manifest(h.i, {
        'b': [2]
      });
      final r = await bounded(h.importer.import(
          text,
          'bad',
          archive({
            'b': [2]
          }),
          token));
      expect(r.code, ImportCode.busy);
      expect(h.i.verifies, 1);
      expect(h.s.calls, ['begin']);
      release(hold);
      expect((await bounded(pending)).code, ImportCode.ok);
      h.s.hook = null;
      expect(
          (await h.run({
            'b': [2]
          }))
              .code,
          ImportCode.ok);
    } finally {
      release(hold);
      h.c.cancelled = true;
      h.s.hook = null;
      await settle(pending);
    }
    final q = Harness();
    final rollbackStarted = Completer<void>();
    final rollbackRelease = Completer<void>();
    q.s.hook = (op) async {
      if (op == 'rollback') {
        release(rollbackStarted);
        await bounded(rollbackRelease.future);
      }
    };
    final failing = observed(q.run({
      'a': [1]
    }, source: Stream<ArchiveEntry>.empty()));
    try {
      await bounded(rollbackStarted.future);
      expect(
          (await q.run({
            'a': [1]
          }))
              .code,
          ImportCode.busy);
      expect(q.i.verifies, 1);
      release(rollbackRelease);
      expect((await bounded(failing)).code, ImportCode.invalidEntry);
      q.s.hook = null;
      expect(
          (await q.run({
            'a': [1]
          }))
              .code,
          ImportCode.ok);
    } finally {
      release(rollbackRelease);
      q.c.cancelled = true;
      q.s.hook = null;
      await settle(failing);
    }
  });
  test('A17 successful publish wins cancellation during commit', () async {
    final h = Harness();
    h.s.hook = (op) async {
      if (op == 'publish') h.c.cancelled = true;
    };
    final r = await h.run({
      'a': [1]
    });
    expect(r.code, ImportCode.ok);
    expect(r.files, 1);
    expect(r.bytes, 1);
    expect(h.s.live, {
      'a': [1]
    });
    expect(h.s.calls, isNot(contains('rollback')));
  });
  test('A18 exact upper bounds reordered files and empty chunks', () async {
    final h = Harness();
    final files = {
      for (var n = 0; n < 4; n++) 'a$n': List<int>.filled(65536, n)
    };
    final source = Stream.fromIterable([
      for (final e in files.entries.toList().reversed)
        ArchiveEntry(e.key, 'file', Stream.fromIterable([<int>[], e.value]))
    ]);
    final r = await h.run(files, source: source);
    expect(r.code, ImportCode.ok);
    expect(r.files, 4);
    expect(r.bytes, 262144);
    expect(h.s.live, files);
  });
  test('A19 defensive immutable writes and streamed timing', () async {
    final h = Harness();
    final started = Completer<void>();
    final hold = Completer<void>();
    final callerBuffer = <int>[1];
    var requestedNextChunk = false;
    h.s.hook = (op) async {
      if (op == 'write' && !started.isCompleted) {
        release(started);
        await bounded(hold.future);
      }
    };
    Stream<List<int>> chunks() async* {
      yield callerBuffer;
      requestedNextChunk = true;
      yield [2];
    }

    final pending = observed(h.run({
      'a': [1, 2]
    }, source: Stream.value(ArchiveEntry('a', 'file', chunks()))));
    try {
      await bounded(started.future);
      await bounded(Future<void>.delayed(Duration.zero));
      expect(requestedNextChunk, false,
          reason:
              'Do not request the next chunk while its prior write is pending.');
      expect(h.s.live, {
        'old.txt': [9]
      });
      expect(h.s.calls, isNot(contains('publish')));
      callerBuffer[0] = 9;
      expect(h.s.writeInputs.first, [1]);
      expect(() => h.s.writeInputs.first.add(3), throwsUnsupportedError);
      release(hold);
      final r = await bounded(pending);
      expect(r.code, ImportCode.ok);
      expect(h.s.calls, ['begin', 'write', 'write', 'publish']);
      expect(
          h.s.live,
          {
            'a': [1, 2]
          },
          reason:
              'Caller mutation after write starts must not change staged bytes.');
    } finally {
      release(hold);
      h.c.cancelled = true;
      h.s.hook = null;
      await settle(pending);
    }
  });
  test('A20 failure await precedes concurrent cancellation', () async {
    final h = Harness();
    h.s.fail = 'write';
    h.s.hook = (op) async {
      if (op == 'write') h.c.cancelled = true;
    };
    h.failed(
        await h.run({
          'a': [1]
        }),
        ImportCode.storageUnavailable);
  });
}
