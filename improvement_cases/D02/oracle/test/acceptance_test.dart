import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

class Policy implements AccessPolicy {
  bool readAllowed = true, writeAllowed = true;
  final readChecks = <String>[], writeChecks = <String>[];
  @override
  bool canRead(String owner) {
    readChecks.add(owner);
    return readAllowed;
  }

  @override
  bool canWrite(String owner) {
    writeChecks.add(owner);
    return writeAllowed;
  }
}

class Files implements DocumentFiles {
  Files() {
    addTearDown(() {
      hold = false;
      for (final gate in gates) {
        if (!gate.isCompleted) gate.complete();
      }
    });
  }
  final data = <String, String>{};
  final operations = <String>[];
  final gates = <Completer<void>>[];
  bool hold = false, failRead = false, failWrite = false;
  @override
  Future<String?> read(String key) async {
    operations.add('read:$key');
    if (failRead) throw FileSystemException('secret-token', '/private/alice');
    return data[key];
  }

  @override
  Future<void> write(String key, String contents) async {
    operations.add('write:$key');
    if (hold) {
      final gate = Completer<void>();
      gates.add(gate);
      await gate.future;
    }
    if (failWrite) throw FileSystemException('secret-token', '/private/alice');
    data[key] = contents;
  }
}

class FaultOperations extends SystemDocumentFileOperations {
  final String fault;
  FaultOperations(this.fault);
  final writes = <String>[];
  final renames = <String>[];
  final deletes = <String>[];
  final flushValues = <bool>[];
  @override
  Future<void> write(File file, String contents, {required bool flush}) async {
    writes.add(file.path);
    flushValues.add(flush);
    if (fault == 'partial-write') {
      await super.write(file, 'partial-secret', flush: flush);
      throw FileSystemException('write-secret', file.path);
    }
    if (fault == 'flush') {
      await super.write(file, contents, flush: false);
      throw FileSystemException('flush-secret', file.path);
    }
    await super.write(file, contents, flush: flush);
  }

  @override
  Future<void> rename(File file, String destination) async {
    renames.add(destination);
    if (fault == 'rename')
      throw FileSystemException('rename-secret', file.path);
    await super.rename(file, destination);
  }

  @override
  Future<void> delete(File file) async {
    deletes.add(file.path);
    await super.delete(file);
  }
}

