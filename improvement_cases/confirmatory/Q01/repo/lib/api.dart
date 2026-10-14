const contractVersion = 1;
class Entry {
  final String id;
  final String title;
  final DateTime updatedAt;
  const Entry(this.id, this.title, this.updatedAt);
}
class Page {
  final List<Entry> entries;
  final String? next;
  const Page(this.entries, this.next);
}
abstract class FeedTransport { Future<Page> fetch(String? cursor); }
abstract class FeedCache {
  Future<String?> read();
  Future<void> write(String encoded);
}
enum RefreshState { applied, superseded, failed }
class RefreshResult {
 final RefreshState state;
 final List<Entry> entries;
 const RefreshResult(this.state, this.entries);
}
