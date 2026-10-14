const contractVersion = 1;
class JournalRecord {
 final String id;
 final DateTime completedAt;
 final bool completed;
 const JournalRecord(this.id,this.completedAt,{required this.completed});
}
abstract class JournalDisk {
 Future<List<JournalRecord>> readAll();
 // Atomic deletion of IDs. No partial deletion if it throws.
 Future<void> deleteIds(Set<String> ids);
}
abstract class Clock { DateTime now(); }
class RetentionPreview {
 final Set<String> ids;
 final DateTime evaluatedAt;
 RetentionPreview(Set<String> ids,this.evaluatedAt):ids=Set.unmodifiable(ids);
}
