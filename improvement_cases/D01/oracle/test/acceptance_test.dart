import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

class Controlled implements SearchService {
  Controlled() {
    addTearDown(() {
      for (final call in calls) {
        if (!call.isCompleted) call.complete([]);
      }
    });
  }
  final queries = <String>[];
  final calls = <Completer<List<String>>>[];
  @override
  Future<List<String>> search(String query) {
    queries.add(query);
    final call = Completer<List<String>>();
    calls.add(call);
    return call.future;
  }
}

void main() {
  test('initial, normalized request, exact transitions and defensive snapshot',
      () async {
    final s = Controlled();
    final c = SearchController(s);
    expect(c.state.phase, SearchPhase.idle);
    expect(c.state.query, '');
    expect(c.state.items, isEmpty);
    expect(c.state.message, isNull);
    final phases = <SearchPhase>[];
    c.addListener(() => phases.add(c.state.phase));
    final pending = c.search('  tea  ');
    expect(s.queries, ['tea']);
    expect(c.state.query, 'tea');
    expect(c.state.items, isEmpty);
    expect(c.state.message, isNull);
    final returned = ['tea'];
    s.calls.single.complete(returned);
    await pending;
    final snapshot = c.state;
    returned.add('mutated');
    expect(snapshot.items, ['tea']);
    expect(() => snapshot.items.add('x'), throwsUnsupportedError);
    expect(phases, [SearchPhase.loading, SearchPhase.ready]);
    final next = c.search('coffee');
    expect(snapshot.items, ['tea']);
    expect(c.state.items, isEmpty);
    s.calls.last.complete([]);
    await next;
    expect(c.state.phase, SearchPhase.ready);
    expect(c.state.items, isEmpty);
    c.dispose();
  });
  test(
      'newest invocation wins, including same-query overlap and stale failures',
      () async {
    for (final staleFails in [false, true]) {
      final s = Controlled();
      final c = SearchController(s);
      var notifications = 0;
      c.addListener(() => notifications++);
      final a = c.search('same');
      final b = c.search('same');
      s.calls[1].complete(['latest']);
      await b;
      final count = notifications;
      if (staleFails) {
        s.calls[0].completeError(StateError('secret'));
      } else {
        s.calls[0].complete(['stale']);
      }
      await a;
      expect(c.state.items, ['latest']);
      expect(c.state.message, isNull);
      expect(notifications, count);
      c.dispose();
    }
  });
  test(
      'different-query stale success cannot clear newer failure and retry uses failure query',
      () async {
    final s = Controlled();
    final c = SearchController(s);
    var n = 0;
    c.addListener(() => n++);
    final a = c.search('old');
    final b = c.search(' new ');
    s.calls[1].completeError(StateError('token=abc'));
    await b;
    expect(c.state.phase, SearchPhase.failed);
    expect(c.state.query, 'new');
    expect(c.state.message, 'Search failed');
    expect(c.state.items, isEmpty);
    s.calls[0].complete(['old']);
    await a;
    expect(c.state.phase, SearchPhase.failed);
    final retry = c.retry();
    expect(s.queries, ['old', 'new', 'new']);
    expect(c.state.phase, SearchPhase.loading);
    expect(c.state.message, isNull);
    s.calls.last.complete(['recovered']);
    await retry;
    expect(c.state.items, ['recovered']);
    final beforeReadyRetry = n;
    final readyRetry = c.retry();
    expect(s.calls.length, 3);
    expect(n, beforeReadyRetry);
    await readyRetry.timeout(const Duration(seconds: 1));
    expect(n, beforeReadyRetry);
    c.dispose();
  });
  test(
      'empty input invalidates pending work and retry outside failure is no-op',
      () async {
    final s = Controlled();
    final c = SearchController(s);
    var n = 0;
    c.addListener(() => n++);
    final idleRetry = c.retry();
    expect(s.calls, isEmpty);
    expect(n, 0);
    await idleRetry.timeout(const Duration(seconds: 1));
    final p = c.search('x');
    expect(n, 1);
    final loadingRetry = c.retry();
    expect(s.calls.length, 1);
    expect(n, 1);
    await loadingRetry.timeout(const Duration(seconds: 1));
    expect(n, 1);
    final clear = c.search('  ');
    expect(s.calls.length, 1);
    expect(n, 2);
    await clear.timeout(const Duration(seconds: 1));
    expect(n, 2);
    expect(c.state.phase, SearchPhase.idle);
    expect(c.state.query, '');
    expect(c.state.items, isEmpty);
    expect(c.state.message, isNull);
    final count = n;
    s.calls.single.completeError(StateError('obsolete'));
    await p;
    expect(n, count);
    expect(c.state.phase, SearchPhase.idle);
    final clearedRetry = c.retry();
    expect(s.calls.length, 1);
    expect(n, count);
    await clearedRetry.timeout(const Duration(seconds: 1));
    expect(n, count);
    c.dispose();
  });
  test(
      'dispose blocks state writes, notifications and future calls, consumes pending errors',
      () async {
    for (final fails in [false, true]) {
      final s = Controlled();
      final c = SearchController(s);
      var n = 0;
      c.addListener(() => n++);
      final p = c.search('x');
      final before = c.state;
      final count = n;
      c.dispose();
      c.dispose();
      if (fails) {
        s.calls.single.completeError(StateError('late'));
      } else {
        s.calls.single.complete(['late']);
      }
      await p;
      final disposedSearch = c.search('y');
      expect(s.calls.length, 1);
      await disposedSearch.timeout(const Duration(seconds: 1));
      final disposedRetry = c.retry();
      expect(s.calls.length, 1);
      await disposedRetry.timeout(const Duration(seconds: 1));
      expect(identical(c.state, before), isTrue);
      expect(n, count);
      expect(s.calls.length, 1);
    }
  });
  test(
      'current failure and retry failure each notify exactly once per transition',
      () async {
    final s = Controlled();
    final c = SearchController(s);
    final phases = <SearchPhase>[];
    c.addListener(() => phases.add(c.state.phase));
    final first = c.search(' fail ');
    expect(phases, [SearchPhase.loading]);
    s.calls[0].completeError(StateError('secret-one'));
    await first;
    expect(phases, [SearchPhase.loading, SearchPhase.failed]);
    final retry = c.retry();
    expect(s.queries, ['fail', 'fail']);
    expect(
        phases, [SearchPhase.loading, SearchPhase.failed, SearchPhase.loading]);
    s.calls[1].completeError(StateError('secret-two'));
    await retry;
    expect(phases, [
      SearchPhase.loading,
      SearchPhase.failed,
      SearchPhase.loading,
      SearchPhase.failed
    ]);
    expect(c.state.message, 'Search failed');
    expect(c.state.items, isEmpty);
    c.dispose();
  });
}
