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
              onTap: () {}),
      ]));
}
