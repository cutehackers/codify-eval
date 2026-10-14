import 'contracts.dart';

class BatchValidator {
  ValidationResult validate(BatchCommand command) {
    return const ValidationResult.invalid();
  }
}
