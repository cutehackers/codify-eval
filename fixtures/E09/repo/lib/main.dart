import 'package:flutter/foundation.dart';

typedef SearchService = Future<List<String>> Function(String query);

class SearchController extends ChangeNotifier {
  final SearchService service;
  SearchController(this.service);
  List<String> results = [];
  String? error;
  bool busy = false;
  Future<void> search(String query) async {
    busy = true;
    notifyListeners();
    try {
      results = await service(query);
      error = null;
    } catch (_) {
      error = '검색 실패';
    }
    busy = false;
    notifyListeners();
  }
}
