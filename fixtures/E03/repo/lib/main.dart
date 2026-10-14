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
    final visible = widget.items;
    return Scaffold(
        body: Column(children: [
      TextField(
          key: const Key('query'), onChanged: (v) => setState(() => query = v)),
      for (final item in visible) Text(item, key: ValueKey('row-$item')),
    ]));
  }
}
