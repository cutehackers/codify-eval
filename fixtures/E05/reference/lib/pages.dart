import 'package:flutter/material.dart';
import 'repository.dart';

class EntryList extends StatelessWidget {
  final EntryRepository repository;
  const EntryList({super.key, required this.repository});
  @override
  Widget build(BuildContext context) => Scaffold(
      appBar: AppBar(title: const Text('기록')),
      body: ListView(children: [
        for (final entry in repository.entries)
          ListTile(
              key: ValueKey('entry-${entry.id}'),
              title: Text(entry.title),
              onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
                  builder: (_) =>
                      EntryDetail(repository: repository, id: entry.id)))),
      ]));
}

class EntryDetail extends StatelessWidget {
  final EntryRepository repository;
  final int id;
  const EntryDetail({super.key, required this.repository, required this.id});
  @override
  Widget build(BuildContext context) {
    final entry = repository.find(id);
    return Scaffold(
        appBar: AppBar(title: Text(entry?.title ?? '찾을 수 없음')),
        body: Text(entry?.body ?? '기록이 없습니다'));
  }
}
