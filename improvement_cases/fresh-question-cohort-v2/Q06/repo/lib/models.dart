const maxNotes = 20;
const maxTitleLength = 80;
const maxBodyLength = 1000;
class Note {
  final String id;
  final String title;
  final String body;
  final String metadata;
  const Note(this.id, this.title, this.body, {this.metadata = 'imported'});
}
class ImportResult {
  final String code;
  final List<String> insertedIds;
  final List<String> updatedIds;
  final List<String> unchangedIds;
  const ImportResult(this.code, {this.insertedIds = const [], this.updatedIds = const [], this.unchangedIds = const []});
}
class Identity {
  final String userId;
  const Identity(this.userId);
}
class Workspace {
  final Set<String> editors;
  Map<String, Note> notes;
  Workspace(this.editors, Map<String, Note> notes) : notes = Map.of(notes);
}
class MemoryStore {
  final Map<String, Workspace> workspaces;
  bool failCommit = false;
  int reads = 0;
  int commits = 0;
  int writes = 0;
  MemoryStore(this.workspaces);
  bool canEdit(String id, String user) => workspaces[id]?.editors.contains(user) ?? false;
  Map<String, Note> snapshot(String id) { reads++; return Map.of(workspaces[id]!.notes); }
  void apply(String id, List<Note> changes) {
    if (failCommit) throw StateError('SECRET storage path');
    workspaces[id]!.notes = {...workspaces[id]!.notes, for(final n in changes) n.id: n};
    writes += changes.length;
    commits++;
  }
}
