import 'dart:io';
import 'package:flutter/material.dart';
import 'todo_store.dart';
import 'todo_controller.dart';
import 'pages.dart';

void main() {
  final directory = Directory(
    Platform.environment['EVAL_DATA_DIR'] ??
        '${Directory.systemTemp.path}/codify-todos',
  );
  runApp(
    TodoApp(
      controller: TodoController(store: TodoStore(directory: directory)),
    ),
  );
}

class TodoApp extends StatelessWidget {
  final TodoController controller;
  const TodoApp({super.key, required this.controller});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: '내 할 일',
    theme: ThemeData(useMaterial3: true),
    home: TodoPage(controller: controller),
  );
}
