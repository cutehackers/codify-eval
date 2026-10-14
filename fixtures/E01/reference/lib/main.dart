import 'package:flutter/material.dart';

void main() =>
    runApp(const MaterialApp(home: ChoicePage(items: ['가', '나', '다'])));

class ChoicePage extends StatefulWidget {
  final List<String> items;
  const ChoicePage({super.key, required this.items});
  @override
  State<ChoicePage> createState() => _ChoicePageState();
}

class _ChoicePageState extends State<ChoicePage> {
  String? selected;
  @override
  Widget build(BuildContext context) => Scaffold(
          body: Column(children: [
        if (widget.items.isEmpty) const Text('항목 없음'),
        for (var i = 0; i < widget.items.length; i++)
          TextButton(
              key: ValueKey('item-$i'),
              onPressed: () {
                setState(() => selected = widget.items[i]);
              },
              child: Text(widget.items[i])),
        Text('선택: ${selected ?? "없음"}', key: const Key('selected')),
      ]));
}
