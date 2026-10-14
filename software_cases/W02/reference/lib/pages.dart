import 'package:flutter/material.dart';
import 'todo_controller.dart';
import 'todo.dart';

class TodoPage extends StatefulWidget {
  final TodoController controller;
  const TodoPage({super.key, required this.controller});
  @override
  State<TodoPage> createState() => _TodoPageState();
}

class _TodoPageState extends State<TodoPage> {
  final title = TextEditingController();
  String filter = '전체';
  List<Todo> get visible => widget.controller.items.where((t) {
    if (filter == '보관함') return t.archived;
    if (t.archived) return false;
    if (filter == '진행 중') return !t.done;
    if (filter == '완료') return t.done;
    return true;
  }).toList();
  @override
  void initState() {
    super.initState();
    widget.controller.initialize();
  }

  @override
  void dispose() {
    title.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('내 할 일')),
    body: AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) => !widget.controller.loaded
          ? const Center(child: Text('불러오는 중'))
          : Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: title,
                          decoration: const InputDecoration(
                            labelText: '할 일 제목',
                          ),
                        ),
                      ),
                      FilledButton(
                        onPressed: () async {
                          await widget.controller.add(title.text);
                          if (widget.controller.error == null) title.clear();
                        },
                        child: const Text('추가'),
                      ),
                    ],
                  ),
                ),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    for (final name in ['전체', '진행 중', '완료', '보관함'])
                      TextButton(
                        onPressed: () => setState(() => filter = name),
                        child: Text(name),
                      ),
                  ],
                ),
                if (widget.controller.error != null)
                  Text(widget.controller.error!),
                if (widget.controller.pendingSave != null)
                  TextButton(
                    onPressed: () async {
                      await widget.controller.retry();
                      if (widget.controller.error == null) title.clear();
                    },
                    child: const Text('다시 시도'),
                  ),
                if (visible.isEmpty) const Text('할 일이 없습니다'),
                Expanded(
                  child: ListView(
                    children: [
                      for (final todo in visible)
                        ListTile(
                          title: Text(todo.title),
                          subtitle: Text(todo.done ? '완료' : '진행 중'),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              if (!todo.archived)
                                TextButton(
                                  onPressed: () =>
                                      widget.controller.toggle(todo.id),
                                  child: Text(
                                    '${todo.done ? '완료 취소' : '완료'}: ${todo.title}',
                                  ),
                                ),
                              if (todo.done && !todo.archived)
                                TextButton(
                                  onPressed: () =>
                                      widget.controller.archive(todo.id),
                                  child: Text('보관: ${todo.title}'),
                                ),
                              if (todo.archived)
                                TextButton(
                                  onPressed: () =>
                                      widget.controller.restore(todo.id),
                                  child: Text('복원: ${todo.title}'),
                                ),
                            ],
                          ),
                        ),
                    ],
                  ),
                ),
              ],
            ),
    ),
  );
}
