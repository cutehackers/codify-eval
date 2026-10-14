import 'contracts.dart';

class ArchiveImporter {
  ArchiveImporter({required this.store, required this.integrity});
  final ImportStore store;
  final Integrity integrity;
  Future<ImportResult> import(String manifest, String tag,
          Stream<ArchiveEntry> entries, Cancellation cancellation) async =>
      const ImportResult(ImportCode.invalidManifest);
}
