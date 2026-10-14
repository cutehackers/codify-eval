class Todo {
  final String id;
  final String title;
  final bool done;
  const Todo({required this.id, required this.title, this.done = false});
  Todo copyWith({bool? done}) =>
      Todo(id: id, title: title, done: done ?? this.done);
  Map<String, dynamic> toJson() => {'id': id, 'title': title, 'done': done};
  factory Todo.fromJson(Map<String, dynamic> json) => Todo(
    id: json['id'] as String,
    title: json['title'] as String,
    done: json['done'] as bool? ?? false,
  );
}
