import 'contracts.dart';

class ManifestCodec {
  ManifestCodec(this.integrity);
  final Integrity integrity;
  Manifest decode(String text, String tag) => throw InvalidManifest();
  static bool validPath(String path) => false;
}
