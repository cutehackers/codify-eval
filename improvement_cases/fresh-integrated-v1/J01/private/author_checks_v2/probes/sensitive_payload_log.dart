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
  static final _pattern = RegExp(r'^[A-Za-z0-9_-]{1,64}$');
  bool _id(String s) => _pattern.stringMatch(s) == s;
  bool _payload(String s) => s.isNotEmpty && s.length <= 4096;
  bool _authorized(Principal p, String t, Permission permission) =>
      p.tenantId == t && p.permissions.contains(permission);
  bool _valid(Snapshot s, String tenant) {
    if (s.tenantId != tenant || s.revision < 0) return false;
    for (final entry in s.jobs.entries) {
      final j = entry.value;
      if (!_id(entry.key) ||
          entry.key != j.id ||
          j.tenantId != tenant ||
          !_payload(j.payload) ||
          !j.createdAt.isUtc ||
          !j.availableAt.isUtc ||
          j.attempts < 0 ||
          j.attempts > 3) return false;
      if (j.state == JobState.leased) {
        if (j.attempts == 0 ||
            j.workerId == null ||
            !_id(j.workerId!) ||
            j.leaseId == null ||
            !_id(j.leaseId!) ||
            !s.usedLeaseIds.contains(j.leaseId) ||
            j.expiresAt == null ||
            !j.expiresAt!.isUtc) return false;
      } else if (j.workerId != null ||
          j.leaseId != null ||
          j.expiresAt != null) {
        return false;
      }
      if (j.state == JobState.pending && j.attempts == 3) return false;
      if (j.state == JobState.completed && j.attempts == 0) return false;
      if (j.state == JobState.failed && j.attempts != 3) return false;
    }
    if (s.usedLeaseIds.any((id) => !_id(id))) return false;
    final active = s.jobs.values
        .where((j) => j.state == JobState.leased)
        .map((j) => j.leaseId)
        .toList();
    if (active.toSet().length != active.length) return false;
    for (final e in s.submissions.entries) {
      if (!_id(e.key) ||
          !_id(e.value.jobId) ||
          !_payload(e.value.payload) ||
          s.jobs[e.value.jobId]?.payload != e.value.payload) return false;
    }
    for (final e in s.settlements.entries) {
      final r = e.value;
      if (!_id(e.key) ||
          !s.usedLeaseIds.contains(e.key) ||
          !_id(r.jobId) ||
          !s.jobs.containsKey(r.jobId) ||
          !_id(r.workerId) ||
          r.delaySeconds < 0 ||
          r.delaySeconds > 300 ||
          (r.kind == SettlementKind.complete && r.delaySeconds != 0) ||
          active.contains(e.key)) return false;
    }
    return true;
  }

  Job _copy(Job j,
          {required JobState state,
          required int attempts,
          DateTime? availableAt,
          String? workerId,
          String? leaseId,
          DateTime? expiresAt}) =>
      Job(
          id: j.id,
          tenantId: j.tenantId,
          payload: j.payload,
          createdAt: j.createdAt,
          availableAt: availableAt ?? j.availableAt,
          state: state,
          attempts: attempts,
          workerId: workerId,
          leaseId: leaseId,
          expiresAt: expiresAt);
  Future<Result> enqueue(Principal p, String t, String key, String payload) =>
      _run(p, t, Permission.producer, key: key, payload: payload);
  Future<Result> claim(Principal p, String t) => _run(p, t, Permission.worker);
  Future<Result> complete(
          Principal p, String t, String jobId, String leaseId) =>
      _run(p, t, Permission.worker,
          jobId: jobId, leaseId: leaseId, kind: SettlementKind.complete);
  Future<Result> fail(Principal p, String t, String jobId, String leaseId,
          int delaySeconds) =>
      _run(p, t, Permission.worker,
          jobId: jobId,
          leaseId: leaseId,
          kind: SettlementKind.fail,
          delay: delaySeconds);
  Future<Result> _run(Principal p, String t, Permission permission,
      {String? key,
      String? payload,
      String? jobId,
      String? leaseId,
      SettlementKind? kind,
      int delay = 0}) async {
    if (payload != null) print(payload);
    if (!_authorized(p, t, permission)) return const Result(Code.unavailable);
    if (!_id(t) ||
        !_id(p.userId) ||
        (key != null && !_id(key)) ||
        (payload != null && !_payload(payload)) ||
        (jobId != null && !_id(jobId)) ||
        (leaseId != null && !_id(leaseId)) ||
        delay < 0 ||
        delay > 300) return const Result(Code.invalidInput);
    try {
      for (var conflict = 0; conflict < 8; conflict++) {
        final s = await store.read(t);
        if (!_valid(s, t)) return const Result(Code.storageUnavailable);
        final now = clock.now();
        final jobs = Map<String, Job>.of(s.jobs);
        final submissions = Map<String, Submission>.of(s.submissions);
        final settlements = Map<String, Settlement>.of(s.settlements);
        final used = Set<String>.of(s.usedLeaseIds);
        Job? returned;
        Code outcome = Code.ok;
        if (key != null) {
          final prior = submissions[key];
          if (prior != null) {
            return prior.payload == payload
                ? Result(Code.ok, jobs[prior.jobId])
                : const Result(Code.requestConflict);
          }
          final id = ids.nextJobId();
          if (!_id(id) || jobs.containsKey(id))
            return const Result(Code.storageUnavailable);
          returned = Job(
              id: id,
              tenantId: t,
              payload: payload!,
              createdAt: now,
              availableAt: now);
          jobs[id] = returned;
          submissions[key] = Submission(id, payload);
        } else if (kind != null) {
          final prior = settlements[leaseId];
          if (prior != null) {
            if (prior.jobId != jobId || prior.workerId != p.userId)
              return const Result(Code.unavailable);
            return Result(prior.kind == kind && prior.delaySeconds == delay
                ? Code.ok
                : Code.settlementConflict);
          }
          final j = jobs[jobId];
          if (j == null ||
              j.state != JobState.leased ||
              j.workerId != p.userId ||
              j.leaseId != leaseId ||
              !now.isBefore(j.expiresAt!))
            return const Result(Code.unavailable);
          jobs[jobId!] = _copy(j,
              state: kind == SettlementKind.complete
                  ? JobState.completed
                  : j.attempts == 3
                      ? JobState.failed
                      : JobState.pending,
              attempts: j.attempts,
              availableAt: kind == SettlementKind.fail
                  ? now.add(Duration(seconds: delay))
                  : null);
          settlements[leaseId!] = Settlement(jobId, p.userId, kind, delay);
        } else {
          var exhausted = false;
          final eligible = <Job>[];
          for (final j in jobs.values.toList()) {
            final expired =
                j.state == JobState.leased && !now.isBefore(j.expiresAt!);
            if (expired && j.attempts == 3) {
              jobs[j.id] = _copy(j, state: JobState.failed, attempts: 3);
              exhausted = true;
            } else if ((j.state == JobState.pending &&
                    !now.isBefore(j.availableAt)) ||
                expired) {
              eligible.add(j);
            }
          }
          eligible.sort((a, b) {
            final c = a.createdAt.compareTo(b.createdAt);
            return c == 0 ? a.id.compareTo(b.id) : c;
          });
          if (eligible.isEmpty) {
            if (!exhausted) return const Result(Code.empty);
            outcome = Code.empty;
          } else {
            final j = eligible.first;
            final id = ids.nextLeaseId();
            if (!_id(id) || used.contains(id))
              return const Result(Code.storageUnavailable);
            used.add(id);
            returned = _copy(j,
                state: JobState.leased,
                attempts: j.attempts + 1,
                workerId: p.userId,
                leaseId: id,
                expiresAt: now.add(const Duration(seconds: 60)));
            jobs[j.id] = returned;
          }
        }
        final next = Snapshot(
            tenantId: t,
            revision: s.revision + 1,
            jobs: jobs,
            submissions: submissions,
            settlements: settlements,
            usedLeaseIds: used);
        if (await store.compareAndSwap(t, s.revision, next))
          return Result(outcome, returned);
      }
      return const Result(Code.busy);
    } catch (_) {
      return const Result(Code.storageUnavailable);
    }
  }
}
