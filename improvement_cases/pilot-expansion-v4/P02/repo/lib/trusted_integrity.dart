import 'dart:convert';
import 'package:crypto/crypto.dart' as crypto;
import 'contracts.dart';

/// Fixture-only key. Production key management is outside this task.
class TrustedIntegrity implements IntegrityService {
  TrustedIntegrity()
    : _key = utf8.encode('P02 deterministic offline fixture key v1');
  final List<int> _key;
  @override
  String sha256Hex(List<int> bytes) => crypto.sha256.convert(bytes).toString();
  @override
  String signCheckpoint(List<int> payload) =>
      crypto.Hmac(crypto.sha256, _key).convert(payload).toString();
  @override
  bool verifyCheckpoint(List<int> payload, String tag) {
    final expected = signCheckpoint(payload);
    var difference = tag.length ^ expected.length;
    for (var i = 0; i < expected.length; i++) {
      difference |=
          expected.codeUnitAt(i) ^ (i < tag.length ? tag.codeUnitAt(i) : 0);
    }
    return difference == 0;
  }
}
