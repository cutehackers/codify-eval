import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/implementation.dart';

class TestClock implements Clock {
  DateTime value = DateTime.utc(2026, 1, 1);
  bool throwNow = false;
  int calls = 0;
  @override
  DateTime now() {
    calls++;
    if (throwNow) throw StateError('secret clock');
    return value;
  }

  void advance(int seconds) {
    value = value.add(Duration(seconds: seconds));
  }
}

class TestIds implements IdSource {
  int jobs = 0, leases = 0;
  int jobCalls = 0, leaseCalls = 0;
  String? forcedJob, forcedLease;
  bool throwJob = false, throwLease = false;
  @override
  String nextJobId() {
    jobCalls++;
    if (throwJob) throw StateError('secret ID source');
    return forcedJob ?? 'job${++jobs}';
  }

  @override
  String nextLeaseId() {
    leaseCalls++;
    if (throwLease) throw StateError('secret ID source');
    return forcedLease ?? 'lease${++leases}';
  }
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

Future<void> noDependencies(
    Fixture f, Future<Result> Function() call, Code expected) async {
  code(await call(), expected);
  expect(f.store.reads, 0);
  expect(f.store.attempts, 0);
  expect(f.store.writes, 0);
  expect(f.clock.calls, 0);
  expect(f.ids.jobCalls, 0);
  expect(f.ids.leaseCalls, 0);
}

void main() {
  test('J01-T01 tenant and permission precede input validation', () async {
    final f = Fixture();
    final foreign = Principal(
        'foreign', 'worker', {Permission.producer, Permission.worker});
    await noDependencies(f, () => f.service.enqueue(foreign, 'tenant', '', ''),
        Code.unavailable);
    await noDependencies(
        f, () => f.service.claim(foreign, 'tenant'), Code.unavailable);
    await noDependencies(f, () => f.service.complete(foreign, 'tenant', '', ''),
        Code.unavailable);
    await noDependencies(f, () => f.service.fail(foreign, 'tenant', '', '', -1),
        Code.unavailable);
    await noDependencies(
        f,
        () => f.service.enqueue(f.worker, 'tenant', 'key', 'p'),
        Code.unavailable);
    await noDependencies(
        f, () => f.service.claim(f.producer, 'tenant'), Code.unavailable);
    await noDependencies(
        f,
        () => f.service.complete(f.producer, 'tenant', 'job', 'lease'),
        Code.unavailable);
    await noDependencies(
        f,
        () => f.service.fail(f.producer, 'tenant', 'job', 'lease', 0),
        Code.unavailable);
  });
  test('J01-T02 validation bounds and no I/O', () async {
    final f = Fixture();
    for (final bad in ['', 'a b', '한글', 'x' * 65, 'valid\n']) {
      await noDependencies(
          f,
          () => f.service.enqueue(f.producer, 'tenant', bad, 'p'),
          Code.invalidInput);
      await noDependencies(
          f,
          () => f.service.complete(f.worker, 'tenant', bad, 'lease'),
          Code.invalidInput);
      await noDependencies(
          f,
          () => f.service.complete(f.worker, 'tenant', 'job', bad),
          Code.invalidInput);
      await noDependencies(
          f,
          () => f.service.fail(f.worker, 'tenant', bad, 'lease', 0),
          Code.invalidInput);
      await noDependencies(
          f,
          () => f.service.fail(f.worker, 'tenant', 'job', bad, 0),
          Code.invalidInput);
      final badUser =
          Principal('tenant', bad, {Permission.producer, Permission.worker});
      final badTenant =
          Principal(bad, 'user', {Permission.producer, Permission.worker});
      for (final pair in [(badUser, 'tenant'), (badTenant, bad)]) {
        await noDependencies(
            f,
            () => f.service.enqueue(pair.$1, pair.$2, 'key', 'p'),
            Code.invalidInput);
        await noDependencies(
            f, () => f.service.claim(pair.$1, pair.$2), Code.invalidInput);
        await noDependencies(
            f,
            () => f.service.complete(pair.$1, pair.$2, 'job', 'lease'),
            Code.invalidInput);
        await noDependencies(
            f,
            () => f.service.fail(pair.$1, pair.$2, 'job', 'lease', 0),
            Code.invalidInput);
      }
    }
    for (final payload in ['', 'x' * 4097]) {
      await noDependencies(
          f,
          () => f.service.enqueue(f.producer, 'tenant', 'key', payload),
          Code.invalidInput);
    }
    for (final delay in [-1, 301]) {
      await noDependencies(
          f,
          () => f.service.fail(f.worker, 'tenant', 'job', 'lease', delay),
          Code.invalidInput);
    }
    final boundary = await f.enqueue('x' * 64, 'x' * 4096);
    expect(boundary.payload.length, 4096);
  });
  test('J01-T03 enqueue dedup and payload conflict', () async {
    final f = Fixture();
    final j = await f.enqueue('key', 'opaque');
    final replay =
        await f.service.enqueue(f.producer, 'tenant', 'key', 'opaque');
    expect(replay.job!.id, j.id);
    code(replay, Code.ok);
    code(await f.service.enqueue(f.producer, 'tenant', 'key', 'changed'),
        Code.requestConflict);
    expect(f.store.writes, 1);
    expect(f.ids.jobs, 1);
    final leased = await f.claim();
    final later =
        await f.service.enqueue(f.producer, 'tenant', 'key', 'opaque');
    expect(later.job!.leaseId, leased.leaseId);
  });
  test('J01-T04 concurrent enqueue one durable submission', () async {
    final f = Fixture();
    final r = await Future.wait(List.generate(
        2, (_) => f.service.enqueue(f.producer, 'tenant', 'key', 'p')));
    expect(r.every((x) => x.code == Code.ok), isTrue);
    expect(r[0].job!.id, r[1].job!.id);
    expect(f.store.state.jobs.length, 1);
    expect(f.store.state.submissions.length, 1);
  });
  test('J01-T05 deterministic order by creation then ID', () async {
    final f = Fixture();
    f.ids.forcedJob = 'z';
    await f.enqueue('first');
    f.ids.forcedJob = 'a';
    await f.enqueue('second');
    f.clock.advance(1);
    f.ids.forcedJob = '0';
    await f.enqueue('third');
    expect((await f.claim()).id, 'a');
    expect((await f.claim()).id, 'z');
    expect((await f.claim()).id, '0');
    code(await f.service.claim(f.worker, 'tenant'), Code.empty);
  });
  test('J01-T06 competing claims have one owner', () async {
    final f = Fixture();
    await f.enqueue('key');
    final results = await Future.wait([
      f.service.claim(f.worker, 'tenant'),
      f.service.claim(f.other, 'tenant')
    ]);
    expect(results.where((r) => r.code == Code.ok).length, 1);
    expect(results.where((r) => r.code == Code.empty).length, 1);
    expect(f.store.state.jobs.values.single.attempts, 1);
  });
  test('J01-T07 exact lease expiration and same worker fresh lease', () async {
    final f = Fixture();
    await f.enqueue('key');
    final first = await f.claim();
    f.clock.advance(59);
    code(await f.service.claim(f.worker, 'tenant'), Code.empty);
    f.clock.advance(1);
    code(await f.service.complete(f.worker, 'tenant', first.id, first.leaseId!),
        Code.unavailable);
    final second = await f.claim();
    expect(second.attempts, 2);
    expect(second.workerId, first.workerId);
    expect(second.leaseId, isNot(first.leaseId));
    code(await f.service.complete(f.worker, 'tenant', first.id, first.leaseId!),
        Code.unavailable);
    code(await f.service.fail(f.worker, 'tenant', first.id, first.leaseId!, 0),
        Code.unavailable);
    expect(f.store.state.jobs[first.id]!.leaseId, second.leaseId);
  });
  test('J01-T08 completion prevents further claims', () async {
    final f = Fixture();
    await f.enqueue('key');
    final j = await f.claim();
    final settled =
        await f.service.complete(f.worker, 'tenant', j.id, j.leaseId!);
    code(settled, Code.ok);
    expect(settled.job, isNull);
    expect(f.store.state.jobs[j.id]!.state, JobState.completed);
    expect(f.store.state.jobs[j.id]!.leaseId, isNull);
    code(await f.service.claim(f.worker, 'tenant'), Code.empty);
  });
  test('J01-T09 completion replay and cross operation conflict', () async {
    final f = Fixture();
    await f.enqueue('key');
    final j = await f.claim();
    code(await f.service.complete(f.worker, 'tenant', j.id, j.leaseId!),
        Code.ok);
    final writes = f.store.writes;
    f.clock.advance(100);
    code(await f.service.complete(f.worker, 'tenant', j.id, j.leaseId!),
        Code.ok);
    code(await f.service.fail(f.worker, 'tenant', j.id, j.leaseId!, 0),
        Code.settlementConflict);
    code(await f.service.complete(f.other, 'tenant', j.id, j.leaseId!),
        Code.unavailable);
    code(await f.service.complete(f.worker, 'tenant', 'otherJob', j.leaseId!),
        Code.unavailable);
    expect(f.store.writes, writes);
  });
  test('J01-T10 failure replay uses operation and delay', () async {
    final f = Fixture();
    await f.enqueue('key');
    final j = await f.claim();
    code(await f.service.fail(f.worker, 'tenant', j.id, j.leaseId!, 300),
        Code.ok);
    final writes = f.store.writes;
    code(await f.service.fail(f.worker, 'tenant', j.id, j.leaseId!, 300),
        Code.ok);
    code(await f.service.fail(f.worker, 'tenant', j.id, j.leaseId!, 299),
        Code.settlementConflict);
    code(await f.service.complete(f.worker, 'tenant', j.id, j.leaseId!),
        Code.settlementConflict);
    expect(f.store.writes, writes);
    f.clock.advance(299);
    code(await f.service.claim(f.worker, 'tenant'), Code.empty);
    f.clock.advance(1);
    final next = await f.claim();
    expect(next.attempts, 2);
    code(await f.service.fail(f.worker, 'tenant', next.id, next.leaseId!, 0),
        Code.ok);
    expect((await f.claim()).attempts, 3);
  });
  test('J01-T11 third failure terminal and replay durable', () async {
    final f = Fixture();
    await f.enqueue('key');
    for (var i = 1; i <= 3; i++) {
      final j = await f.claim();
      expect(j.attempts, i);
      code(await f.service.fail(f.worker, 'tenant', j.id, j.leaseId!, 0),
          Code.ok);
      code(await f.service.fail(f.worker, 'tenant', j.id, j.leaseId!, 0),
          Code.ok);
    }
    expect(f.store.state.jobs.values.single.state, JobState.failed);
    code(await f.service.claim(f.worker, 'tenant'), Code.empty);
  });
  test('J01-T12 third expiration skips and commits next atomically', () async {
    final f = Fixture();
    final old = await f.enqueue('old');
    await f.claim();
    f.clock.advance(60);
    await f.claim();
    f.clock.advance(60);
    await f.claim();
    await f.enqueue('next');
    f.clock.advance(60);
    final writes = f.store.writes;
    final next = await f.claim();
    expect(next.id, isNot(old.id));
    expect(next.attempts, 1);
    expect(f.store.state.jobs[old.id]!.state, JobState.failed);
    expect(f.store.writes, writes + 1);
  });
  test('J01-T13 exhausted only queue commits empty once', () async {
    final f = Fixture();
    await f.enqueue('key');
    await f.claim();
    f.clock.advance(60);
    await f.claim();
    f.clock.advance(60);
    await f.claim();
    f.clock.advance(60);
    final writes = f.store.writes;
    code(await f.service.claim(f.worker, 'tenant'), Code.empty);
    expect(f.store.writes, writes + 1);
    expect(f.store.state.jobs.values.single.state, JobState.failed);
    code(await f.service.claim(f.worker, 'tenant'), Code.empty);
    expect(f.store.writes, writes + 1);
  });
  test('J01-T14 conflict rechecks time before settling', () async {
    final f = Fixture();
    await f.enqueue('key');
    final j = await f.claim();
    final writes = f.store.writes;
    f.store.beforeCas = (s) {
      f.clock.advance(60);
      s.external();
    };
    code(await f.service.complete(f.worker, 'tenant', j.id, j.leaseId!),
        Code.unavailable);
    expect(f.store.writes, writes);
    expect(f.store.state.settlements, isEmpty);
  });
  test('J01-T15 conflict rechecks replaced ownership', () async {
    final f = Fixture();
    await f.enqueue('key');
    final j = await f.claim();
    f.store.beforeCas = (s) {
      final replaced = Job(
          id: j.id,
          tenantId: 'tenant',
          payload: j.payload,
          createdAt: j.createdAt,
          availableAt: j.availableAt,
          state: JobState.leased,
          attempts: 2,
          workerId: 'other',
          leaseId: 'externalLease',
          expiresAt: j.expiresAt);
      s.state = Snapshot(
          tenantId: 'tenant',
          revision: s.state.revision + 1,
          jobs: {j.id: replaced},
          submissions: s.state.submissions,
          usedLeaseIds: {...s.state.usedLeaseIds, 'externalLease'});
    };
    code(await f.service.fail(f.worker, 'tenant', j.id, j.leaseId!, 0),
        Code.unavailable);
    expect(f.store.state.jobs[j.id]!.workerId, 'other');
  });
  test('J01-T16 eight conflicts busy with no service mutation', () async {
    final f = Fixture();
    f.store.alwaysConflict = true;
    code(await f.service.enqueue(f.producer, 'tenant', 'key', 'p'), Code.busy);
    expect(f.store.attempts, 8);
    expect(f.store.reads, 8);
    expect(f.store.state.jobs, isEmpty);
    expect(f.store.writes, 0);
  });
  test('J01-T17 failed write leaves key reusable and errors opaque', () async {
    final f = Fixture();
    f.store.throwWrite = true;
    code(await f.service.enqueue(f.producer, 'tenant', 'key', 'secret payload'),
        Code.storageUnavailable);
    expect(f.store.state.jobs, isEmpty);
    expect(f.store.state.submissions, isEmpty);
    f.store.throwWrite = false;
    await f.enqueue('key', 'replacement');
    f.store.throwRead = true;
    code(await f.service.claim(f.worker, 'tenant'), Code.storageUnavailable);
  });
  test('J01-T18 malformed snapshots rejected before use', () async {
    final time = DateTime.utc(2026);
    Job job(
            {String id = 'job',
            String tenant = 'tenant',
            int attempts = 0,
            JobState state = JobState.pending,
            String? worker,
            String? lease,
            DateTime? expires,
            String payload = 'p',
            DateTime? created}) =>
        Job(
            id: id,
            tenantId: tenant,
            payload: payload,
            createdAt: created ?? time,
            availableAt: time,
            attempts: attempts,
            state: state,
            workerId: worker,
            leaseId: lease,
            expiresAt: expires);
    final malformed = <Snapshot>[
      Snapshot(tenantId: 'foreign', revision: 0),
      Snapshot(tenantId: 'tenant', revision: -1),
      Snapshot(tenantId: 'tenant', revision: 0, jobs: {'wrong': job()}),
      Snapshot(
          tenantId: 'tenant',
          revision: 0,
          jobs: {'job': job(tenant: 'foreign')}),
      Snapshot(
          tenantId: 'tenant', revision: 0, jobs: {'job': job(payload: '')}),
      Snapshot(
          tenantId: 'tenant', revision: 0, jobs: {'job': job(attempts: 4)}),
      Snapshot(
          tenantId: 'tenant', revision: 0, jobs: {'job': job(attempts: 3)}),
      Snapshot(
          tenantId: 'tenant',
          revision: 0,
          jobs: {'job': job(state: JobState.completed)}),
      Snapshot(
          tenantId: 'tenant',
          revision: 0,
          jobs: {'job': job(state: JobState.failed)}),
      Snapshot(
          tenantId: 'tenant', revision: 0, jobs: {'job': job(worker: 'w')}),
      Snapshot(
          tenantId: 'tenant',
          revision: 0,
          jobs: {'job': job(state: JobState.leased, attempts: 1)}),
      Snapshot(
          tenantId: 'tenant',
          revision: 0,
          submissions: {'key': const Submission('missing', 'p')}),
      Snapshot(tenantId: 'tenant', revision: 0, usedLeaseIds: {'bad id'}),
      Snapshot(tenantId: 'tenant', revision: 0, settlements: {
        'lease': const Settlement('missing', 'w', SettlementKind.complete, 0)
      }),
    ];
    final validLeased = job(
        state: JobState.leased,
        attempts: 1,
        worker: 'w',
        lease: 'lease',
        expires: time);
    malformed.addAll([
      Snapshot(
          tenantId: 'tenant',
          revision: 0,
          jobs: {'job': job(created: DateTime(2026))}),
      Snapshot(tenantId: 'tenant', revision: 0, jobs: {'job': validLeased}),
      Snapshot(tenantId: 'tenant', revision: 0, jobs: {
        'job': job(
            state: JobState.leased,
            attempts: 1,
            worker: 'bad worker',
            lease: 'lease',
            expires: time)
      }, usedLeaseIds: {
        'lease'
      }),
      Snapshot(tenantId: 'tenant', revision: 0, jobs: {
        'job': job(
            state: JobState.leased,
            attempts: 1,
            worker: 'w',
            lease: 'lease',
            expires: DateTime(2026))
      }, usedLeaseIds: {
        'lease'
      }),
      Snapshot(tenantId: 'tenant', revision: 0, jobs: {
        'job': validLeased,
        'second': job(
            id: 'second',
            state: JobState.leased,
            attempts: 1,
            worker: 'w',
            lease: 'lease',
            expires: time)
      }, usedLeaseIds: {
        'lease'
      }),
      Snapshot(
          tenantId: 'tenant',
          revision: 0,
          jobs: {'job': job()},
          submissions: {'bad key': const Submission('job', 'p')}),
      Snapshot(
          tenantId: 'tenant',
          revision: 0,
          jobs: {'job': job()},
          submissions: {'key': const Submission('job', 'different')}),
      for (final receipt in [
        const Settlement('job', 'bad worker', SettlementKind.fail, 0),
        const Settlement('job', 'w', SettlementKind.fail, -1),
        const Settlement('job', 'w', SettlementKind.fail, 301),
        const Settlement('job', 'w', SettlementKind.complete, 1),
      ])
        Snapshot(
            tenantId: 'tenant',
            revision: 0,
            jobs: {'job': job()},
            usedLeaseIds: {'lease'},
            settlements: {'lease': receipt}),
      Snapshot(tenantId: 'tenant', revision: 0, jobs: {
        'job': validLeased
      }, usedLeaseIds: {
        'lease'
      }, settlements: {
        'lease': const Settlement('job', 'w', SettlementKind.complete, 0)
      }),
    ]);
    for (final snapshot in malformed) {
      final f = Fixture();
      f.store.state = snapshot;
      code(await f.service.claim(f.worker, 'tenant'), Code.storageUnavailable);
      code(await f.service.enqueue(f.producer, 'tenant', 'key', 'p'),
          Code.storageUnavailable);
      code(await f.service.complete(f.worker, 'tenant', 'job', 'lease'),
          Code.storageUnavailable);
      expect(f.store.attempts, 0);
      expect(f.ids.jobs + f.ids.leases, 0);
    }
  });
  test('J01-T19 generated IDs malformed or reused fail closed', () async {
    final f = Fixture();
    f.ids.forcedJob = 'bad id';
    code(await f.service.enqueue(f.producer, 'tenant', 'key', 'p'),
        Code.storageUnavailable);
    f.ids.forcedJob = 'same';
    await f.enqueue('key');
    code(await f.service.enqueue(f.producer, 'tenant', 'another', 'p'),
        Code.storageUnavailable);
    f.ids.forcedLease = 'bad id';
    code(await f.service.claim(f.worker, 'tenant'), Code.storageUnavailable);
    f.ids.forcedLease = 'sameLease';
    final j = await f.claim();
    code(
        await f.service.fail(f.worker, 'tenant', j.id, j.leaseId!, 0), Code.ok);
    final writes = f.store.writes;
    code(await f.service.claim(f.worker, 'tenant'), Code.storageUnavailable);
    expect(f.store.writes, writes);
    expect(f.store.state.jobs[j.id]!.attempts, 1);
  });
  test('J01-T20 unknown wrong owner and failed lease unavailable', () async {
    final f = Fixture();
    await f.enqueue('key');
    final j = await f.claim();
    code(await f.service.complete(f.other, 'tenant', j.id, j.leaseId!),
        Code.unavailable);
    code(await f.service.complete(f.worker, 'tenant', 'missing', 'unknown'),
        Code.unavailable);
    code(await f.service.fail(f.worker, 'tenant', j.id, 'unknown', 0),
        Code.unavailable);
    expect(f.store.state.jobs[j.id]!.state, JobState.leased);
  });
  test('J01-T21 enqueue conflict uses fresh submission fingerprint', () async {
    final f = Fixture();
    f.store.beforeCas = (s) {
      final j = Job(
          id: 'externalJob',
          tenantId: 'tenant',
          payload: 'other',
          createdAt: f.clock.now(),
          availableAt: f.clock.now());
      s.state = Snapshot(
          tenantId: 'tenant',
          revision: s.state.revision + 1,
          jobs: {j.id: j},
          submissions: {'key': Submission(j.id, j.payload)});
    };
    code(await f.service.enqueue(f.producer, 'tenant', 'key', 'p'),
        Code.requestConflict);
    expect(f.store.state.jobs.keys, ['externalJob']);
    expect(f.store.writes, 0);
  });
  test('J01-T22 claim conflict chooses freshly eligible job', () async {
    final f = Fixture();
    f.ids.forcedJob = 'z';
    await f.enqueue('z');
    f.store.beforeCas = (s) {
      final j = Job(
          id: 'a',
          tenantId: 'tenant',
          payload: 'external',
          createdAt: f.clock.now(),
          availableAt: f.clock.now());
      s.external(jobs: {...s.state.jobs, 'a': j});
    };
    expect((await f.claim()).id, 'a');
    expect(f.store.state.jobs['z']!.state, JobState.pending);
  });
  test('J01-T23 historical failure replay cannot alter new lease', () async {
    final f = Fixture();
    await f.enqueue('key');
    final first = await f.claim();
    code(await f.service.fail(f.worker, 'tenant', first.id, first.leaseId!, 0),
        Code.ok);
    final next = await f.claim();
    final writes = f.store.writes;
    code(await f.service.fail(f.worker, 'tenant', first.id, first.leaseId!, 0),
        Code.ok);
    code(await f.service.complete(f.worker, 'tenant', first.id, first.leaseId!),
        Code.settlementConflict);
    expect(f.store.state.jobs[first.id]!.leaseId, next.leaseId);
    expect(f.store.writes, writes);
  });
  test('J01-T24 snapshot constructors detach caller collections', () {
    final jobs = <String, Job>{};
    final used = <String>{};
    final s = Snapshot(
        tenantId: 'tenant', revision: 0, jobs: jobs, usedLeaseIds: used);
    used.add('later');
    jobs['later'] = Job(
        id: 'later',
        tenantId: 'tenant',
        payload: 'p',
        createdAt: DateTime.utc(2026),
        availableAt: DateTime.utc(2026));
    expect(s.jobs, isEmpty);
    expect(s.usedLeaseIds, isEmpty);
    expect(() => s.usedLeaseIds.add('x'), throwsUnsupportedError);
    expect(() => s.jobs.clear(), throwsUnsupportedError);
  });
  test('J01-T25 preserve unrelated records and detached old snapshot',
      () async {
    final f = Fixture();
    final first = await f.enqueue('first', 'one');
    final second = await f.enqueue('second', 'two');
    final old = f.store.state;
    final lease = await f.claim();
    code(await f.service.fail(f.worker, 'tenant', lease.id, lease.leaseId!, 0),
        Code.ok);
    final again = await f.claim();
    expect(f.store.state.jobs[second.id]!.payload, 'two');
    expect(f.store.state.jobs[second.id]!.state, JobState.pending);
    expect(f.store.state.submissions.keys.toSet(), {'first', 'second'});
    expect(f.store.state.usedLeaseIds,
        containsAll([lease.leaseId, again.leaseId]));
    expect(f.store.state.settlements.keys, contains(lease.leaseId));
    expect(old.jobs[first.id]!.attempts, 0);
    expect(old.usedLeaseIds, isEmpty);
  });
  test('J01-T26 shared store separate services and tenant wide keys', () async {
    final f = Fixture();
    final second = QueueService(f.store, f.clock, f.ids);
    final otherProducer = Principal('tenant', 'another', {Permission.producer});
    final queued = await f.enqueue('key');
    final replay =
        await second.enqueue(otherProducer, 'tenant', 'key', 'payload');
    expect(replay.job!.id, queued.id);
    expect(f.store.writes, 1);
    final results = await Future.wait(
        [f.service.claim(f.worker, 'tenant'), second.claim(f.other, 'tenant')]);
    expect(results.where((r) => r.code == Code.ok).length, 1);
    expect(f.store.state.jobs[queued.id]!.attempts, 1);
  });
  test('J01-T27 dependency exceptions fixed and no writes', () async {
    final f = Fixture();
    f.clock.throwNow = true;
    code(await f.service.enqueue(f.producer, 'tenant', 'key', 'p'),
        Code.storageUnavailable);
    f.clock.throwNow = false;
    f.ids.throwJob = true;
    code(await f.service.enqueue(f.producer, 'tenant', 'key', 'p'),
        Code.storageUnavailable);
    expect(f.store.writes, 0);
    f.ids.throwJob = false;
    await f.enqueue('key');
    f.ids.throwLease = true;
    code(await f.service.claim(f.worker, 'tenant'), Code.storageUnavailable);
    expect(f.store.writes, 1);
    expect(f.store.state.jobs.values.single.attempts, 0);
  });
  test('J01-T28 concurrent complete versus fail one receipt and conflict',
      () async {
    final f = Fixture();
    await f.enqueue('key');
    final j = await f.claim();
    final results = await Future.wait([
      f.service.complete(f.worker, 'tenant', j.id, j.leaseId!),
      f.service.fail(f.worker, 'tenant', j.id, j.leaseId!, 0)
    ]);
    expect(
        results.map((r) => r.code).toSet(), {Code.ok, Code.settlementConflict});
    expect(f.store.state.settlements.length, 1);
    expect(f.store.writes, 3);
  });
  test('J01-T29 third attempt may complete before expiration', () async {
    final f = Fixture();
    await f.enqueue('key');
    await f.claim();
    f.clock.advance(60);
    await f.claim();
    f.clock.advance(60);
    final j = await f.claim();
    expect(j.attempts, 3);
    code(await f.service.complete(f.worker, 'tenant', j.id, j.leaseId!),
        Code.ok);
    expect(f.store.state.jobs[j.id]!.state, JobState.completed);
    code(await f.service.claim(f.worker, 'tenant'), Code.empty);
  });
  test('J01-T30 valid foreign principal cannot touch tenant data', () async {
    final f = Fixture();
    await f.enqueue('key');
    final lease = await f.claim();
    final foreign = Principal(
        'foreign', 'worker', {Permission.producer, Permission.worker});
    final reads = f.store.reads;
    final writes = f.store.writes;
    code(
        await f.service.enqueue(foreign, 'tenant', 'newKey', 'foreign payload'),
        Code.unavailable);
    code(await f.service.claim(foreign, 'tenant'), Code.unavailable);
    code(await f.service.complete(foreign, 'tenant', lease.id, lease.leaseId!),
        Code.unavailable);
    code(await f.service.fail(foreign, 'tenant', lease.id, lease.leaseId!, 0),
        Code.unavailable);
    expect(f.store.reads, reads);
    expect(f.store.writes, writes);
    expect(f.store.state.jobs[lease.id]!.state, JobState.leased);
  });
  test('J01-T31 service does not print payload or backend errors', () async {
    final f = Fixture();
    final messages = <String>[];
    await runZoned(() async {
      await f.enqueue('key', 'private payload marker');
      await f.claim();
      f.store.throwRead = true;
      code(await f.service.claim(f.worker, 'tenant'), Code.storageUnavailable);
      f.store.throwRead = false;
      f.store.throwWrite = true;
      code(
          await f.service
              .enqueue(f.producer, 'tenant', 'new', 'private payload marker'),
          Code.storageUnavailable);
    }, zoneSpecification:
        ZoneSpecification(print: (self, parent, zone, message) {
      messages.add(message);
    }));
    final sensitive = [
      'private payload marker',
      'secret backend detail',
      'secret clock',
      'secret ID source'
    ];
    expect(
        messages.where((message) => sensitive.any(message.contains)), isEmpty);
  });
}
