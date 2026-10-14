import 'dart:convert';
import 'contracts.dart';

class BatchValidator {
  ValidationResult validate(BatchCommand command) {
    bool identifier(String value) => value.isNotEmpty && value.trim() == value && !value.contains('\u0000');
    if (!identifier(command.owner) || !identifier(command.key) ||
        command.transfers.isEmpty || command.transfers.length > 20) {
      return const ValidationResult.invalid();
    }
    final ids = <String>{};
    for (final transfer in command.transfers) {
      if (!identifier(transfer.id) || !identifier(transfer.from) ||
          !identifier(transfer.to) || transfer.from == transfer.to ||
          transfer.amount <= 0 || transfer.amount > 1000000000 || !ids.add(transfer.id)) {
        return const ValidationResult.invalid();
      }
    }
    final ordered = List<Transfer>.of(command.transfers)..sort((a, b) => a.id.compareTo(b.id));
    final fingerprint = jsonEncode([command.owner,
      for (final t in ordered) [t.id, t.from, t.to, t.amount]]);
    return ValidationResult.valid(ValidatedBatch(command, fingerprint));
  }
}
