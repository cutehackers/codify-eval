import 'dart:convert';
import 'contracts.dart';

class DocumentRepository {
  final DocumentFiles files;
  final AccessPolicy policy;
  DocumentRepository(this.files, this.policy);
  Future<void> _tail = Future<void>.value();
  static final _slug = RegExp(r'^[a-z][a-z0-9_-]{0,31}$');
  void _validate(String owner, String id) {
    if (_slug.firstMatch(owner)?.end != owner.length ||
        _slug.firstMatch(id)?.end != id.length) {
      throw ArgumentError('Invalid document identifier');
    }
  }

  Future<T> _ordered<T>(Future<T> Function() action) {
    final result = _tail.then((_) => action());
    _tail = result.then<void>((_) {}, onError: (Object _, StackTrace __) {});
    return result;
  }

  Future<void> save(String owner, String id, String body) async {
    _validate(owner, id);

    await _ordered(() async {
      try {
        await files.write(
            '$owner.$id.json',
            jsonEncode({
              'version': 1,
              'owner': owner,
              'id': id,
              'body': body,
            }));
      } catch (_) {
        throw StorageFailure();
      }
    });
  }

  Future<String?> load(String owner, String id) async {
    _validate(owner, id);

    return _ordered(() async {
      try {
        final raw = await files.read('$owner.$id.json');
        if (raw == null) return null;
        final value = jsonDecode(raw);
        if (value is! Map<String, dynamic> ||
            value.length != 4 ||
            value['version'] is! int ||
            value['version'] != 1 ||
            value['owner'] != owner ||
            value['id'] != id ||
            value['body'] is! String) {
          throw const FormatException('Invalid document');
        }
        return value['body'] as String;
      } catch (_) {
        throw StorageFailure();
      }
    });
  }
}
