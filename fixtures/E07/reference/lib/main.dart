import 'dart:convert';

class SavedTask {
  final String title;
  final bool done;
  const SavedTask(this.title, this.done);
  Map<String, Object> toJson() => {'schema': 2, 'title': title, 'done': done};
}

List<SavedTask> decodeTasks(String data) {
  final root = jsonDecode(data);
  if (root is! List) throw const FormatException('expected list');
  return root.map((v) {
    if (v is! Map) throw const FormatException('expected object');
    final version = v['schema'];
    if (v.containsKey('schema') && version != 1 && version != 2)
      throw const FormatException('unsupported schema');
    final title = v.containsKey('title') ? v['title'] : v['name'];
    final done = v.containsKey('done') ? v['done'] : false;
    if (title is! String || done is! bool)
      throw const FormatException('invalid task');
    return SavedTask(title, done);
  }).toList();
}

String encodeTasks(List<SavedTask> tasks) =>
    jsonEncode(tasks.map((t) => t.toJson()).toList());
