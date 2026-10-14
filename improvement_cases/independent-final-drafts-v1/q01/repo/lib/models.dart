enum ShortagePolicy { atomic, partial }
class RequestContext {
  final String tenant, actor;
  final bool canAllocate;
  const RequestContext(this.tenant, this.actor, {this.canAllocate = true});
}
class Allocation {
  final String member;
  final int units;
  const Allocation(this.member, this.units);
}
class Batch {
  final String id, tenant;
  final int expectedRevision;
  final List<Allocation> items;
  Batch(this.id, this.tenant, this.expectedRevision, List<Allocation> items)
      : items = List.unmodifiable(items);
}
class LedgerState {
  final String tenant;
  final int capacity, revision;
  final Map<String, int> allocations;
  LedgerState(this.tenant, this.capacity, this.revision, Map<String,int> allocations)
      : allocations = Map.unmodifiable(allocations);
  int get remaining => capacity - allocations.values.fold(0, (a,b) => a+b);
}
class Receipt {
  final int revision;
  final Map<String,int> granted;
  Receipt(this.revision, Map<String,int> granted) : granted = Map.unmodifiable(granted);
}
class AllocationException implements Exception {
  final String code;
  const AllocationException(this.code);
  @override String toString() => 'AllocationException($code)';
}
abstract class LedgerStore {
  LedgerState get state;
  // Must atomically persist state and replay record or throw before either changes.
  Receipt? replay(String id, String fingerprint);
  void commit(LedgerState state, String id, String fingerprint, Receipt receipt);
}
class MemoryLedgerStore implements LedgerStore {
  LedgerState _state;
  final Map<String, (String, Receipt)> _replays = {};
  bool failNextCommit = false;
  MemoryLedgerStore(this._state);
  @override LedgerState get state => _state;
  @override Receipt? replay(String id, String fingerprint) {
    final record = _replays[id];
    if (record == null) return null;
    if (record.$1 != fingerprint) throw const AllocationException('id_conflict');
    return record.$2;
  }
  @override void commit(LedgerState state, String id, String fingerprint, Receipt receipt) {
    if (failNextCommit) { failNextCommit = false; throw StateError('internal-storage-secret'); }
    _state = state;
    _replays[id] = (fingerprint, receipt);
  }
}
