import 'package:flutter/foundation.dart';
import 'search_service.dart';
import 'search_state.dart';

class SearchController extends ChangeNotifier {
  final SearchService service;
  SearchController(this.service);
  SearchState _state = SearchState(SearchPhase.idle, '', const []);
  SearchState get state => _state;
  int _generation = 0;
  bool _disposed = false;
  void _emit(SearchState next) {
    _state = next;
    notifyListeners();
  }

  Future<void> search(String input) async {
    if (_disposed) return;
    final query = input.trim();
    final generation = ++_generation;
    if (query.isEmpty) {
      _state = SearchState(SearchPhase.idle, '', const []);
      return;
    }
    _emit(SearchState(SearchPhase.loading, query, const []));
    try {
      final result = await service.search(query);
      if (_disposed || generation != _generation) return;
      _emit(SearchState(SearchPhase.ready, query, result));
    } catch (_) {
      if (_disposed || generation != _generation) return;
      _emit(SearchState(SearchPhase.failed, query, const [], 'Search failed'));
    }
  }

  Future<void> retry() async {
    if (_disposed || _state.phase != SearchPhase.failed) return;
    await search(_state.query);
  }

  @override
  void dispose() {
    if (_disposed) return;
    _disposed = true;
    ++_generation;
    super.dispose();
  }
}
