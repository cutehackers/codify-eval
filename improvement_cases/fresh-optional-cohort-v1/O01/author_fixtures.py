from pathlib import Path
import json, hashlib, shutil
BASE=Path(__file__).resolve().parent.parent

def write(case,path,text):
 p=BASE/case/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text.strip()+'\n')
for c in ['O01','O02']:
 write(c,'repo/pubspec.yaml',f'''name: {c.lower()}_fixture
publish_to: none
environment:
  sdk: '>=3.3.0 <4.0.0'
dependencies:
  flutter:
    sdk: flutter
dev_dependencies:
  flutter_test:
    sdk: flutter''')
 write(c,'repo/analysis_options.yaml','analyzer:\n  errors:\n    unused_import: error')

common='''import 'dart:convert';

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
  static const messages = <String,String>{MESSAGES};
}
'''
msgs1="'applied':'Applied','unchanged':'Unchanged','forbidden':'Not allowed','invalid_import':'Invalid import','conflict':'Import changed','storage_failure':'Import unavailable'"
msgs2="'applied':'Applied','unchanged':'Unchanged','forbidden':'Not allowed','invalid_request':'Invalid export','not_found':'Document unavailable','conflict':'Export changed','storage_failure':'Export unavailable'"
models1=common.replace('MESSAGES',msgs1)+'''
final class SavedSearch {
  const SavedSearch(this.workspaceId, this.id, this.title, this.expression, this.createdAt);
  final String workspaceId, id, title, expression, createdAt;
}
final class PortableSearch {
  const PortableSearch(this.id, this.title, this.expression);
  final String id, title, expression;
}
final class ImportData {
  ImportData(this.workspaceId, List<PortableSearch> rows) : rows = List.unmodifiable(rows);
  final String workspaceId;
  final List<PortableSearch> rows;
}
final class SearchSnapshot {
  SearchSnapshot(this.revision, Map<String,SavedSearch> records) : records = Map.unmodifiable(records);
  final int revision;
  final Map<String,SavedSearch> records;
}
final class SearchPlan {
  SearchPlan(List<SavedSearch> effects, List<Map<String,Object>> report)
      : effects = List.unmodifiable(effects), report = List.unmodifiable(report);
  final List<SavedSearch> effects;
  final List<Map<String,Object>> report;
}
abstract interface class SearchStore {
  SearchSnapshot load(String workspaceId);
  bool compareAndApply(String workspaceId, int revision, List<SavedSearch> effects);
}
/// This adapter owns atomic rollback. Failure after staging never mutates saved state.
final class MemorySearchStore implements SearchStore {
  final Map<String, SearchSnapshot> data = {};
  final List<String> loads = [];
  int commits = 0;
  bool throwLoad = false, throwCommit = false, rejectCommit = false;
  @override SearchSnapshot load(String workspaceId) {
    loads.add(workspaceId);
    if (throwLoad) throw StateError('private store diagnostic');
    return data[workspaceId] ?? SearchSnapshot(0, {});
  }
  @override bool compareAndApply(String workspaceId, int revision, List<SavedSearch> effects) {
    commits++;
    final old = data[workspaceId] ?? SearchSnapshot(0, {});
    if (rejectCommit || old.revision != revision) return false;
    final staged = Map<String,SavedSearch>.from(old.records);
    for (final row in effects) { staged[row.id] = row; }
    if (throwCommit) throw StateError('private staged diagnostic');
    data[workspaceId] = SearchSnapshot(revision + 1, staged);
    return true;
  }
}
final class DecodeFailure implements Exception {}
/// Protected JSON boundary. Duplicate object keys and malformed JSON are rejected.
Object? decodePortableJson(String text) {
  try {
    final parser = _StrictJson(text);
    final result = parser.value(); parser.ws();
    if (parser.i != text.length) throw DecodeFailure();
    return result;
  } catch (_) { throw DecodeFailure(); }
}
final class _StrictJson {
  _StrictJson(this.text);
  final String text; int i = 0;
  void ws() { while (i < text.length && ' \\r\\n\\t'.contains(text[i])) { i++; } }
  String string() {
    final start = i++; bool escaped = false;
    while (i < text.length) {
      final c = text[i++];
      if (!escaped && c == '"') return jsonDecode(text.substring(start, i)) as String;
      if (!escaped && c == '\\\\') { escaped = true; } else { escaped = false; }
    }
    throw DecodeFailure();
  }
  Object? value() {
    ws(); if (i >= text.length) throw DecodeFailure();
    if (text[i] == '"') return string();
    if (text[i] == '{') {
      i++; ws(); final out = <String,Object?>{};
      if (i < text.length && text[i] == '}') { i++; return out; }
      while (true) {
        ws(); if (i >= text.length || text[i] != '"') throw DecodeFailure();
        final key = string(); if (out.containsKey(key)) throw DecodeFailure();
        ws(); if (i >= text.length || text[i++] != ':') throw DecodeFailure();
        out[key] = value(); ws(); if (i >= text.length) throw DecodeFailure();
        final end = text[i++]; if (end == '}') return out;
        if (end != ',') throw DecodeFailure();
      }
    }
    if (text[i] == '[') {
      i++; ws(); final out = <Object?>[];
      if (i < text.length && text[i] == ']') { i++; return out; }
      while (true) {
        out.add(value()); ws(); if (i >= text.length) throw DecodeFailure();
        final end = text[i++]; if (end == ']') return out;
        if (end != ',') throw DecodeFailure();
      }
    }
    final start = i;
    while (i < text.length && !',]} \\r\\n\\t'.contains(text[i])) { i++; }
    if (i == start) throw DecodeFailure();
    return jsonDecode(text.substring(start,i));
  }
}
'''
write('O01','repo/lib/models.dart',models1)
codec='''import 'dart:convert';
import 'models.dart';

ImportData? decodeSearchImport(Object? value) {
  if (value is! Map || value.keys.any((k) => k is! String)) return null;
  final version = value['version'];
  if (version is! int || (version != 1 && version != 2)) return null;
  final collection = version == 1 ? 'searches' : 'items';
  if (value.length != 3 || !value.containsKey('workspaceId') || !value.containsKey(collection)) return null;
  final workspace = value['workspaceId']; final rows = value[collection];
  if (!validId(workspace) || rows is! List || rows.length > 100) return null;
  final ids = <String>{}; final result = <PortableSearch>[];
  for (final row in rows) {
    if (row is! Map || row.length != 3 || !row.containsKey('id')) return null;
    final titleKey = version == 1 ? 'label' : 'title';
    final expressionKey = version == 1 ? 'query' : 'expression';
    if (!row.containsKey(titleKey) || !row.containsKey(expressionKey)) return null;
    final id = row['id'], title = row[titleKey], expression = row[expressionKey];
    if (!validId(id) || title is! String || title.isEmpty || title.length > 80 ||
        expression is! String || expression.isEmpty || expression.length > 2000 || !ids.add(id as String)) return null;
    result.add(PortableSearch(id, title, expression));
  }
  return ImportData(workspace as String, result);
}
String encodeSearchExport(ImportData data) => '${jsonEncode({
  'version': 2, 'workspaceId': data.workspaceId,
  'items': data.rows.map((r) => {'id': r.id, 'title': r.title, 'expression': r.expression}).toList(),
})}\\n';
'''
plan='''import 'models.dart';

SearchPlan planSearchImport(ImportData data, SearchSnapshot snapshot) {
  final effects = <SavedSearch>[]; final report = <Map<String,Object>>[];
  for (final row in data.rows) {
    final old = snapshot.records[row.id];
    final action = old == null ? 'inserted' : old.title == row.title && old.expression == row.expression ? 'unchanged' : 'updated';
    if (action != 'unchanged') {
      effects.add(SavedSearch(data.workspaceId, row.id, row.title, row.expression, old?.createdAt ?? 'imported'));
    }
    report.add({'id': row.id, 'action': action});
  }
  return SearchPlan(effects, report);
}
'''
service='''import 'models.dart';
import 'search_codec.dart';
import 'search_plan.dart';

Outcome importSavedSearches({required Object? targetWorkspaceId, required Object? expectedRevision,
    required String jsonText, required PermissionProvider permissions, required SearchStore store}) {
  // Permission identity comes from the injected provider, never the payload.
  if (!permissions.canAccess(targetWorkspaceId is String ? targetWorkspaceId : '')) return Outcome('forbidden', null);
  if (!validId(targetWorkspaceId) || !validRevision(expectedRevision)) return Outcome('invalid_import', null);
  ImportData? data;
  try { data = decodeSearchImport(decodePortableJson(jsonText)); }
  on DecodeFailure { return Outcome('invalid_import', null); }
  if (data == null || data.workspaceId != targetWorkspaceId) return Outcome('invalid_import', null);
  try {
    final snapshot = store.load(targetWorkspaceId as String);
    for (final entry in snapshot.records.entries) {
      if (entry.value.workspaceId != targetWorkspaceId || entry.value.id != entry.key || !validId(entry.key)) return Outcome('forbidden', null);
    }
    if (snapshot.revision != expectedRevision) return Outcome('conflict', null);
    final plan = planSearchImport(data, snapshot);
    if (plan.effects.isEmpty) return Outcome('unchanged', snapshot.revision, plan.report);
    if (!store.compareAndApply(targetWorkspaceId, snapshot.revision, plan.effects)) return Outcome('conflict', null);
    return Outcome('applied', snapshot.revision + 1, plan.report);
  } catch (_) { return Outcome('storage_failure', null); }
}
'''
refs1={'search_codec.dart':codec,'search_plan.dart':plan,'search_import_service.dart':service}
for f,t in refs1.items():write('O01','private/reference/lib/'+f,t)
write('O01','repo/lib/search_codec.dart',"import 'models.dart';\nImportData? decodeSearchImport(Object? value) => throw UnimplementedError();\nString encodeSearchExport(ImportData data) => throw UnimplementedError();")
write('O01','repo/lib/search_plan.dart',"import 'models.dart';\nSearchPlan planSearchImport(ImportData data, SearchSnapshot snapshot) => throw UnimplementedError();")
write('O01','repo/lib/search_import_service.dart',"import 'models.dart';\nOutcome importSavedSearches({required Object? targetWorkspaceId, required Object? expectedRevision, required String jsonText, required PermissionProvider permissions, required SearchStore store}) => throw UnimplementedError();")

