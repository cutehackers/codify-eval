import 'entry.dart';

class EntryRepository {
  final List<Entry> entries;
  EntryRepository(this.entries);
  Entry? find(int id) {
    for (final entry in entries) {
      if (entry.id == id) return entry;
    }
    return null;
  }
}
