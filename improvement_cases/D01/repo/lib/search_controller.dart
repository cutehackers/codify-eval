import 'package:flutter/foundation.dart';
import 'search_service.dart';
import 'search_state.dart';

class SearchController extends ChangeNotifier {
  final SearchService service;
  SearchController(this.service);
  SearchState _state = SearchState(SearchPhase.idle, '', const []);
  SearchState get state => _state;
  String _lastQuery = '';
  Future<void> search(String input) async {
    _lastQuery = input;
    _state = SearchState(SearchPhase.loading, input, _state.items);
    notifyListeners();
    try {
      final result = await service.search(input);
      _state = SearchState(SearchPhase.ready, input, result);
    } catch (error) {
      _state = SearchState(
          SearchPhase.failed, input, _state.items, error.toString());
    }
    notifyListeners();
  }

  Future<void> retry() => search(_lastQuery);
}
