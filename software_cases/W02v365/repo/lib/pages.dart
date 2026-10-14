import 'package:flutter/material.dart';
import 'todo_controller.dart';

class TodoPage extends StatefulWidget {
  final TodoController controller;
  const TodoPage({super.key, required this.controller});
  @override
  State<TodoPage> createState() => _TodoPageState();
}

class _TodoPageState extends State<TodoPage> {
  final title = TextEditingController();
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
                          title.clear();
                        },
                        child: const Text('추가'),
                      ),
                    ],
                  ),
                ),
                if (widget.controller.error != null)
                  Text(widget.controller.error!),
                if (widget.controller.items.isEmpty) const Text('할 일이 없습니다'),
                Expanded(
                  child: ListView(
                    children: [
                      for (final todo in widget.controller.items)
                        ListTile(
                          title: Text(todo.title),
                          subtitle: Text(todo.done ? '완료' : '진행 중'),
                          trailing: TextButton(
                            onPressed: () => widget.controller.toggle(todo.id),
                            child: Text(
                              '${todo.done ? '완료 취소' : '완료'}: ${todo.title}',
                            ),
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
