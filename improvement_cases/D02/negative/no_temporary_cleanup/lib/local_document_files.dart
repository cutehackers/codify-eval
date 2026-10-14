import 'dart:io';
import 'contracts.dart';
import 'file_operations.dart';

class LocalDocumentFiles implements DocumentFiles {
  final Directory root;
  final DocumentFileOperations operations;
  LocalDocumentFiles(this.root, {DocumentFileOperations? operations})
      : operations = operations ?? const SystemDocumentFileOperations();
  int _counter = 0;
  static final _key =
      RegExp(r'^[a-z][a-z0-9_-]{0,31}\.[a-z][a-z0-9_-]{0,31}\.json$');
  File _file(String key) {
    if (_key.firstMatch(key)?.end != key.length)
      throw ArgumentError('Invalid storage key');
    return File('${root.path}${Platform.pathSeparator}$key');
  }

  Future<void> _check(File file) async {
    final type = await operations.type(file.path, followLinks: false);
    if (type != FileSystemEntityType.notFound &&
        type != FileSystemEntityType.file) {
      throw StorageFailure();
    }
  }

  @override
  Future<String?> read(String key) async {
    final file = _file(key);
    try {
      await _check(file);
      if (!await operations.exists(file)) return null;
      return await operations.read(file);
    } catch (_) {
      throw StorageFailure();
    }
  }

  @override
  Future<void> write(String key, String contents) async {
    final file = _file(key);
    File? temporary;
    try {
      await _check(file);
      temporary = File(
          '${file.path}.tmp-${DateTime.now().microsecondsSinceEpoch}-${_counter++}');
      await operations.write(temporary, contents, flush: true);
      await operations.rename(temporary, file.path);
    } catch (_) {
      throw StorageFailure();
    } finally {
      try {
        if (temporary != null && await operations.exists(temporary)) {
          /* Defect: do not clean up an existing temporary file. */
        }
      } catch (_) {
        /* Cleanup failures must not reveal paths or replace the operation result. */
      }
    }
  }
}
