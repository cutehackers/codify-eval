enum ProcessorCode {
  ok,
  unauthorized,
  busy,
  notInitialized,
  invalidBatch,
  replayConflict,
  stockOutOfRange,
  capacityExceeded,
  concurrentCommit,
  storageUnavailable,
  corruptCheckpoint,
}

class AccessContext {
  AccessContext({required Set<String> allowedTenants})
    : allowedTenants = Set.unmodifiable(allowedTenants);
  final Set<String> allowedTenants;
}

class TenantView {
  TenantView({
    required String tenantId,
    required int revision,
    required Map<String, int> stock,
    required this.processedCount,
  }) : tenantId = tenantId,
       revision = revision,
       stock = Map.unmodifiable(stock);
  final String tenantId;
  final int revision;
  final Map<String, int> stock;
  final int processedCount;
}

class ProcessorResult {
  ProcessorResult({
    required this.code,
    this.view,
    this.accepted = 0,
    this.replayed = 0,
    this.recovered = false,
  });
  final ProcessorCode code;
  final TenantView? view;
  final int accepted;
  final int replayed;
  final bool recovered;
}

class StoreRecord {
  StoreRecord({required this.revision, this.primary, this.recovery});
  final int revision;
  final String? primary;
  final String? recovery;
}

abstract interface class CheckpointStore {
  Future<StoreRecord> read(String tenantId);
  Future<bool> compareAndSwap(
    String tenantId,
    int expectedRevision,
    StoreRecord replacement,
  );
}

class StoreUnavailable implements Exception {}

abstract interface class IntegrityService {
  String sha256Hex(List<int> bytes);
  String signCheckpoint(List<int> payload);
  bool verifyCheckpoint(List<int> payload, String tag);
}

class CheckpointState {
  CheckpointState({
    required String tenantId,
    required int revision,
    required Map<String, int> stock,
    required Map<String, String> replays,
  }) : tenantId = tenantId,
       revision = revision,
       stock = Map.unmodifiable(stock),
       replays = Map.unmodifiable(replays);
  final String tenantId;
  final int revision;
  final Map<String, int> stock;
  final Map<String, String> replays;
}

class InvalidCheckpoint implements Exception {}
