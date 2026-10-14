import 'package:flutter/material.dart';
import 'notes.dart';
export 'notes.dart';

void main() => runApp(NoteApp(controller: NoteController()));

class NoteApp extends StatelessWidget {
  final NoteController controller;
  const NoteApp({super.key, required this.controller});
  @override
  Widget build(BuildContext context) =>
      MaterialApp(home: NotePage(controller: controller));
}

class NotePage extends StatefulWidget {
  final NoteController controller;
  const NotePage({super.key, required this.controller});
  @override
  State<NotePage> createState() => _NotePageState();
}

class _NotePageState extends State<NotePage> {
  final input = TextEditingController();
  int? editing;
  @override
  void dispose() {
    input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
      body: AnimatedBuilder(
          animation: widget.controller,
          builder: (context, _) => Column(children: [
                TextField(key: const Key('title'), controller: input),
                TextButton(
                    key: const Key('save'),
                    onPressed: () {
                      widget.controller.save(input.text, id: editing);
                      input.clear();
                      editing = null;
                    },
                    child: const Text('저장')),
                if (widget.controller.notes.isEmpty) const Text('기록 없음'),
                for (final note in widget.controller.notes)
                  ListTile(
                      key: ValueKey('note-${note.id}'),
                      title: Text(note.title),
                      onTap: () {
                        input.text = note.title;
                        editing = note.id;
                      }),
              ])));
}
