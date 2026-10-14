import 'models.dart';
ShortagePolicy productionShortagePolicy() => throw UnimplementedError('Resolve the product decision');
class AllocationService {
  final LedgerStore store;
  final ShortagePolicy policy;
  AllocationService(this.store, {required this.policy});
  Receipt allocate(RequestContext context, Batch batch) {
    throw UnimplementedError('Implement the public contract');
  }
}
