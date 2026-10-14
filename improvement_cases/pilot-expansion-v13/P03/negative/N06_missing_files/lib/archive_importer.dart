import 'contracts.dart';
import 'manifest_codec.dart';

class _Abort implements Exception {
  _Abort(this.code);
  final ImportCode code;
}

class ArchiveImporter {
  ArchiveImporter({required this.store, required this.integrity});
  final ImportStore store;
  final Integrity integrity;
  bool _busy = false;
  Future<ImportResult> import(String manifest, String tag,
      Stream<ArchiveEntry> entries, Cancellation cancellation) async {
    if (_busy) return const ImportResult(ImportCode.busy);
    _busy = true;
    String? stage;
    var published = false;
    void check() {
      if (cancellation.cancelled) throw _Abort(ImportCode.cancelled);
    }

    try {
      check();
      final plan = ManifestCodec(integrity).decode(manifest, tag);
      final expected = {for (final f in plan.files) f.path: f};
      check();
      stage = await store.begin();
      check();
      final seen = <String>{};
      var total = 0;
      await for (final entry in entries) {
        check();
        if (!ManifestCodec.validPath(entry.path) ||
            entry.kind != 'file' ||
            !expected.containsKey(entry.path) ||
            !seen.add(entry.path)) {
          throw _Abort(ImportCode.invalidEntry);
        }
        final spec = expected[entry.path]!;
        final data = <int>[];
        await for (final chunk in entry.chunks) {
          check();
          if (chunk.any((b) => b < 0 || b > 255))
            throw _Abort(ImportCode.invalidEntry);
          if (data.length + chunk.length > spec.size ||
              data.length + chunk.length > 65536 ||
              total + chunk.length > 262144) {
            throw _Abort(ImportCode.limitExceeded);
          }
          data.addAll(chunk);
          total += chunk.length;
          await store.write(stage, entry.path, List<int>.unmodifiable(chunk));
          check();
        }
        check();
        if (data.length != spec.size ||
            integrity.sha256Hex(data) != spec.digest) {
          throw _Abort(ImportCode.integrityMismatch);
        }
        // Empty files must exist in the stage too.
        if (data.isEmpty) {
          await store.write(stage, entry.path, const []);
          check();
        }
      }
      check();
      // Removed manifest completeness validation.
      await store.publish(stage);
      published = true;
      // A completed atomic publication is success even if cancellation changed during publish.
      return ImportResult(ImportCode.ok, files: seen.length, bytes: total);
    } on InvalidManifest {
      return const ImportResult(ImportCode.invalidManifest);
    } on _Abort catch (e) {
      return ImportResult(e.code);
    } on SourceUnavailable {
      return const ImportResult(ImportCode.sourceUnavailable);
    } on StorageUnavailable {
      return const ImportResult(ImportCode.storageUnavailable);
    } finally {
      if (stage != null && !published) await store.rollback(stage);
      _busy = false;
    }
  }
}
