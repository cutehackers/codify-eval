import 'dart:collection';

enum Permission { producer, worker }

enum JobState { pending, leased, completed, failed }

enum Code {
  ok,
  empty,
  unavailable,
  invalidInput,
  requestConflict,
  settlementConflict,
  busy,
  storageUnavailable
}

enum SettlementKind { complete, fail }

class Principal {
  final String tenantId, userId;
  final Set<Permission> permissions;
  Principal(this.tenantId, this.userId, Set<Permission> permissions)
      : permissions = Set.unmodifiable(permissions);
}

class Job {
  final String id, tenantId, payload;
  final DateTime createdAt, availableAt;
  final JobState state;
  final int attempts;
  final String? workerId, leaseId;
  final DateTime? expiresAt;
  const Job(
      {required this.id,
      required this.tenantId,
      required this.payload,
      required this.createdAt,
      required this.availableAt,
      this.state = JobState.pending,
      this.attempts = 0,
      this.workerId,
      this.leaseId,
      this.expiresAt});
}

class Submission {
  final String jobId, payload;
  const Submission(this.jobId, this.payload);
}

class Settlement {
  final String jobId, workerId;
  final SettlementKind kind;
  final int delaySeconds;
  const Settlement(this.jobId, this.workerId, this.kind, this.delaySeconds);
}

class Snapshot {
  final String tenantId;
  final int revision;
  final Map<String, Job> jobs;
  final Map<String, Submission> submissions;
  final Map<String, Settlement> settlements;
  final Set<String> usedLeaseIds;
  Snapshot(
      {required this.tenantId,
      required this.revision,
      Map<String, Job> jobs = const {},
      Map<String, Submission> submissions = const {},
      Map<String, Settlement> settlements = const {},
      Set<String> usedLeaseIds = const {}})
      : jobs = UnmodifiableMapView(Map.of(jobs)),
        submissions = UnmodifiableMapView(Map.of(submissions)),
        settlements = UnmodifiableMapView(Map.of(settlements)),
        usedLeaseIds = Set.unmodifiable(usedLeaseIds);
}

class Result {
  final Code code;
  final Job? job;
  const Result(this.code, [this.job]);
}

abstract class QueueStore {
  Future<Snapshot> read(String tenantId);
  // Atomic: succeeds only if current revision == expectedRevision, then replaces
  // the complete tenant snapshot. False means no write. Exceptions mean no write.
  Future<bool> compareAndSwap(
      String tenantId, int expectedRevision, Snapshot next);
}

abstract class Clock {
  DateTime now();
}

abstract class IdSource {
  String nextJobId();
  String nextLeaseId();
}

class QueueService {
  final QueueStore store;
  final Clock clock;
  final IdSource ids;
  QueueService(this.store, this.clock, this.ids);
  Future<Result> enqueue(Principal principal, String tenantId, String key,
          String payload) async =>
      const Result(Code.unavailable);
  Future<Result> claim(Principal principal, String tenantId) async =>
      const Result(Code.unavailable);
  Future<Result> complete(Principal principal, String tenantId, String jobId,
          String leaseId) async =>
      const Result(Code.unavailable);
  Future<Result> fail(Principal principal, String tenantId, String jobId,
          String leaseId, int delaySeconds) async =>
      const Result(Code.unavailable);
}
