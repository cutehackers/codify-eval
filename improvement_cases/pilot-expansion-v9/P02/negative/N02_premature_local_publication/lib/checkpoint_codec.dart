import 'dart:convert';
import 'contracts.dart';

class CheckpointCodec {
  CheckpointCodec(IntegrityService integrity) : _integrity = integrity;
  final IntegrityService _integrity;

  String encode(CheckpointState state) {
    try {
      _validate(state);
      final bytes = _payload(state);
      return jsonEncode({'payload': base64Encode(bytes),
        'tag': _integrity.signCheckpoint(bytes)});
    } catch (_) {
      throw InvalidCheckpoint();
    }
  }

  CheckpointState decode(String checkpoint,
      {required String expectedTenant, required int expectedRevision}) {
    try {
      final outer = jsonDecode(checkpoint);
      if (!_fields(outer, const ['payload', 'tag'])) throw InvalidCheckpoint();
      final encoded = outer['payload'];
      final tag = outer['tag'];
      if (encoded is! String || tag is! String || !_matches(_hex, tag)) {
        throw InvalidCheckpoint();
      }
      if (checkpoint != jsonEncode({'payload': encoded, 'tag': tag})) {
        throw InvalidCheckpoint();
      }
      final bytes = base64Decode(encoded);
      if (base64Encode(bytes) != encoded) throw InvalidCheckpoint();
      if (!_integrity.verifyCheckpoint(bytes, tag)) throw InvalidCheckpoint();
      final body = jsonDecode(utf8.decode(bytes, allowMalformed: false));
      if (!_fields(body, const ['schema', 'tenant', 'revision', 'stock', 'replays']) ||
          body['schema'] is! int || body['schema'] != 1 ||
          body['tenant'] is! String || body['revision'] is! int ||
          body['stock'] is! Map || body['replays'] is! Map) {
        throw InvalidCheckpoint();
      }
      final stock = <String, int>{};
      final replays = <String, String>{};
      for (final entry in (body['stock'] as Map).entries) {
        if (entry.key is! String || entry.value is! int) throw InvalidCheckpoint();
        stock[entry.key as String] = entry.value as int;
      }
      for (final entry in (body['replays'] as Map).entries) {
        if (entry.key is! String || entry.value is! String) throw InvalidCheckpoint();
        replays[entry.key as String] = entry.value as String;
      }
      final state = CheckpointState(tenantId: body['tenant'] as String,
          revision: body['revision'] as int, stock: stock, replays: replays);
      _validate(state);
      if (state.tenantId != expectedTenant || state.revision != expectedRevision) {
        throw InvalidCheckpoint();
      }
      final canonical = _payload(state);
      if (canonical.length != bytes.length) throw InvalidCheckpoint();
      for (var i = 0; i < bytes.length; i++) {
        if (canonical[i] != bytes[i]) throw InvalidCheckpoint();
      }
      return state;
    } catch (_) {
      throw InvalidCheckpoint();
    }
  }

  static final _tenant = RegExp(r'[a-z][a-z0-9_-]{0,31}');
  static final _identity = RegExp(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}');
  static final _hex = RegExp(r'[0-9a-f]{64}');
  static bool _matches(RegExp grammar, String value) {
    final match = grammar.matchAsPrefix(value);
    return match != null && match.end == value.length;
  }

  static bool _fields(dynamic value, List<String> names) =>
      value is Map && value.length == names.length &&
      names.every(value.containsKey);

  static void _validate(CheckpointState state) {
    if (!_matches(_tenant, state.tenantId) || state.revision < 0 ||
        state.revision > 2147483647 || state.replays.length > 10000) {
      throw InvalidCheckpoint();
    }
    for (final entry in state.stock.entries) {
      if (!_matches(_identity, entry.key) || entry.value < 1 ||
          entry.value > 2147483647) throw InvalidCheckpoint();
    }
    for (final entry in state.replays.entries) {
      if (!_matches(_identity, entry.key) || !_matches(_hex, entry.value)) {
        throw InvalidCheckpoint();
      }
    }
  }

  static List<int> _payload(CheckpointState state) {
    final skus = state.stock.keys.toList()..sort();
    final ids = state.replays.keys.toList()..sort();
    return utf8.encode(jsonEncode({
      'schema': 1,
      'tenant': state.tenantId,
      'revision': state.revision,
      'stock': {for (final key in skus) key: state.stock[key]!},
      'replays': {for (final key in ids) key: state.replays[key]!},
    }));
  }
}
