import 'package:flutter/material.dart';

void main() => runApp(const MaterialApp(
    home: CatalogPage(items: ['Apple', 'Banana', 'Apricot'])));

class CatalogPage extends StatefulWidget {
  final List<String> items;
  const CatalogPage({super.key, required this.items});
  @override
  State<CatalogPage> createState() => _CatalogPageState();
}

class _CatalogPageState extends State<CatalogPage> {
  String query = '';
  @override
  Widget build(BuildContext context) {
    final q = query.trim().toLowerCase();
    final visible =
        widget.items.where((item) => item.toLowerCase().contains(q)).toList();
    return Scaffold(
        body: Column(children: [
      TextField(
          key: const Key('query'), onChanged: (v) => setState(() => query = v)),
      if (visible.isEmpty) const Text('검색 결과 없음'),
      for (final item in visible) Text(item, key: ValueKey('row-$item')),
    ]));
  }
}
