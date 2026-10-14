import 'dart:convert';

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
  static const messages = <String,String>{'applied':'Applied','unchanged':'Unchanged','forbidden':'Not allowed','invalid_import':'Invalid import','conflict':'Import changed','storage_failure':'Import unavailable'};
}

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
  void ws() { while (i < text.length && ' \r\n\t'.contains(text[i])) { i++; } }
  String string() {
    final start = i++; bool escaped = false;
    while (i < text.length) {
      final c = text[i++];
      if (!escaped && c == '"') return jsonDecode(text.substring(start, i)) as String;
      if (!escaped && c == '\\') { escaped = true; } else { escaped = false; }
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
    while (i < text.length && !',]} \r\n\t'.contains(text[i])) { i++; }
    if (i == start) throw DecodeFailure();
    return jsonDecode(text.substring(start,i));
  }
}
