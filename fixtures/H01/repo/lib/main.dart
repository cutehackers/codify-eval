import 'package:flutter/material.dart';

void main() => runApp(const MaterialApp(home: QuantityPage(maximum: 5)));

class QuantityPage extends StatefulWidget {
  final int maximum;
  const QuantityPage({super.key, required this.maximum});
  @override
  State<QuantityPage> createState() => _QuantityPageState();
}

class _QuantityPageState extends State<QuantityPage> {
  int count = 0;
  @override
  Widget build(BuildContext context) => Scaffold(
          body: Column(children: [
        Text('수량 $count'),
        TextButton(
            key: const Key('minus'),
            onPressed: () => setState(() => count--),
            child: const Text('감소')),
        TextButton(
            key: const Key('plus'),
            onPressed: () => setState(() => count++),
            child: const Text('증가'))
      ]));
}
