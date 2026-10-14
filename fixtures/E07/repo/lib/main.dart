import 'dart:convert';

class SavedTask {
  final String title;
  final bool done;
  const SavedTask(this.title, this.done);
  Map<String, Object> toJson() => {'schema': 2, 'title': title, 'done': done};
}

List<SavedTask> decodeTasks(String data) {
  final values = jsonDecode(data) as List<dynamic>;
  return values.map((v) {
    final m = v as Map<String, dynamic>;
    return SavedTask(m['title'] as String, m['done'] as bool);
  }).toList();
}

String encodeTasks(List<SavedTask> tasks) =>
    jsonEncode(tasks.map((t) => t.toJson()).toList());
