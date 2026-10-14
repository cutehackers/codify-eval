import 'package:flutter/material.dart';

typedef SaveName = Future<void> Function(String name);
void main() => runApp(MaterialApp(home: NameForm(save: (_) async {})));

class NameForm extends StatefulWidget {
  final SaveName save;
  const NameForm({super.key, required this.save});
  @override
  State<NameForm> createState() => _NameFormState();
}

class _NameFormState extends State<NameForm> {
  final input = TextEditingController();
  String message = '';
  bool busy = false;
  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    final clean = input.text.trim();
    if (clean.isEmpty) {
      setState(() => message = '이름을 입력하세요');
      return;
    }
    if (busy) return;
    setState(() {
      busy = true;
      message = '저장 중';
    });
    try {
      await widget.save(clean);
      if (mounted) setState(() => message = '저장 완료');
    } catch (_) {
      if (mounted) setState(() => message = '저장 실패. 다시 시도하세요');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
          body: Column(children: [
        TextField(key: const Key('name'), controller: input),
        TextButton(
            key: const Key('submit'),
            onPressed: busy ? null : submit,
            child: const Text('저장')),
        Text(message)
      ]));
}
