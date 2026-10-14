import 'dart:async';

class Actor {
  final String id;
  final String owner;
  const Actor(this.id, this.owner);
}
class Transfer {
  final String id;
  final String from;
  final String to;
  final int amount;
  const Transfer(this.id, this.from, this.to, this.amount);
}
class BatchCommand {
  final String owner;
  final String key;
  final List<Transfer> transfers;
  BatchCommand(this.owner, this.key, List<Transfer> transfers)
      : transfers = List.unmodifiable(transfers);
}
class Account {
  final String id;
  final String owner;
  final int balance;
  const Account(this.id, this.owner, this.balance);
}
enum FailureCode {
  invalid, forbidden, conflict, missingAccount, insufficientFunds,
  balanceLimit, unavailable, internal,
}
class ValidatedBatch {
  final BatchCommand command;
  final String fingerprint;
  const ValidatedBatch(this.command, this.fingerprint);
}
class ValidationResult {
  final ValidatedBatch? batch;
  final FailureCode? failure;
  const ValidationResult.valid(ValidatedBatch value) : batch = value, failure = null;
  const ValidationResult.invalid() : batch = null, failure = FailureCode.invalid;
}
class Receipt {
  final String owner;
  final String key;
  final String fingerprint;
  final int transferCount;
  final Map<String, int> balances;
  Receipt(this.owner, this.key, this.fingerprint, this.transferCount,
      Map<String, int> balances) : balances = Map.unmodifiable(balances);
}
class BatchResult {
  final Receipt? receipt;
  final FailureCode? failure;
  final String? message;
  const BatchResult.success(Receipt value) : receipt = value, failure = null, message = null;
  const BatchResult.failed(FailureCode code) : receipt = null, failure = code,
      message = 'Batch could not be completed.';
}
abstract interface class BatchAuthorizer {
  Future<bool> canTransfer(Actor actor, String owner);
}
abstract interface class BatchTransaction {
  Account? account(String id);
  Receipt? receipt(String owner, String key);
  void putAccount(Account account);
  void putReceipt(Receipt receipt);
}
/// Serializes transactions across service instances. Callback mutations commit
/// together only when callback completes normally. A failed commit rolls back.
/// StoreUnavailable may also be thrown after a successful durable commit.
abstract interface class AtomicBatchStore {
  Future<T> transaction<T>(FutureOr<T> Function(BatchTransaction tx) callback);
}
class StoreUnavailable implements Exception {
  final String detail;
  const StoreUnavailable(this.detail);
}
class BatchRejected implements Exception {
  final FailureCode code;
  const BatchRejected(this.code);
}
