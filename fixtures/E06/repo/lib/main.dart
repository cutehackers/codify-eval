import 'package:flutter/material.dart';
import 'store.dart';
export 'store.dart';

void main() => runApp(MaterialApp(home: DraftPage(store: MemoryStore())));

class DraftPage extends StatefulWidget {
  final LocalStore store;
  const DraftPage({super.key, required this.store});
  @override
  State<DraftPage> createState() => _DraftPageState();
}

class _DraftPageState extends State<DraftPage> {
  final input = TextEditingController();
  String message = '';
  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  Future<void> save() async {
    setState(() => message = '저장됨');
  }

  @override
  Widget build(BuildContext context) => Scaffold(
          body: Column(children: [
        TextField(key: const Key('draft'), controller: input),
        TextButton(
            key: const Key('save'), onPressed: save, child: const Text('저장')),
        Text(message)
      ]));
}