models2=common.replace("import 'dart:convert';\n",'').replace('MESSAGES',msgs2)+'''
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
'''
write('O02','repo/lib/models.dart',models2)
selection='''import 'models.dart';

bool validExportRequest(ExportRequest request) => validId(request.workspaceId) && validId(request.bundleId) &&
    validRevision(request.expectedRevision) && request.ids.isNotEmpty && request.ids.length <= 100 &&
    request.ids.every(validId) && request.ids.toSet().length == request.ids.length;
Selection selectDocuments(ExportRequest request, DocumentReader reader) {
  final docs = <Document>[];
  for (final id in request.ids) {
    final doc = reader.read(request.workspaceId as String, id as String);
    if (doc == null) return Selection('not_found', []);
    if (doc.workspaceId != request.workspaceId || doc.id != id) return Selection('forbidden', []);
    docs.add(doc);
  }
  return Selection(null, docs);
}
'''
encoding='''import 'dart:convert';
import 'models.dart';

TextBundle? encodeTextBundle(String workspaceId, List<Document> documents) {
  // Validate every record before producing a bundle.
  if (documents.any((d) => !validId(d.id) || d.workspaceId != workspaceId || d.title.length > 80 || d.body.length > 100000)) return null;
  final files = <String,List<int>>{}; final manifestRows = <Map<String,Object>>[]; final report = <Map<String,Object>>[];
  for (final doc in documents) {
    final path = 'documents/${doc.id}.txt'; final bytes = utf8.encode(doc.body);
    files[path] = bytes;
    manifestRows.add({'id':doc.id,'title':doc.title,'path':path,'byteLength':bytes.length});
    report.add({'id':doc.id,'path':path,'byteLength':bytes.length});
  }
  final manifest = utf8.encode('${jsonEncode({'version':1,'workspaceId':workspaceId,'documents':manifestRows})}\\n');
  return TextBundle(manifest, files, report);
}
'''
eservice='''import 'models.dart';
import 'export_selection.dart';
import 'export_encoding.dart';

Outcome exportTextBundle({required ExportRequest request, required PermissionProvider permissions,
    required DocumentReader reader, required BundleStore store,
    TextBundle? Function(String,List<Document>)? encoder}) {
  if (!permissions.canAccess(request.workspaceId is String ? request.workspaceId as String : '')) return Outcome('forbidden', null);
  if (!validExportRequest(request)) return Outcome('invalid_request', null);
  try {
    final selected = selectDocuments(request, reader);
    if (selected.code != null) return Outcome(selected.code!, null);
    // Normal length/shape failures are invalid requests even with an injected encoder.
    if (selected.documents.any((d) => d.title.length > 80 || d.body.length > 100000)) return Outcome('invalid_request', null);
    final bundle = (encoder ?? encodeTextBundle)(request.workspaceId as String, selected.documents);
    if (bundle == null) return Outcome('invalid_request', null);
    final snapshot = store.load(request.workspaceId as String, request.bundleId as String);
    if (snapshot.revision != request.expectedRevision) return Outcome('conflict', null);
    if (sameBundle(snapshot.bundle,bundle)) return Outcome('unchanged', snapshot.revision,bundle.report);
    if (!store.compareAndReplace(request.workspaceId as String,request.bundleId as String,snapshot.revision,bundle)) return Outcome('conflict',null);
    return Outcome('applied',snapshot.revision+1,bundle.report);
  } catch (_) { return Outcome('storage_failure',null); }
}
'''
refs2={'export_selection.dart':selection,'export_encoding.dart':encoding,'export_service.dart':eservice}
for f,t in refs2.items():write('O02','private/reference/lib/'+f,t)
write('O02','repo/lib/export_selection.dart',"import 'models.dart';\nbool validExportRequest(ExportRequest request) => throw UnimplementedError();\nSelection selectDocuments(ExportRequest request, DocumentReader reader) => throw UnimplementedError();")
write('O02','repo/lib/export_encoding.dart',"import 'models.dart';\nTextBundle? encodeTextBundle(String workspaceId,List<Document> documents) => throw UnimplementedError();")
write('O02','repo/lib/export_service.dart',"import 'models.dart';\nOutcome exportTextBundle({required ExportRequest request, required PermissionProvider permissions, required DocumentReader reader, required BundleStore store, TextBundle? Function(String,List<Document>)? encoder}) => throw UnimplementedError();")
# Each negative is the whole three-file implementation with one independently identified defect.
neg1={
 'security_permission_bypass':('search_import_service.dart',service.replace("if (!permissions.canAccess(targetWorkspaceId is String ? targetWorkspaceId : '')) return Outcome('forbidden', null);","permissions.canAccess(targetWorkspaceId is String ? targetWorkspaceId : '');")),
 'atomicity_stale_revision':('search_import_service.dart',service.replace("if (snapshot.revision != expectedRevision) return Outcome('conflict', null);",'// Incorrectly trusts the loaded revision instead of the request revision.')),
 'compatibility_v1_query':('search_codec.dart',codec.replace("result.add(PortableSearch(id, title, expression));","result.add(PortableSearch(id, title, version == 1 ? title : expression));")),
 'reporting_reverse_order':('search_plan.dart',plan.replace('SearchPlan(effects, report);','SearchPlan(effects, report.reversed.toList());')),
}
neg2={
 'security_permission_bypass':('export_service.dart',eservice.replace("if (!permissions.canAccess(request.workspaceId is String ? request.workspaceId as String : '')) return Outcome('forbidden', null);","permissions.canAccess(request.workspaceId is String ? request.workspaceId as String : '');")),
 'atomicity_stale_noop':('export_service.dart',eservice.replace("    if (snapshot.revision != request.expectedRevision) return Outcome('conflict', null);\n    if (sameBundle(snapshot.bundle,bundle)) return Outcome('unchanged', snapshot.revision,bundle.report);","    if (sameBundle(snapshot.bundle,bundle)) return Outcome('unchanged', snapshot.revision,bundle.report);\n    if (snapshot.revision != request.expectedRevision) return Outcome('conflict', null);")),
 'compatibility_byte_length':('export_encoding.dart',encoding.replace("'byteLength':bytes.length","'byteLength':doc.body.length")),
 'reporting_reverse_order':('export_encoding.dart',encoding.replace('TextBundle(manifest, files, report);','TextBundle(manifest, files, report.reversed.toList());')),
}
for c,refs,negs in [('O01',refs1,neg1),('O02',refs2,neg2)]:
 for name,(changed,body) in negs.items():
  for f,t in refs.items():write(c,f'private/negative_controls/{name}/lib/{f}',body if f==changed else t)
  write(c,f'private/negative_controls/{name}/fault.json',json.dumps({'fault_category':name.split('_')[0],'changed_file':'lib/'+changed,'independent_fault':name,'expected':'assertion_failure_not_compile_error'},indent=2))
