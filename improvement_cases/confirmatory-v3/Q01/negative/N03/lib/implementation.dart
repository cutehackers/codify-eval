import 'dart:convert';
import 'api.dart';
class FeedController {
 final FeedTransport transport;
 final FeedCache cache;
 List<Entry> _entries = [];
 int _generation = 0;
 List<Entry> get entries => List.unmodifiable(_entries);
 FeedController(this.transport, this.cache);
 Future<void> restore() async {
  final generation = _generation;
  try {
   final raw = await cache.read();
   if (raw == null) return;
   final decoded = jsonDecode(raw);
   final rows = decoded is List ? decoded :
     decoded is Map && decoded['version'] == 2 ? decoded['entries'] : null;
   if (rows is! List) return;
   final parsed = <Entry>[];
   for (final row in rows) {
    if (row is! Map || row['id'] is! String || row['title'] is! String || row['updatedAt'] is! String) return;
    final timestamp = DateTime.tryParse(row['updatedAt'] as String);
    if (timestamp == null) return;
    parsed.add(Entry(row['id'] as String, row['title'] as String, timestamp.toUtc()));
   }
   if (_generation == generation) _entries = _normalize(parsed);
  } catch (_) { /* preserve current view on invalid cache */ }
 }
 List<Entry> _normalize(List<Entry> rows) {
  final byId = <String,Entry>{};
  for (final row in rows) {
   final old = byId[row.id];
   if (old == null || !row.updatedAt.isBefore(old.updatedAt)) byId[row.id] = Entry(row.id, row.title, row.updatedAt.toUtc());
  }
  final result = byId.values.toList();
  result.sort((a,b) { final date = b.updatedAt.compareTo(a.updatedAt); return date == 0 ? a.id.compareTo(b.id) : date; });
  return result;
 }
 Future<RefreshResult> refresh() async {
  final generation = ++_generation;
  final rows = <Entry>[];
  final cursors = <String>{};
  String? cursor;
  try {
   do {
    final page = await transport.fetch(cursor);
    
    rows.addAll(page.entries);
    cursor = page.next;
    if (cursor != null && !cursors.add(cursor)) throw StateError('cursor cycle');
   } while (cursor != null);
   final normalized = _normalize(rows);
   final encoded = jsonEncode({'version':2,'entries':normalized.map((e)=>{'id':e.id,'title':e.title,'updatedAt':e.updatedAt.toUtc().toIso8601String()}).toList()});
   
   // write is started only by a current generation; an already pending write
   // cannot be cancelled. Keep the latest visible generation after completion.
   await cache.write(encoded);
   
   _entries = normalized;
   return RefreshResult(RefreshState.applied, entries);
  } catch (_) {
   return RefreshResult(generation == _generation ? RefreshState.failed : RefreshState.superseded, entries);
  }
 }
}
