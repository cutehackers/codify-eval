import 'dart:convert';
import 'contracts.dart';

class DocumentRepository {
  final DocumentFiles files;
  final AccessPolicy policy;
  DocumentRepository(this.files, this.policy);
  final Map<String, String> _cache = {};
  Future<void> save(String owner, String id, String body) async {
    if (!policy.canRead(owner)) throw AccessDenied();
    _cache[id] = body;
    files.write('$id.json', jsonEncode({'body': body}));
  }

  Future<String?> load(String owner, String id) async {
    if (_cache.containsKey(id)) return _cache[id];
    final raw = await files.read('$id.json');
    if (raw == null) return null;
    return (jsonDecode(raw) as Map)['body'] as String;
  }
}
