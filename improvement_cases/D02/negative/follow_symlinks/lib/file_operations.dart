import 'dart:io';

/// Public file-I/O seam. Implementations must preserve the dart:io meanings.
abstract class DocumentFileOperations {
  Future<FileSystemEntityType> type(String path, {required bool followLinks});
  Future<bool> exists(File file);
  Future<String> read(File file);
  Future<void> write(File file, String contents, {required bool flush});
  Future<void> rename(File file, String destination);
  Future<void> delete(File file);
}

class SystemDocumentFileOperations implements DocumentFileOperations {
  const SystemDocumentFileOperations();
  @override
  Future<FileSystemEntityType> type(String path, {required bool followLinks}) =>
      FileSystemEntity.type(path, followLinks: followLinks);
  @override
  Future<bool> exists(File file) => file.exists();
  @override
  Future<String> read(File file) => file.readAsString();
  @override
  Future<void> write(File file, String contents, {required bool flush}) async {
    await file.writeAsString(contents, flush: flush);
  }

  @override
  Future<void> rename(File file, String destination) async {
    await file.rename(destination);
  }

  @override
  Future<void> delete(File file) async {
    await file.delete();
  }
}
