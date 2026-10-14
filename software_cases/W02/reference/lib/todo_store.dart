import 'dart:convert';
import 'dart:io';
import 'todo.dart';

class TodoStore {
  final Directory directory;
  TodoStore({required this.directory});
  File get file => File('${directory.path}/todos.json');
  Future<List<Todo>> load() async {
    if (!await file.exists()) return [];
    final data = jsonDecode(await file.readAsString()) as List<dynamic>;
    return data.map((e) => Todo.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> save(List<Todo> todos) async {
    await directory.create(recursive: true);
    final temporary = File('${file.path}.tmp');
    await temporary.writeAsString(
      jsonEncode(todos.map((t) => t.toJson()).toList()),
      flush: true,
    );
    await temporary.rename(file.path);
  }
}
