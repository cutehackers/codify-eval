import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/implementation.dart';

class TestClock implements Clock {
  DateTime value = DateTime.utc(2026, 1, 1);
  @override
  DateTime now() => value;
  void advance(int seconds) {
    value = value.add(Duration(seconds: seconds));
  }
}

class TestIds implements IdSource {
  int jobs = 0, leases = 0;
  String? forcedJob, forcedLease;
  @override
  String nextJobId() => forcedJob ?? 'job${++jobs}';
  @override
  String nextLeaseId() => forcedLease ?? 'lease${++leases}';
}

class MemoryStore implements QueueStore {
  Snapshot state = Snapshot(tenantId: 'tenant', revision: 0);
  int reads = 0, writes = 0, attempts = 0;
  bool throwRead = false, throwWrite = false, alwaysConflict = false;
  void Function(MemoryStore)? beforeCas;
  @override
  Future<Snapshot> read(String tenantId) async {
    reads++;
    if (throwRead) throw StateError('secret backend detail');
    return state;
  }

  @override
  Future<bool> compareAndSwap(
      String tenantId, int revision, Snapshot next) async {
    attempts++;
    final hook = beforeCas;
    beforeCas = null;
    hook?.call(this);
    if (throwWrite) throw StateError('secret backend detail');
    if (alwaysConflict || state.revision != revision) return false;
    expect(tenantId, 'tenant');
    expect(next.tenantId, tenantId);
    expect(next.revision, revision + 1);
    state = next;
    writes++;
    return true;
  }

  void external({Map<String, Job>? jobs}) {
    state = Snapshot(
        tenantId: state.tenantId,
        revision: state.revision + 1,
        jobs: jobs ?? state.jobs,
        submissions: state.submissions,
        settlements: state.settlements,
        usedLeaseIds: state.usedLeaseIds);
  }
}

class Fixture {
  final store = MemoryStore();
  final clock = TestClock();
  final ids = TestIds();
  late final service = QueueService(store, clock, ids);
  final producer = Principal('tenant', 'producer', {Permission.producer});
  final worker = Principal('tenant', 'worker', {Permission.worker});
  final other = Principal('tenant', 'other', {Permission.worker});
  Future<Job> enqueue(String key, [String payload = 'payload']) async {
    final r = await service.enqueue(producer, 'tenant', key, payload);
    expect(r.code, Code.ok);
    return r.job!;
  }

  Future<Job> claim() async {
    final r = await service.claim(worker, 'tenant');
    expect(r.code, Code.ok);
    return r.job!;
  }
}

void code(Result result, Code expected) {
  expect(result.code, expected);
  if (expected != Code.ok) expect(result.job, isNull);
}

void main() {
  test('public enqueue then claim', () async {
    final f = Fixture();
    final queued = await f.enqueue('submission');
    expect(queued.state, JobState.pending);
    final claimed = await f.claim();
    expect(claimed.id, queued.id);
    expect(claimed.payload, 'payload');
    expect(claimed.attempts, 1);
    expect(claimed.expiresAt, f.clock.now().add(const Duration(seconds: 60)));
  });
  test('public permission denial has no store access', () async {
    final f = Fixture();
    code(await f.service.claim(f.producer, 'tenant'), Code.unavailable);
    expect(f.store.reads, 0);
    expect(f.store.writes, 0);
  });
}
