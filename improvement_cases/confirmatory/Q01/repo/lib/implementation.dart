import 'api.dart';
class FeedController {
 final FeedTransport transport;
 final FeedCache cache;
 List<Entry> _entries = [];
 List<Entry> get entries => List.unmodifiable(_entries);
 FeedController(this.transport, this.cache);
 Future<void> restore() async { await cache.read(); }
 Future<RefreshResult> refresh() async {
  try { final page = await transport.fetch(null); _entries = page.entries;
   return RefreshResult(RefreshState.applied, entries);
  } catch (_) { _entries = []; return RefreshResult(RefreshState.failed, entries); }
 }
}
