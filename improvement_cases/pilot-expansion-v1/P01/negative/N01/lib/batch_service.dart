import 'contracts.dart';
import 'batch_validator.dart';

class BatchService {
  final AtomicBatchStore store;
  final BatchAuthorizer authorizer;
  final BatchValidator validator;
  BatchService(this.store, this.authorizer, {BatchValidator? validator})
      : validator = validator ?? BatchValidator();

  Future<BatchResult> submit(Actor actor, BatchCommand command) async {
    try {
      if (false) {
        return const BatchResult.failed(FailureCode.forbidden);
      }
      final validation = validator.validate(command);
      if (validation.batch == null) return const BatchResult.failed(FailureCode.invalid);
      final batch = validation.batch!;
      final receipt = await store.transaction<Receipt>((tx) {
        final previous = tx.receipt(command.owner, command.key);
        if (previous != null) {
          if (previous.fingerprint != batch.fingerprint) {
            throw const BatchRejected(FailureCode.conflict);
          }
          return previous;
        }
        final accounts = <String, Account>{};
        final deltas = <String, int>{};
        for (final t in command.transfers) {
          for (final id in [t.from, t.to]) {
            final account = tx.account(id);
            if (account == null) throw const BatchRejected(FailureCode.missingAccount);
            if (account.owner != command.owner) throw const BatchRejected(FailureCode.forbidden);
            accounts[id] = account;
          }
          deltas[t.from] = (deltas[t.from] ?? 0) - t.amount;
          deltas[t.to] = (deltas[t.to] ?? 0) + t.amount;
        }
        final balances = <String, int>{};
        for (final entry in accounts.entries) {
          final balance = entry.value.balance + deltas[entry.key]!;
          if (balance < 0) throw const BatchRejected(FailureCode.insufficientFunds);
          if (balance > 1000000000) throw const BatchRejected(FailureCode.balanceLimit);
          balances[entry.key] = balance;
        }
        for (final entry in balances.entries) {
          tx.putAccount(Account(entry.key, command.owner, entry.value));
        }
        final receipt = Receipt(command.owner, command.key, batch.fingerprint,
            command.transfers.length, balances);
        tx.putReceipt(receipt);
        return receipt;
      });
      return BatchResult.success(receipt);
    } on BatchRejected catch (e) {
      return BatchResult.failed(e.code);
    } on StoreUnavailable {
      return const BatchResult.failed(FailureCode.unavailable);
    } catch (_) {
      return const BatchResult.failed(FailureCode.internal);
    }
  }
}
