import 'dart:convert';
import 'contracts.dart';
import 'checkpoint_codec.dart';

class EventProcessor {
  EventProcessor({required String tenantId, required AccessContext context,
      required CheckpointStore store, required IntegrityService integrity})
      : _tenantId = tenantId, _context = context, _store = store,
        _integrity = integrity, _codec = CheckpointCodec(integrity);

  final String _tenantId;
  final AccessContext _context;
  final CheckpointStore _store;
  final IntegrityService _integrity;
  final CheckpointCodec _codec;
  CheckpointState? _state;
  TenantView? _view;
  bool _busy = false;

  bool get _authorized => _matches(_tenantGrammar, _tenantId) &&
      _context.allowedTenants.contains(_tenantId);
  TenantView? get current => _authorized ? _view : null;
  ProcessorResult _failure(ProcessorCode code) => ProcessorResult(
      code: code, view: code == ProcessorCode.unauthorized ? null : _view);

  Future<ProcessorResult> restore() async {
    if (!_authorized) return _failure(ProcessorCode.unauthorized);
    if (_busy) return _failure(ProcessorCode.busy);
    _busy = true;
    try {
      final record = await _store.read(_tenantId);
      if (record.revision < 0 || record.revision > 2147483647) {
        return _failure(ProcessorCode.corruptCheckpoint);
      }
      if (record.revision == 0 && record.primary == null && record.recovery == null) {
        _publish(CheckpointState(tenantId: _tenantId, revision: 0,
            stock: const {}, replays: const {}));
        return ProcessorResult(code: ProcessorCode.ok, view: _view);
      }
      CheckpointState? decodeCopy(String? copy) {
        if (copy == null) return null;
        try {
          return _codec.decode(copy, expectedTenant: _tenantId,
              expectedRevision: record.revision);
        } on InvalidCheckpoint {
          return null;
        }
      }
      final primary = decodeCopy(record.primary);
      final recovery = decodeCopy(record.recovery);
      if ((primary == null && recovery == null) ||
          (primary != null && recovery != null && record.primary != record.recovery)) {
        return _failure(ProcessorCode.corruptCheckpoint);
      }
      _publish(primary ?? recovery!);
      return ProcessorResult(code: ProcessorCode.ok, view: _view,
          recovered: primary == null || recovery == null);
    } on StoreUnavailable {
      return _failure(ProcessorCode.storageUnavailable);
    } finally {
      _busy = false;
    }
  }

  Future<ProcessorResult> ingest(String batchJson) async {
    if (!_authorized) return _failure(ProcessorCode.unauthorized);
    if (_busy) return _failure(ProcessorCode.busy);
    _busy = true;
    try {
      final before = _state;
      if (before == null) return _failure(ProcessorCode.notInitialized);
      final events = _parse(batchJson);
      if (events == null) return _failure(ProcessorCode.invalidBatch);
      final stock = Map<String, int>.of(before.stock);
      final replays = Map<String, String>.of(before.replays);
      var accepted = 0;
      var replayed = 0;
      for (final event in events) {
        final fingerprint = _integrity.sha256Hex(utf8.encode(jsonEncode([
          event.id, event.sku, event.delta, event.occurredAt,
        ])));
        final previous = replays[event.id];
        if (previous != null) {
          if (previous != fingerprint) return _failure(ProcessorCode.replayConflict);
          replayed++;
          continue;
        }
        final nextStock = (stock[event.sku] ?? 0) + event.delta;
        if (nextStock < 0 || nextStock > 2147483647) {
          return _failure(ProcessorCode.stockOutOfRange);
        }
        if (replays.length >= 10000) return _failure(ProcessorCode.capacityExceeded);
        replays[event.id] = fingerprint;
        if (nextStock == 0) {
          stock.remove(event.sku);
        } else {
          stock[event.sku] = nextStock;
        }
        accepted++;
      }
      if (accepted == 0) {
        return ProcessorResult(code: ProcessorCode.ok, view: _view, replayed: replayed);
      }
      if (before.revision == 2147483647) return _failure(ProcessorCode.capacityExceeded);
      final staged = CheckpointState(tenantId: _tenantId,
          revision: before.revision + 1, stock: stock, replays: replays);
      final checkpoint = _codec.encode(staged);
      _publish(staged);
      final committed = await _store.compareAndSwap(_tenantId, before.revision,
          StoreRecord(revision: staged.revision, primary: checkpoint, recovery: checkpoint));
      if (!committed) return _failure(ProcessorCode.concurrentCommit);
      return ProcessorResult(code: ProcessorCode.ok, view: _view,
          accepted: accepted, replayed: replayed);
    } on StoreUnavailable {
      return _failure(ProcessorCode.storageUnavailable);
    } finally {
      _busy = false;
    }
  }

  void _publish(CheckpointState state) {
    _state = state;
    _view = TenantView(tenantId: state.tenantId, revision: state.revision,
        stock: state.stock, processedCount: state.replays.length);
  }

  static final _tenantGrammar = RegExp(r'[a-z][a-z0-9_-]{0,31}');
  static final _identityGrammar = RegExp(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}');
  static final _timestampGrammar = RegExp(
      r'(20[0-9]{2})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})\.([0-9]{3})Z');
  static bool _matches(RegExp grammar, String value) {
    final match = grammar.matchAsPrefix(value);
    return match != null && match.end == value.length;
  }

  static bool _validTimestamp(String value) {
    final match = _timestampGrammar.matchAsPrefix(value);
    if (match == null || match.end != value.length) return false;
    final year = int.parse(match[1]!);
    final month = int.parse(match[2]!);
    final day = int.parse(match[3]!);
    final hour = int.parse(match[4]!);
    final minute = int.parse(match[5]!);
    final second = int.parse(match[6]!);
    if (month < 1 || month > 12 || day < 1 || hour > 23 || minute > 59 || second > 59) {
      return false;
    }
    final leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    final days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    return day <= days[month - 1];
  }

  static List<_Event>? _parse(String input) {
    try {
      if (utf8.encode(input).length > 65536) return null;
      final root = jsonDecode(input);
      if (root is! Map || root.length != 1 || !root.containsKey('events')) return null;
      final list = root['events'];
      if (list is! List || list.isEmpty || list.length > 100) return null;
      final events = <_Event>[];
      for (final item in list) {
        if (item is! Map || item.length != 4 ||
            !const ['id', 'sku', 'delta', 'occurredAt'].every(item.containsKey)) return null;
        final id = item['id'];
        final sku = item['sku'];
        final delta = item['delta'];
        final at = item['occurredAt'];
        if (id is! String || sku is! String || delta is! int || at is! String ||
            !_matches(_identityGrammar, id) || !_matches(_identityGrammar, sku) ||
            delta == 0 || delta < -1000000 || delta > 1000000 || !_validTimestamp(at)) {
          return null;
        }
        events.add(_Event(id, sku, delta, at));
      }
      return events;
    } on FormatException {
      return null;
    }
  }
}

class _Event {
  _Event(this.id, this.sku, this.delta, this.occurredAt);
  final String id;
  final String sku;
  final int delta;
  final String occurredAt;
}
