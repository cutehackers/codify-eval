import 'dart:io';
import 'contracts.dart';
import 'file_operations.dart';

class LocalDocumentFiles implements DocumentFiles {
  final Directory root;
  final DocumentFileOperations operations;
  LocalDocumentFiles(this.root, {DocumentFileOperations? operations})
      : operations = operations ?? const SystemDocumentFileOperations();
  File _file(String key) => File('${root.path}/$key');
  @override
  Future<String?> read(String key) async {
    final file = _file(key);
    return await operations.exists(file) ? await operations.read(file) : null;
  }

  @override
  Future<void> write(String key, String contents) =>
      operations.write(_file(key), contents, flush: false);
}