Future<void> turn() async {
  for (var i = 0; i < 8; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  test(
      'permission is fresh, read/write independent, denial does no storage work',
      () async {
    final f = Files(), p = Policy();
    final r = DocumentRepository(f, p);
    p.readAllowed = false;
    await r.save('alice', 'note', 'a');
    expect(p.writeChecks, ['alice']);
    expect(p.readChecks, isEmpty);
    await expectLater(r.load('alice', 'note'), throwsA(isA<AccessDenied>()));
    expect(f.operations, ['write:alice.note.json']);
    p.readAllowed = true;
    expect(await r.load('alice', 'note'), 'a');
    p.writeAllowed = false;
    await expectLater(
        r.save('alice', 'note', 'b'), throwsA(isA<AccessDenied>()));
    p.readAllowed = false;
    await expectLater(r.load('alice', 'note'), throwsA(isA<AccessDenied>()));
    expect(f.operations, ['write:alice.note.json', 'read:alice.note.json']);
    expect(AccessDenied().toString(), 'Access denied');
  });
  test('invalid identifiers reject before policy or storage', () async {
    final f = Files(), p = Policy();
    final r = DocumentRepository(f, p);
    final invalid = [
      '',
      '../alice',
      'a/b',
      'A',
      'a.b',
      'a\\b',
      'a ' * 2,
      'a' * 33,
      '1alice',
      'alice\n'
    ];
    for (final value in invalid) {
      await expectLater(r.save(value, 'note', 'x'), throwsArgumentError);
      await expectLater(r.load('alice', value), throwsArgumentError);
      await expectLater(r.save('alice', value, 'x'), throwsArgumentError);
      await expectLater(r.load(value, 'note'), throwsArgumentError);
    }
    expect(f.operations, isEmpty);
    expect(p.readChecks, isEmpty);
    expect(p.writeChecks, isEmpty);
    await r.save('a_1-z', 'b_2-x', '');
    expect(await r.load('a_1-z', 'b_2-x'), '');
  });
  test('owner isolation, versioned persisted identity and reopen without cache',
      () async {
    final f = Files(), p = Policy();
    final r = DocumentRepository(f, p);
    const body = '한글 \n "quotes" \u0000';
    await r.save('alice', 'shared', body);
    await r.save('bob', 'shared', 'other');
    expect(jsonDecode(f.data['alice.shared.json']!),
        {'version': 1, 'owner': 'alice', 'id': 'shared', 'body': body});
    final reopened = DocumentRepository(f, p);
    expect(await reopened.load('alice', 'shared'), body);
    expect(await reopened.load('bob', 'shared'), 'other');
    expect(await reopened.load('alice', 'missing'), isNull);
    f.data['alice.shared.json'] = jsonEncode(
        {'version': 1, 'owner': 'alice', 'id': 'shared', 'body': 'external'});
    expect(await r.load('alice', 'shared'), 'external');
  });
  test('strict corrupt data rejects without leaking contents', () async {
    final f = Files(), p = Policy();
    final r = DocumentRepository(f, p);
    for (final raw in [
      'token-secret',
      '[]',
      jsonEncode(
          {'version': 1, 'owner': 'bob', 'id': 'note', 'body': 'secret'}),
      jsonEncode(
          {'version': 1, 'owner': 'alice', 'id': 'other', 'body': 'secret'}),
      jsonEncode(
          {'version': 2, 'owner': 'alice', 'id': 'note', 'body': 'secret'}),
      jsonEncode(
          {'version': 1.0, 'owner': 'alice', 'id': 'note', 'body': 'secret'}),
      jsonEncode({'version': 1, 'owner': 'alice', 'id': 'note', 'body': 42}),
      jsonEncode({
        'version': 1,
        'owner': 'alice',
        'id': 'note',
        'body': 'secret',
        'extra': true
      }),
      jsonEncode({'owner': 'alice', 'id': 'note', 'body': 'secret'})
    ]) {
      f.data['alice.note.json'] = raw;
      await expectLater(
          r.load('alice', 'note'),
          throwsA(isA<StorageFailure>().having(
              (e) => e.toString(), 'message', 'Storage operation failed')));
    }
  });
  test(
      'operations serialize by invocation, completion waits for persistence, failure recovers queue',
      () async {
    final f = Files(), p = Policy();
    final r = DocumentRepository(f, p);
    f.hold = true;
    var completed = false;
    final first = r.save('alice', 'note', 'one').then((_) => completed = true);
    final second = r.save('alice', 'note', 'two');
    final read = r.load('alice', 'note');
    await turn();
    expect(completed, isFalse);
    expect(f.operations, ['write:alice.note.json']);
    f.gates[0].complete();
    await first;
    await turn();
    expect(f.operations, ['write:alice.note.json', 'write:alice.note.json']);
    f.gates[1].complete();
    await second;
    expect(await read, 'two');
    f.hold = false;
    f.failWrite = true;
    await expectLater(
        r.save('alice', 'note', 'broken'),
        throwsA(isA<StorageFailure>().having(
            (e) => e.toString(), 'message', 'Storage operation failed')));
    f.failWrite = false;
    await r.save('alice', 'note', 'recovered');
    f.failRead = true;
    await expectLater(
        r.load('alice', 'note'),
        throwsA(isA<StorageFailure>().having(
            (e) => e.toString(), 'message', 'Storage operation failed')));
    f.failRead = false;
    expect(await r.load('alice', 'note'), 'recovered');
  });
  test(
      'disk roundtrip, malformed bytes, no temporary residue, failures redact paths',
      () async {
    final root = await Directory.systemTemp.createTemp('document-fixture-');
    addTearDown(() => root.delete(recursive: true));
    final p = Policy();
    final r = DocumentRepository(LocalDocumentFiles(root), p);
    await r.save('alice', 'note', 'first');
    await r.save('alice', 'note', 'second');
    expect(
        await DocumentRepository(LocalDocumentFiles(root), p)
            .load('alice', 'note'),
        'second');
    expect(
        (await root.list().toList())
            .map((e) => e.path.split(Platform.pathSeparator).last),
        ['alice.note.json']);
    await File('${root.path}/alice.note.json').writeAsString('{secret');
    await expectLater(r.load('alice', 'note'), throwsA(isA<StorageFailure>()));
    final absent = Directory('${root.path}/does-not-exist');
    await expectLater(
        LocalDocumentFiles(absent).write('alice.note.json', 'x'),
        throwsA(isA<StorageFailure>().having(
            (e) => e.toString(), 'message', 'Storage operation failed')));
  });
  test('file adapter rejects paths before IO and never follows a leaf symlink',
      () async {
    final root = await Directory.systemTemp.createTemp('document-link-');
    addTearDown(() => root.delete(recursive: true));
    final files = LocalDocumentFiles(root);
    for (final key in [
      '../escaped.json',
      'alice/other.json',
      'alice.note.json/child',
      'note.json'
    ]) {
      await expectLater(files.read(key), throwsArgumentError);
      await expectLater(files.write(key, 'x'), throwsArgumentError);
    }
    final target = File('${root.path}/protected.txt');
    await target.writeAsString('protected');
    final link = Link('${root.path}/alice.note.json');
    await link.create(target.path);
    await expectLater(
        files.read('alice.note.json'), throwsA(isA<StorageFailure>()));
    await expectLater(files.write('alice.note.json', 'overwrite'),
        throwsA(isA<StorageFailure>()));
    expect(await target.readAsString(), 'protected');
    expect(await link.exists(), isTrue);
    expect((await root.list().toList()).length, 2);
  });
  test(
      'authorized queued calls keep permission decisions and new calls recheck',
      () async {
    final f = Files(), p = Policy();
    final r = DocumentRepository(f, p);
    f.hold = true;
    final first = r.save('alice', 'note', 'one');
    final second = r.save('alice', 'note', 'two');
    p.writeAllowed = false;
    var deniedCompleted = false;
    final denied = r.save('alice', 'note', 'denied').then<Object?>((_) {
      deniedCompleted = true;
      return null;
    }, onError: (Object error) {
      deniedCompleted = true;
      return error;
    });
    await turn();
    expect(deniedCompleted, isTrue,
        reason:
            'Denied save must complete without waiting for permitted file work');
    expect(
        await denied.timeout(const Duration(seconds: 1)), isA<AccessDenied>());
    expect(p.writeChecks, ['alice', 'alice', 'alice']);
    expect(f.operations, ['write:alice.note.json']);
    f.gates[0].complete();
    await first;
    await turn();
    f.gates[1].complete();
    await second;
    expect(await r.load('alice', 'note'), 'two');
  });
  test('local adapter rejects invalid UTF-8 and non-file destinations',
      () async {
    final root = await Directory.systemTemp.createTemp('document-invalid-');
    addTearDown(() => root.delete(recursive: true));
    final files = LocalDocumentFiles(root);
    final target = File('${root.path}/alice.note.json');
    await target.writeAsBytes([0xff, 0xfe]);
    await expectLater(
        files.read('alice.note.json'), throwsA(isA<StorageFailure>()));
    await target.delete();
    await Directory(target.path).create();
    await expectLater(
        files.read('alice.note.json'), throwsA(isA<StorageFailure>()));
    await expectLater(
        files.write('alice.note.json', 'x'), throwsA(isA<StorageFailure>()));
    expect(await Directory(target.path).exists(), isTrue);
    expect((await root.list().toList()).length, 1);
  });
  test(
      'temporary write and flush failures preserve destination, clean residue and redact errors',
      () async {
    for (final fault in ['partial-write', 'flush']) {
      final root = await Directory.systemTemp.createTemp('document-atomic-');
      addTearDown(() => root.delete(recursive: true));
      final destination = File('${root.path}/alice.note.json');
      const previous = 'original Unicode 기록';
      await destination.writeAsString(previous);
      final operations = FaultOperations(fault);
      final files = LocalDocumentFiles(root, operations: operations);
      await expectLater(
          files.write('alice.note.json', 'replacement'),
          throwsA(isA<StorageFailure>().having(
              (e) => e.toString(), 'message', 'Storage operation failed')));
      expect(await destination.readAsString(), previous);
      expect(operations.writes, hasLength(1));
      expect(operations.writes.single, isNot(destination.path));
      expect(File(operations.writes.single).parent.path, root.path);
      expect(operations.flushValues, [true]);
      expect(operations.renames, isEmpty);
      expect(operations.deletes, contains(operations.writes.single));
      expect(
          (await root.list().toList()).map((e) => e.path), [destination.path]);
    }
  });
  test('rename failure cleans temporary file and redacts error', () async {
    final root = await Directory.systemTemp.createTemp('document-rename-');
    addTearDown(() => root.delete(recursive: true));
    final operations = FaultOperations('rename');
    final files = LocalDocumentFiles(root, operations: operations);
    await expectLater(
        files.write('alice.note.json', 'replacement'),
        throwsA(isA<StorageFailure>().having(
            (e) => e.toString(), 'message', 'Storage operation failed')));
    expect(operations.writes, hasLength(1));
    expect(File(operations.writes.single).parent.path, root.path);
    expect(operations.flushValues, [true]);
    expect(operations.renames, ['${root.path}/alice.note.json']);
    expect(operations.deletes, contains(operations.writes.single));
    expect(await root.list().toList(), isEmpty);
  });
}
