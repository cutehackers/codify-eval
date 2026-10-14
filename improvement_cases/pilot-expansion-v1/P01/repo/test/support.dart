import 'dart:async';
import 'package:fixture_app/contracts.dart';

class TestAuthorizer implements BatchAuthorizer {
  bool allowed = true;
  int calls = 0;
  Object? error;
  Future<void> Function()? delay;
  @override
  Future<bool> canTransfer(Actor actor, String owner) async {
    calls++;
    if (delay != null) await delay!();
    if (error != null) throw error!;
    return allowed;
  }
}
class MemoryStore implements AtomicBatchStore {
  Map<String, Account> accounts;
  Map<String, Receipt> receipts = {};
  int calls = 0;
  Future<void> Function()? beforeCommit;
  Future<void> Function()? afterCommit;
  Future<void> _tail = Future<void>.value();
  MemoryStore(List<Account> initial) : accounts = {for (final a in initial) a.id: a};
  @override
  Future<T> transaction<T>(FutureOr<T> Function(BatchTransaction tx) callback) async {
    calls++;
    final previous = _tail;
    final release = Completer<void>();
    _tail = release.future;
    await previous;
    try {
      final tx = MemoryTransaction(Map.of(accounts), Map.of(receipts));
      final result = await callback(tx);
      if (beforeCommit != null) await beforeCommit!();
      accounts = tx.accounts;
      receipts = tx.receipts;
      if (afterCommit != null) await afterCommit!();
      return result;
    } finally {
      release.complete();
    }
  }
}
class MemoryTransaction implements BatchTransaction {
  final Map<String, Account> accounts;
  final Map<String, Receipt> receipts;
  MemoryTransaction(this.accounts, this.receipts);
  String slot(String owner, String key) => '$owner\u0000$key';
  @override
  Account? account(String id) => accounts[id];
  @override
  Receipt? receipt(String owner, String key) => receipts[slot(owner, key)];
  @override
  void putAccount(Account account) { accounts[account.id] = account; }
  @override
  void putReceipt(Receipt receipt) { receipts[slot(receipt.owner, receipt.key)] = receipt; }
}
