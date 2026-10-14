import 'package:flutter/material.dart';
import 'user_banner.dart';

void main() => runApp(const TodoPage());

class TodoPage extends StatefulWidget {
  const TodoPage({super.key});
  @override
  State<TodoPage> createState() => _TodoPageState();
}

class _TodoPageState extends State<TodoPage> {
  bool done = false;
  @override
  Widget build(BuildContext context) => MaterialApp(
          home: Scaffold(
              body: Column(children: [
        const Text(userBanner),
        Checkbox(key: const Key('done'), value: done, onChanged: (value) {}),
        Text(done ? '완료' : '진행 중')
      ])));
}
