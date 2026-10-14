import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

void main() {
  test('newest wins success and failure', () async {
    final requests = <Completer<List<String>>>[];
    final c = SearchController((_) {
      final p = Completer<List<String>>();
      requests.add(p);
      return p.future;
    });
    final first = c.search('a');
    final latest = c.search('b');
    requests[1].complete(['latest']);
    await latest;
    requests[0].complete(['stale']);
    await first;
    expect(c.results, ['latest']);
    expect(c.busy, false);
    final old = c.search('c');
    final next = c.search('d');
    requests[3].complete(['d']);
    await next;
    requests[2].completeError(StateError('old'));
    await old;
    expect(c.error, isNull);
    expect(c.results, ['d']);
    c.dispose();
  });
  test('failure retry disposal', () async {
    int calls = 0;
    final requests = <Completer<List<String>>>[];
    final c = SearchController((_) {
      calls++;
      final p = Completer<List<String>>();
      requests.add(p);
      return p.future;
    });
    final fail = c.search('same');
    requests[0].completeError(StateError('x'));
    await fail;
    expect(c.error, '검색 실패');
    final retry = c.search('same');
    expect(c.error, isNull);
    expect(c.busy, true);
    requests[1].complete(['ok']);
    await retry;
    expect(c.results, ['ok']);
    final pending = c.search('dispose');
    c.dispose();
    requests[2].complete(['late']);
    await pending;
    await c.search('ignored');
    expect(calls, 3);
  });
}
