abstract class DocumentFiles {
  Future<String?> read(String key);
  Future<void> write(String key, String contents);
}

abstract class AccessPolicy {
  bool canRead(String owner);
  bool canWrite(String owner);
}

class AccessDenied implements Exception {
  @override
  String toString() => 'Access denied';
}

class StorageFailure implements Exception {
  @override
  String toString() => 'Storage operation failed';
}
