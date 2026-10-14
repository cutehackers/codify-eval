final class PermissionProvider {
  PermissionProvider(this.allowed);
  bool allowed;
  int calls = 0;
  final List<String> targets = [];
  bool canAccess(String workspaceId) { calls++; targets.add(workspaceId); return allowed; }
}
bool validId(Object? value) => value is String && RegExp(r'^[A-Za-z0-9_-]{1,40}$').hasMatch(value);
bool validRevision(Object? value) => value is int && value >= 0;
final class Outcome {
  Outcome(this.code, this.revision, [List<Map<String, Object>> report = const []])
      : report = List.unmodifiable(report.map((r) => Map<String, Object>.unmodifiable(r)));
  final String code;
  final int? revision;
  final List<Map<String, Object>> report;
  String get message => messages[code]!;
  static const messages = <String,String>{'applied':'Applied','unchanged':'Unchanged','forbidden':'Not allowed','invalid_request':'Invalid export','not_found':'Document unavailable','conflict':'Export changed','storage_failure':'Export unavailable'};
}

final class Document {
  const Document(this.workspaceId, this.id, this.title, this.body);
  final String workspaceId, id, title, body;
}
final class ExportRequest {
  ExportRequest(this.workspaceId, this.bundleId, this.expectedRevision, List<Object?> ids) : ids = List.unmodifiable(ids);
  final Object? workspaceId, bundleId, expectedRevision;
  final List<Object?> ids;
}
final class Selection {
  Selection(this.code, List<Document> documents) : documents = List.unmodifiable(documents);
  final String? code;
  final List<Document> documents;
}
final class TextBundle {
  TextBundle(List<int> manifest, Map<String,List<int>> files, List<Map<String,Object>> report)
      : manifest = List.unmodifiable(manifest), files = Map.unmodifiable(files.map((k,v) => MapEntry(k,List<int>.unmodifiable(v)))),
        report = List.unmodifiable(report.map((r) => Map<String,Object>.unmodifiable(r)));
  final List<int> manifest;
  final Map<String,List<int>> files;
  final List<Map<String,Object>> report;
}
final class BundleSnapshot {
  const BundleSnapshot(this.revision, this.bundle);
  final int revision;
  final TextBundle? bundle;
}
abstract interface class DocumentReader { Document? read(String workspaceId, String id); }
final class MemoryDocumentReader implements DocumentReader {
  final Map<String,Document> data = {};
  final List<String> reads = [];
  bool throwRead = false;
  @override Document? read(String workspaceId, String id) {
    reads.add('$workspaceId/$id');
    if (throwRead) throw StateError('private reader diagnostic');
    return data['$workspaceId/$id'];
  }
}
abstract interface class BundleStore {
  BundleSnapshot load(String workspaceId, String bundleId);
  bool compareAndReplace(String workspaceId, String bundleId, int revision, TextBundle bundle);
}
final class MemoryBundleStore implements BundleStore {
  final Map<String,BundleSnapshot> data = {};
  final List<String> loads = [];
  int commits = 0;
  bool throwLoad = false, throwCommit = false, rejectCommit = false;
  @override BundleSnapshot load(String workspaceId, String bundleId) {
    loads.add('$workspaceId/$bundleId');
    if (throwLoad) throw StateError('private store diagnostic');
    return data['$workspaceId/$bundleId'] ?? const BundleSnapshot(0,null);
  }
  @override bool compareAndReplace(String workspaceId, String bundleId, int revision, TextBundle bundle) {
    commits++;
    final key = '$workspaceId/$bundleId';
    final old = data[key] ?? const BundleSnapshot(0,null);
    if (rejectCommit || old.revision != revision) return false;
    final staged = BundleSnapshot(revision+1,bundle);
    if (throwCommit) throw StateError('private staged diagnostic');
    data[key] = staged;
    return true;
  }
}
bool sameBytes(List<int> a,List<int> b) {
  if (a.length != b.length) return false;
  for (var i=0;i<a.length;i++) { if (a[i]!=b[i]) return false; }
  return true;
}
bool sameBundle(TextBundle? a, TextBundle b) {
  if (a == null || !sameBytes(a.manifest,b.manifest) || a.files.length != b.files.length) return false;
  for (final e in b.files.entries) {
    final old = a.files[e.key]; if (old == null || !sameBytes(old,e.value)) return false;
  }
  return true;
}
