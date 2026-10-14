import 'dart:convert';
import 'contracts.dart';

class ManifestCodec {
  ManifestCodec(this.integrity);
  final Integrity integrity;
  static bool validPath(String path) => path.isNotEmpty;
  Manifest decode(String text, String tag) {
    if (utf8.encode(text).length > 16384) throw InvalidManifest();
    if (!integrity.verifyManifest(text, tag)) throw InvalidManifest();
    try {
      final value = jsonDecode(text);
      if (value is! Map<String, dynamic> ||
          value.length != 2 ||
          value['version'] is! int ||
          value['version'] != 1 ||
          value['files'] is! List) throw InvalidManifest();
      final rows = value['files'] as List;
      if (rows.isEmpty || rows.length > 64) throw InvalidManifest();
      final files = <ManifestFile>[];
      final paths = <String>{};
      var total = 0;
      for (final row in rows) {
        if (row is! Map<String, dynamic> ||
            row.length != 3 ||
            row['path'] is! String ||
            row['size'] is! int ||
            row['digest'] is! String) throw InvalidManifest();
        final path = row['path'] as String;
        final size = row['size'] as int;
        final digest = row['digest'] as String;
        if (!validPath(path) ||
            !paths.add(path) ||
            size < 0 ||
            size > 65536 ||
            !RegExp(r'^[0-9a-f]{64}$').hasMatch(digest))
          throw InvalidManifest();
        total += size;
        if (total > 262144) throw InvalidManifest();
        files.add(ManifestFile(path, size, digest));
      }
      for (final a in paths) {
        for (final b in paths) {
          if (a != b && b.startsWith('$a/')) throw InvalidManifest();
        }
      }
      return Manifest(files);
    } on InvalidManifest {
      rethrow;
    } catch (_) {
      throw InvalidManifest();
    }
  }
}
