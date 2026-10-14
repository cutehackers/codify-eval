import 'package:flutter/foundation.dart';
import 'todo.dart';
import 'todo_store.dart';

class TodoController extends ChangeNotifier {
  final TodoStore store;
  final List<Todo> items = [];
  bool loaded = false;
  String? error;
  TodoController({required this.store});
  Future<void> initialize() async {
    try {
      items
        ..clear()
        ..addAll(await store.load());
    } catch (_) {
      error = '목록을 불러오지 못했습니다';
    }
    loaded = true;
    notifyListeners();
  }

  Future<void> commit(List<Todo> next) async {
    try {
      await store.save(next);
      items
        ..clear()
        ..addAll(next);
      error = null;
    } catch (_) {
      error = '저장하지 못했습니다';
    }
    notifyListeners();
  }

  Future<void> add(String title) async {
    final clean = title.trim();
    if (clean.isEmpty) return;
    await commit([
      ...items,
      Todo(id: DateTime.now().microsecondsSinceEpoch.toString(), title: clean),
    ]);
  }

  Future<void> toggle(String id) async {
    await commit([
      for (final t in items)
        if (t.id == id) t.copyWith(done: !t.done) else t,
    ]);
  }
}
