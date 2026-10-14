class Job {
  final String id, tenant, asset, note;
  final int revision, attempts;
  final String state;
  const Job(this.id, this.tenant, this.asset, this.note,
      {this.revision = 1, this.attempts = 0, this.state = 'pending'});
  Job copy({int? attempts, String? state}) => Job(id, tenant, asset, note,
      revision: revision, attempts: attempts ?? this.attempts,
      state: state ?? this.state);
}
abstract class OutboxStore {
  Future<List<Job>> read();
  // Atomic replacement. If this throws, the old snapshot remains intact.
  Future<void> replace(List<Job> jobs);
}
class SendResult {
  final bool retryable;
  final String code;
  const SendResult(this.code, {this.retryable = false});
}
abstract class RepairApi {
  Future<SendResult> send(Job job, String idempotencyKey);
}
class SyncSummary {
  final int sent, retried, rejected;
  final bool storageUnavailable;
  const SyncSummary(this.sent, this.retried, this.rejected,
      {this.storageUnavailable = false});
}
