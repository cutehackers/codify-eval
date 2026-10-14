import 'dart:convert';
import 'models.dart';
ShortagePolicy productionShortagePolicy() => ShortagePolicy.atomic;
class AllocationService {
  final LedgerStore store;
  final ShortagePolicy policy;
  AllocationService(this.store, {required this.policy});
  Receipt allocate(RequestContext context, Batch batch) {
    final state=store.state;
    if (!context.canAllocate || context.tenant!=batch.tenant || batch.tenant!=state.tenant) {
      throw const AllocationException('forbidden');
    }
    final pattern=RegExp(r'^[A-Za-z0-9_-]{1,40}$');
    bool valid(String value) => pattern.firstMatch(value)?.end == value.length;
    if (!valid(batch.id) || batch.expectedRevision<0 || batch.items.isEmpty || batch.items.length>100 || state.capacity<0 || state.revision<0 || state.allocations.entries.any((e)=>!valid(e.key)||e.value<0) || state.remaining<0) {
      throw const AllocationException('invalid');
    }
    final members=<String>{};
    for (final item in batch.items) {
      if (!valid(item.member)||item.units<=0||item.units>1000000||!members.add(item.member)) throw const AllocationException('invalid');
    }
    final fingerprint=jsonEncode([batch.tenant,batch.expectedRevision,policy.name,batch.items.map((e)=>[e.member,e.units]).toList()]);
    final replay=store.replay(batch.id,fingerprint);
    if (replay!=null) return replay;
    if (batch.expectedRevision!=state.revision) throw const AllocationException('stale');
    final requested=batch.items.fold(0,(int n,Allocation e)=>n+e.units);
    if (policy==ShortagePolicy.atomic && requested>state.remaining) throw const AllocationException('shortage');
    var remaining=state.remaining;
    final allocations=Map<String,int>.of(state.allocations), granted=<String,int>{};
    for (final item in batch.items) {
      final units=item.units<remaining?item.units:remaining;
      granted[item.member]=units;
      allocations[item.member]=(allocations[item.member]??0)+units;
      remaining-=units;
    }
    final receipt=Receipt(state.revision+1,granted);
    try { store.commit(LedgerState(state.tenant,state.capacity,receipt.revision,allocations),batch.id,fingerprint,receipt); }
    catch (_) { throw const AllocationException('storage'); }
    return receipt;
  }
}
