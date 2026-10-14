import 'dart:convert';
import 'models.dart';
class NoteImportService {
  final MemoryStore store;
  final Identity identity;
  NoteImportService(this.store, this.identity);
  ImportResult importBackup(String targetWorkspaceId, String backupJson) {
    if (!store.workspaces.containsKey(targetWorkspaceId)) return const ImportResult('access_denied');
    dynamic data;
    try { data = jsonDecode(backupJson); } catch (_) { return const ImportResult('invalid_backup'); }
    if (data is! Map<String, dynamic> || data.length != 3 ||
        !data.containsKey('version') || !data.containsKey('workspaceId') || !data.containsKey('notes') ||
        data['version'] is! int || data['version'] != 1 || data['workspaceId'] is! String ||
        data['workspaceId'] != targetWorkspaceId || data['notes'] is! List ||
        (data['notes'] as List).length > maxNotes) return const ImportResult('invalid_backup');
    final incoming = <Note>[];
    final ids = <String>{};
    for (final item in data['notes'] as List) {
      if (item is! Map<String, dynamic> || item.length != 3 ||
          !item.containsKey('id') || !item.containsKey('title') || !item.containsKey('body') ||
          item['id'] is! String || item['title'] is! String || item['body'] is! String) {
        return const ImportResult('invalid_backup');
      }
      final id = item['id'] as String; final title = item['title'] as String; final body = item['body'] as String;
      if (id.trim().isEmpty || !ids.add(id) || title.length > maxTitleLength || body.length > maxBodyLength) {
        return const ImportResult('invalid_backup');
      }
      incoming.add(Note(id, title, body));
    }
    final existing = store.snapshot(targetWorkspaceId);
    final changes = <Note>[]; final inserted = <String>[]; final updated = <String>[]; final unchanged = <String>[];
    for (final note in incoming) {
      final old = existing[note.id];
      if (old == null) { changes.add(note); inserted.add(note.id); }
      else { unchanged.add(note.id); }
    }
    if (changes.isEmpty) return ImportResult('ok', insertedIds: inserted, updatedIds: updated, unchangedIds: unchanged);
    try {
      store.apply(targetWorkspaceId, changes);
      return ImportResult('ok', insertedIds: inserted, updatedIds: updated, unchangedIds: unchanged);
    } catch (_) { return const ImportResult('storage_failure'); }
  }
}
