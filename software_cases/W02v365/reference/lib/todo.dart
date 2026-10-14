class Todo {
  final String id;
  final String title;
  final bool done;
  final bool archived;
  const Todo({
    required this.id,
    required this.title,
    this.done = false,
    this.archived = false,
  });
  Todo copyWith({bool? done, bool? archived}) => Todo(
    id: id,
    title: title,
    done: done ?? this.done,
    archived: archived ?? this.archived,
  );
  Map<String, dynamic> toJson() => {
    'id': id,
    'title': title,
    'done': done,
    'archived': archived,
  };
  factory Todo.fromJson(Map<String, dynamic> json) => Todo(
    id: json['id'] as String,
    title: json['title'] as String,
    done: json['done'] as bool? ?? false,
    archived: json['archived'] as bool? ?? false,
  );
}
