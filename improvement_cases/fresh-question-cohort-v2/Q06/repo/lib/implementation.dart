import 'models.dart';
class NoteImportService {
  final MemoryStore store;
  final Identity identity;
  NoteImportService(this.store, this.identity);
  ImportResult importBackup(String targetWorkspaceId, String backupJson) => throw UnimplementedError();
}
