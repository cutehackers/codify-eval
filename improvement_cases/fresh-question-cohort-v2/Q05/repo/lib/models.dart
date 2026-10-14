class Row {
  final String skuId;
  final int quantity;
  const Row(this.skuId, this.quantity);
}
class Shortage {
  final String skuId;
  final int requested;
  final int available;
  const Shortage(this.skuId, this.requested, this.available);
}
class Outcome {
  final String code;
  final List<Row> reserved;
  final List<Shortage> shortages;
  const Outcome(this.code, {this.reserved = const [], this.shortages = const []});
}
class Request {
  final String warehouseId;
  final String orderId;
  final List<Row> rows;
  const Request(this.warehouseId, this.orderId, this.rows);
}
class Identity {
  final String tenantId;
  final String operatorId;
  const Identity(this.tenantId, this.operatorId);
}
class Recorded {
  final String signature;
  final Outcome outcome;
  const Recorded(this.signature, this.outcome);
}
class Warehouse {
  final String tenantId;
  Map<String, int> stock;
  Map<String, Recorded> orders;
  Warehouse(this.tenantId, Map<String, int> stock)
      : stock = Map.of(stock), orders = {};
}
class MemoryStore {
  final Map<String, Warehouse> warehouses;
  bool failCommit = false;
  int commits = 0;
  int stockReads = 0;
  MemoryStore(this.warehouses);
  bool accessible(String id, String tenant) => warehouses[id]?.tenantId == tenant;
  Map<String, int> snapshot(String id) {
    stockReads++;
    return Map.of(warehouses[id]!.stock);
  }
  Recorded? recorded(String id, String order) => warehouses[id]!.orders[order];
  void commit(String id, String order, Recorded record, Map<String, int> next) {
    if (failCommit) throw StateError('SECRET storage disk detail');
    warehouses[id]!.stock = Map.of(next);
    warehouses[id]!.orders = {...warehouses[id]!.orders, order: record};
    commits++;
  }
}
