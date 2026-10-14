enum SearchPhase { idle, loading, ready, failed }

class SearchState {
  final SearchPhase phase;
  final String query;
  final List<String> items;
  final String? message;
  SearchState(this.phase, this.query, Iterable<String> items, [this.message])
      : items = List.unmodifiable(items);
}
