import 'contracts.dart';
import 'batch_validator.dart';

class BatchService {
  final AtomicBatchStore store;
  final BatchAuthorizer authorizer;
  final BatchValidator validator;
  BatchService(this.store, this.authorizer, {BatchValidator? validator})
      : validator = validator ?? BatchValidator();

  Future<BatchResult> submit(Actor actor, BatchCommand command) async {
    return const BatchResult.failed(FailureCode.unavailable);
  }
}
