import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/contracts.dart';
import 'package:fixture_app/batch_service.dart';
import 'package:fixture_app/batch_validator.dart';
import 'support.dart';

const actor = Actor('member', 'team');
BatchCommand command({String key = 'request', int amount = 20}) =>
    BatchCommand('team', key, [Transfer('t1', 'a', 'b', amount)]);
class Harness {
  final MemoryStore store = MemoryStore([
    const Account('a', 'team', 100), const Account('b', 'team', 0),
    const Account('c', 'team', 20), const Account('foreign', 'other', 100),
    const Account('x', 'other', 50), const Account('y', 'other', 0),
  ]);
  final TestAuthorizer auth = TestAuthorizer();
  BatchService get service => BatchService(store, auth);
  Future<BatchResult> send(BatchCommand value) => service.submit(actor, value);
}
void failed(BatchResult result, FailureCode code) {
  expect(result.failure, code);
  expect(result.receipt, isNull);
  expect(result.message, 'Batch could not be completed.');
}
Receipt succeeded(BatchResult result) {
  expect(result.failure, isNull);
  expect(result.message, isNull);
  expect(result.receipt, isA<Receipt>());
  return result.receipt!;
}
Future<bool> observeEntered(
    Completer<void> entered, Future<BatchResult> pending) {
  return Future.any<bool>([
    entered.future.then((_) => true),
    pending.then((_) => false, onError: (Object error, StackTrace stack) => false),
  ]);
}
void main() {
  test('R01 validator accepts boundary batch size and amounts', () {
    final items = List.generate(20, (i) => Transfer('t$i', 'a', 'b', 1000000000));
    expect(BatchValidator().validate(BatchCommand('team', 'key', items)).batch, isNotNull);
  });
  test('R01 rejects invalid identifiers and transfer structures before storage', () async {
    final h = Harness();
    final invalid = [
      BatchCommand('', 'key', [const Transfer('t', 'a', 'b', 1)]),
      BatchCommand('team', ' key', [const Transfer('t', 'a', 'b', 1)]),
      BatchCommand('team', 'key', []),
      BatchCommand('team', 'key', List.generate(21, (i) => Transfer('t$i', 'a', 'b', 1))),
      BatchCommand('team', 'key', [const Transfer('t', 'a', 'a', 1)]),
      BatchCommand('team', 'key', [const Transfer('t', 'a', 'b', 0)]),
      BatchCommand('team', 'key', [const Transfer('t', 'a', 'b', -1)]),
      BatchCommand('team', 'key', [const Transfer('t', 'a', 'b', 1000000001)]),
      BatchCommand('team', 'key', [const Transfer('t', 'a', 'b', 1), const Transfer('t', 'b', 'a', 1)]),
      BatchCommand('team', 'key', [const Transfer(' t', 'a', 'b', 1)]),
      BatchCommand('team', 'key', [const Transfer('t', '', 'b', 1)]),
      BatchCommand('team', 'key', [const Transfer('t', 'a', 'b ', 1)]),
      BatchCommand('team', 'ke\u0000y', [const Transfer('t', 'a', 'b', 1)]),
    ];
    for (final value in invalid) { failed(await h.service.submit(Actor('member', value.owner), value), FailureCode.invalid); }
    expect(h.store.calls, 0);
    expect(h.store.accounts['a']!.balance, 100);
  });
  test('R02 fingerprints preserve payload fields without delimiter collisions', () {
    final v = BatchValidator();
    String fp(BatchCommand c) {
      final result = v.validate(c);
      expect(result.failure, isNull);
      expect(result.batch, isA<ValidatedBatch>());
      return result.batch!.fingerprint;
    }
    expect(fp(command()), fp(command(key: 'different')));
    final base = fp(command());
    final changes = [
      BatchCommand('other', 'request', [const Transfer('t1', 'a', 'b', 20)]),
      BatchCommand('team', 'request', [const Transfer('t2', 'a', 'b', 20)]),
      BatchCommand('team', 'request', [const Transfer('t1', 'c', 'b', 20)]),
      BatchCommand('team', 'request', [const Transfer('t1', 'a', 'c', 20)]),
      command(amount: 21),
    ];
    for (final value in changes) { expect(fp(value), isNot(base)); }
    expect(fp(BatchCommand('team', 'k', [const Transfer('a|b', 'c', 'd', 1)])),
        isNot(fp(BatchCommand('team', 'k', [const Transfer('a', 'b|c', 'd', 1)]))));
  });
  test('R03 owner mismatch is rejected without authorization or storage', () async {
    final h = Harness();
    failed(await h.service.submit(const Actor('member', 'other'), command()), FailureCode.forbidden);
    expect(h.auth.calls, 0); expect(h.store.calls, 0);
  });
  test('R03 denied and malformed request remains forbidden before validation', () async {
    final h = Harness(); h.auth.allowed = false;
    failed(await h.send(BatchCommand('team', '', [])), FailureCode.forbidden);
    expect(h.auth.calls, 1); expect(h.store.calls, 0);
  });
  test('R03 awaited authorization prevents early store access', () async {
    final h = Harness(); final gate = Completer<void>(); final entered = Completer<void>();
    h.auth.delay = () { entered.complete(); return gate.future; };
    final pending = h.send(command());
    try {
      expect(await observeEntered(entered, pending), isTrue, reason: 'Expected asynchronous dependency to be invoked.');
      expect(h.store.calls, 0);
    } finally {
      gate.complete();
      if (!entered.isCompleted) entered.complete();
      await pending;
    }
    expect((await pending).receipt, isNotNull);
  });
  test('R03 revocation blocks committed replay', () async {
    final h = Harness(); expect((await h.send(command())).receipt, isNotNull);
    final calls = h.store.calls; h.auth.allowed = false;
    failed(await h.send(command()), FailureCode.forbidden);
    expect(h.auth.calls, 2); expect(h.store.calls, calls);
  });
  test('R03 foreign source and destination are rejected atomically', () async {
    for (final transfer in [const Transfer('t', 'foreign', 'b', 10), const Transfer('t', 'a', 'foreign', 10)]) {
      final h = Harness();
      failed(await h.send(BatchCommand('team', 'k', [transfer])), FailureCode.forbidden);
      expect(h.store.accounts['a']!.balance, 100);
      expect(h.store.accounts['foreign']!.balance, 100); expect(h.store.receipts, isEmpty);
    }
  });
  test('R04 successful multi-account batch conserves money and snapshots receipt', () async {
    final h = Harness();
    final result = await h.send(BatchCommand('team', 'k', [
      const Transfer('one', 'a', 'b', 30), const Transfer('two', 'c', 'b', 10)]));
    expect(result.failure, isNull); expect(result.message, isNull);
    final receipt = succeeded(result);
    expect(receipt.owner, 'team'); expect(receipt.key, 'k'); expect(receipt.transferCount, 2);
    expect(receipt.fingerprint, isNotEmpty); expect(receipt.balances, {'a': 70, 'b': 40, 'c': 10});
    expect(h.store.accounts['a']!.balance + h.store.accounts['b']!.balance + h.store.accounts['c']!.balance, 120);
    expect(() => receipt.balances['a'] = 999, throwsUnsupportedError);
    await h.send(command(key: 'later', amount: 10));
    expect(receipt.balances['a'], 70);
  });
  test('R04 net balances allow incoming funds and cycles regardless of order', () async {
    final h = Harness();
    final result = await h.send(BatchCommand('team', 'net', [
      const Transfer('out', 'b', 'c', 30), const Transfer('in', 'a', 'b', 30),
      const Transfer('cycle1', 'b', 'a', 200), const Transfer('cycle2', 'a', 'b', 200)]));
    expect(succeeded(result).balances, {'a': 70, 'b': 0, 'c': 50});
  });
  test('R04 missing account rejects whole batch', () async {
    final h = Harness();
    failed(await h.send(BatchCommand('team', 'k', [const Transfer('one', 'a', 'b', 10), const Transfer('two', 'c', 'missing', 1)])), FailureCode.missingAccount);
    expect(h.store.accounts['a']!.balance, 100); expect(h.store.receipts, isEmpty);
  });
  test('R04 insufficient funds rejects whole batch after valid prefix', () async {
    final h = Harness();
    failed(await h.send(BatchCommand('team', 'k', [const Transfer('one', 'a', 'b', 10), const Transfer('two', 'c', 'b', 21)])), FailureCode.insufficientFunds);
    expect(h.store.accounts['a']!.balance, 100); expect(h.store.accounts['b']!.balance, 0);
    expect(h.store.accounts['c']!.balance, 20); expect(h.store.receipts, isEmpty);
  });
  test('R04 upper balance bound rejects credit without debit', () async {
    final h = Harness(); h.store.accounts['b'] = const Account('b', 'team', 1000000000);
    failed(await h.send(command(amount: 1)), FailureCode.balanceLimit);
    expect(h.store.accounts['a']!.balance, 100); expect(h.store.accounts['b']!.balance, 1000000000);
    expect(h.store.receipts, isEmpty);
  });
  test('R05 success persists receipt and accounts in one transaction', () async {
    final h = Harness(); final result = await h.send(command());
    expect(h.store.calls, 1); expect(h.store.receipts.length, 1);
    expect(h.store.receipts.values.single.balances, succeeded(result).balances);
    expect(h.store.accounts['a']!.balance, 80); expect(h.store.accounts['b']!.balance, 20);
  });
  test('R06 reordered replay returns original receipt after later account changes', () async {
    final h = Harness(); final transfers = [const Transfer('one', 'a', 'b', 10), const Transfer('two', 'c', 'b', 5)];
    final first = succeeded(await h.send(BatchCommand('team', 'k', transfers)));
    await h.send(command(key: 'later', amount: 10));
    final replay = succeeded(await h.send(BatchCommand('team', 'k', transfers.reversed.toList())));
    expect(replay.balances, first.balances); expect(replay.fingerprint, first.fingerprint);
    expect(replay.transferCount, first.transferCount); expect(h.store.accounts['a']!.balance, 80);
  });
  test('R06 changed payload conflicts without moving money', () async {
    final h = Harness(); await h.send(command());
    failed(await h.send(command(amount: 21)), FailureCode.conflict);
    expect(h.store.accounts['a']!.balance, 80); expect(h.store.receipts.length, 1);
  });
  test('R06 invalid payload with committed key stays invalid', () async {
    final h = Harness(); await h.send(command());
    failed(await h.send(command(amount: 0)), FailureCode.invalid);
    expect(h.store.calls, 1); expect(h.store.accounts['a']!.balance, 80);
  });
  test('R06 same key is independent across owners', () async {
    final h = Harness(); await h.send(command());
    final result = await h.service.submit(const Actor('second', 'other'),
        BatchCommand('other', 'request', [const Transfer('t1', 'x', 'y', 10)]));
    expect(succeeded(result).owner, 'other'); expect(h.store.receipts.length, 2);
    expect(h.store.accounts['x']!.balance, 40);
  });
  test('R07 concurrent same payload across instances applies once', () async {
    final h = Harness();
    final results = await Future.wait(List.generate(8, (_) => h.service.submit(actor, command())));
    expect(results.every((r) => r.receipt != null), isTrue);
    for (final r in results) { expect(succeeded(r).balances, {'a': 80, 'b': 20}); }
    expect(h.store.accounts['a']!.balance, 80); expect(h.store.receipts.length, 1);
  });
  test('R07 conflicting concurrent requests have one winner', () async {
    final h = Harness();
    final results = await Future.wait([h.send(command(amount: 20)), h.send(command(amount: 30))]);
    expect(results.where((r) => r.receipt != null).length, 1);
    expect(results.where((r) => r.failure == FailureCode.conflict).length, 1);
    final balance = succeeded(results.singleWhere((r) => r.receipt != null)).balances['a'];
    expect(h.store.accounts['a']!.balance, balance); expect(h.store.receipts.length, 1);
  });
  test('R07 competing keys cannot overspend shared balance', () async {
    final h = Harness();
    final results = await Future.wait([h.send(command(key: 'one', amount: 80)), h.send(command(key: 'two', amount: 80))]);
    expect(results.where((r) => r.receipt != null).length, 1);
    expect(results.where((r) => r.failure == FailureCode.insufficientFunds).length, 1);
    expect(h.store.accounts['a']!.balance, 20); expect(h.store.receipts.length, 1);
  });
  test('R08 delayed failure before commit rolls back and new instance retries', () async {
    final h = Harness(); final gate = Completer<void>(); final entered = Completer<void>();
    h.store.beforeCommit = () async { entered.complete(); await gate.future; throw const StoreUnavailable('private failure'); };
    final pending = h.send(command());
    try { expect(await observeEntered(entered, pending), isTrue, reason: 'Expected asynchronous dependency to be invoked.'); expect(h.store.accounts['a']!.balance, 100); expect(h.store.receipts, isEmpty); }
    finally {
      gate.complete();
      if (!entered.isCompleted) entered.complete();
      await pending;
    }
    failed(await pending, FailureCode.unavailable);
    expect(h.store.calls, 1); expect(h.store.accounts['a']!.balance, 100);
    h.store.beforeCommit = null;
    expect(succeeded(await h.service.submit(actor, command())).balances['a'], 80);
  });
  test('R08 delayed lost acknowledgement replays after restart without duplicate debit', () async {
    final h = Harness(); final gate = Completer<void>(); final entered = Completer<void>();
    h.store.afterCommit = () async { entered.complete(); await gate.future; throw const StoreUnavailable('private acknowledgement'); };
    final pending = h.send(command());
    try { expect(await observeEntered(entered, pending), isTrue, reason: 'Expected asynchronous dependency to be invoked.'); expect(h.store.accounts['a']!.balance, 80); expect(h.store.receipts.length, 1); }
    finally {
      gate.complete();
      if (!entered.isCompleted) entered.complete();
      await pending;
    }
    failed(await pending, FailureCode.unavailable); expect(h.store.calls, 1);
    h.store.afterCommit = null;
    final retry = await h.service.submit(actor, command());
    expect(succeeded(retry).balances, {'a': 80, 'b': 20}); expect(h.store.accounts['a']!.balance, 80);
  });
  test('R08 changed retry after lost acknowledgement conflicts and queue recovers', () async {
    final h = Harness(); h.store.afterCommit = () async { throw const StoreUnavailable('secret'); };
    failed(await h.send(command()), FailureCode.unavailable); h.store.afterCommit = null;
    failed(await h.service.submit(actor, command(amount: 25)), FailureCode.conflict);
    expect(succeeded(await h.send(command(key: 'new', amount: 10))).balances['a'], 70);
    expect(h.store.receipts.length, 2);
  });
  test('R09 authorization exceptions are sanitized without storage', () async {
    final h = Harness(); h.auth.error = StateError('secret token and owner');
    failed(await h.send(command()), FailureCode.internal); expect(h.store.calls, 0);
    h.auth.error = const StoreUnavailable('secret');
    failed(await h.send(command()), FailureCode.unavailable);
  });
  test('R09 transaction exceptions are sanitized rollback and do not poison future calls', () async {
    final h = Harness(); h.store.beforeCommit = () async { throw StateError('secret balance'); };
    failed(await h.send(command()), FailureCode.internal);
    expect(h.store.accounts['a']!.balance, 100); expect(h.store.receipts, isEmpty);
    h.store.beforeCommit = null; expect((await h.send(command())).receipt, isNotNull);
  });
  test('R09 validator exceptions are sanitized before storage', () async {
    final h = Harness();
    final service = BatchService(h.store, h.auth, validator: ExplodingValidator());
    failed(await service.submit(actor, command()), FailureCode.internal); expect(h.store.calls, 0);
  });
}
class ExplodingValidator extends BatchValidator {
  @override
  ValidationResult validate(BatchCommand command) => throw StateError('secret input');
}
