import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';

void main() => runApp(const NotesApp());

class Note {
  final String id;
  final String title;
  final String body;
  const Note(this.id, this.title, this.body);
  Map<String, String> toJson() => {'id': id, 'title': title, 'body': body};
  factory Note.fromJson(Map<String, dynamic> json) => Note(
      json['id'] as String, json['title'] as String, json['body'] as String);
}

class NotesApp extends StatelessWidget {
  const NotesApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
      title: '내 메모',
      theme: ThemeData(useMaterial3: true),
      home: const NotesPage());
}

class NotesPage extends StatefulWidget {
  const NotesPage({super.key});
  @override
  State<NotesPage> createState() => _NotesPageState();
}

class _NotesPageState extends State<NotesPage> {
  final List<Note> notes = [];
  bool loaded = false;
  String? error;
  File get file => File(
      '${Platform.environment['EVAL_DATA_DIR'] ?? '${Directory.systemTemp.path}/codify-notes'}/notes.json');
  @override
  void initState() {
    super.initState();
    restore();
  }

  Future<void> restore() async {
    try {
      if (await file.exists()) {
        final data = jsonDecode(await file.readAsString()) as List<dynamic>;
        notes.addAll(data.map((v) => Note.fromJson(v as Map<String, dynamic>)));
      }
    } catch (_) {
      error = '메모를 불러오지 못했습니다';
    }
    if (mounted) setState(() => loaded = true);
  }

  Future<void> persist(List<Note> next) async {
    await file.parent.create(recursive: true);
    final temporary = File('${file.path}.tmp');
    await temporary.writeAsString(
        jsonEncode(next.map((n) => n.toJson()).toList()),
        flush: true);
    await temporary.rename(file.path);
    notes
      ..clear()
      ..addAll(next);
    if (mounted) setState(() {});
  }

  Future<void> editor([Note? existing]) async {
    final title = TextEditingController(text: existing?.title ?? '');
    final body = TextEditingController(text: existing?.body ?? '');
    String? validation;
    bool busy = false;
    await Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (context) => StatefulBuilder(
            builder: (context, setPage) => Scaffold(
                  appBar:
                      AppBar(title: Text(existing == null ? '새 메모' : '메모 편집')),
                  body: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(children: [
                        TextField(
                            controller: title,
                            decoration: const InputDecoration(labelText: '제목'),
                            autofocus: true),
                        TextField(
                            controller: body,
                            decoration: const InputDecoration(labelText: '내용'),
                            maxLines: 5),
                        if (validation != null) Text(validation!),
                        Row(children: [
                          FilledButton(
                              onPressed: busy
                                  ? null
                                  : () async {
                                      final clean = title.text.trim();
                                      if (clean.isEmpty) {
                                        setPage(() => validation = '제목을 입력하세요');
                                        return;
                                      }
                                      setPage(() {
                                        busy = true;
                                        validation = null;
                                      });
                                      final updated = Note(
                                          existing?.id ??
                                              DateTime.now()
                                                  .microsecondsSinceEpoch
                                                  .toString(),
                                          clean,
                                          body.text);
                                      final next = List<Note>.of(notes);
                                      if (existing == null) {
                                        next.add(updated);
                                      } else {
                                        next[next.indexWhere(
                                                (n) => n.id == existing.id)] =
                                            updated;
                                      }
                                      try {
                                        await persist(next);
                                        if (context.mounted)
                                          Navigator.of(context).pop();
                                      } catch (_) {
                                        if (context.mounted)
                                          setPage(() {
                                            busy = false;
                                            validation = '저장하지 못했습니다';
                                          });
                                      }
                                    },
                              child: const Text('저장')),
                          TextButton(
                              onPressed: () => Navigator.of(context).pop(),
                              child: const Text('취소')),
                        ]),
                      ])),
                ))));
    title.dispose();
    body.dispose();
  }

  Future<void> detail(Note original) async {
    await Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (context) => Scaffold(
              appBar: AppBar(title: const Text('메모 상세')),
              body: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        TextButton(
                            onPressed: () => Navigator.of(context)
                                .popUntil((route) => route.isFirst),
                            child: const Text('목록으로')),
                        Text(original.title),
                        Text(original.body),
                        Row(children: [
                          FilledButton(
                              onPressed: () {
                                Navigator.of(context).pop();
                                editor(original);
                              },
                              child: const Text('편집')),
                          TextButton(
                              onPressed: () async {
                                final confirmed = await showDialog<bool>(
                                    context: context,
                                    builder: (context) => AlertDialog(
                                          title: const Text('메모 삭제'),
                                          content: const Text('이 메모를 삭제할까요?'),
                                          actions: [
                                            TextButton(
                                                onPressed: () =>
                                                    Navigator.of(context)
                                                        .pop(false),
                                                child: const Text('취소')),
                                            TextButton(
                                                onPressed: () =>
                                                    Navigator.of(context)
                                                        .pop(true),
                                                child: const Text('삭제 확인'))
                                          ],
                                        ));
                                if (confirmed != true) return;
                                try {
                                  await persist(notes
                                      .where((n) => n.id != original.id)
                                      .toList());
                                  if (context.mounted)
                                    Navigator.of(context).pop();
                                } catch (_) {
                                  if (context.mounted)
                                    ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(
                                            content: Text('삭제하지 못했습니다')));
                                }
                              },
                              child: const Text('삭제')),
                        ]),
                      ])),
            )));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('내 메모')),
        body: !loaded
            ? const Center(child: Text('불러오는 중'))
            : Column(children: [
                if (error != null) Text(error!),
                if (notes.isEmpty) const Text('메모가 없습니다'),
                Expanded(
                    child: ListView(children: [
                  for (final note in notes)
                    ListTile(
                      title: Text(note.title),
                      subtitle: Text(note.body,
                          maxLines: 1, overflow: TextOverflow.ellipsis),
                      trailing: TextButton(
                          onPressed: () => detail(note),
                          child: Text('열기: ${note.title}')),
                    )
                ])),
              ]),
        floatingActionButton: loaded
            ? FloatingActionButton.extended(
                onPressed: editor, label: const Text('새 메모'))
            : null,
      );
}
