import 'package:flutter/material.dart';
import 'entry.dart';
import 'repository.dart';
import 'pages.dart';
export 'entry.dart';
export 'repository.dart';
export 'pages.dart';

void main() => runApp(EntryApp(
    repository: EntryRepository(
        const [Entry(1, '산책', '저녁 산책'), Entry(2, '독서', '책 읽기')])));

class EntryApp extends StatelessWidget {
  final EntryRepository repository;
  const EntryApp({super.key, required this.repository});
  @override
  Widget build(BuildContext context) =>
      MaterialApp(home: EntryList(repository: repository));
}
