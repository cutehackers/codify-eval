import 'package:flutter/foundation.dart';

typedef SearchService = Future<List<String>> Function(String query);

class SearchController extends ChangeNotifier {
  final SearchService service;
  SearchController(this.service);
  List<String> results = [];
  String? error;
  bool busy = false;
  int _generation = 0;
  bool _disposed = false;
  Future<void> search(String query) async {
    if (_disposed) return;
    final generation = ++_generation;
    busy = true;
    error = null;
    notifyListeners();
    try {
      final next = await service(query);
      if (_disposed || generation != _generation) return;
      results = next;
      error = null;
    } catch (_) {
      if (_disposed || generation != _generation) return;
      error = '검색 실패';
    }
    if (_disposed || generation != _generation) return;
    busy = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _generation++;
    super.dispose();
  }
}
