enum ImportCode {
  ok,
  busy,
  cancelled,
  invalidManifest,
  invalidEntry,
  limitExceeded,
  integrityMismatch,
  sourceUnavailable,
  storageUnavailable
}

class ImportResult {
  const ImportResult(this.code, {this.files = 0, this.bytes = 0});
  final ImportCode code;
  final int files;
  final int bytes;
}

class Cancellation {
  bool cancelled = false;
}

class ArchiveEntry {
  ArchiveEntry(this.path, this.kind, this.chunks);
  final String path;
  final String kind;
  final Stream<List<int>> chunks;
}

class ManifestFile {
  const ManifestFile(this.path, this.size, this.digest);
  final String path;
  final int size;
  final String digest;
}

class Manifest {
  Manifest(List<ManifestFile> files) : files = List.unmodifiable(files);
  final List<ManifestFile> files;
}

class InvalidManifest implements Exception {}

class SourceUnavailable implements Exception {}

class StorageUnavailable implements Exception {}

abstract interface class Integrity {
  bool verifyManifest(String text, String tag);
  String sha256Hex(List<int> bytes);
}

abstract interface class ImportStore {
  Future<String> begin();
  Future<void> write(String stage, String path, List<int> chunk);
  Future<void> publish(String stage);
  Future<void> rollback(String stage);
}
