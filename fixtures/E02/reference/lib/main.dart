import 'package:flutter/material.dart';

void main() => runApp(CounterApp(controller: CounterController()));

class CounterController extends ChangeNotifier {
  int value = 0;
  void increment() {
    value++;
    notifyListeners();
  }

  void reset() {
    value = 0;
    notifyListeners();
  }
}

class CounterApp extends StatelessWidget {
  final CounterController controller;
  const CounterApp({super.key, required this.controller});
  @override
  Widget build(BuildContext context) => MaterialApp(
      home: Scaffold(
          body: AnimatedBuilder(
              animation: controller,
              builder: (_, _) => Column(children: [
                    Text('합계 ${controller.value}', key: const Key('total')),
                    Text('미리보기 ${controller.value}'),
                    TextButton(
                        key: const Key('add'),
                        onPressed: controller.increment,
                        child: const Text('추가')),
                    TextButton(
                        key: const Key('reset'),
                        onPressed: controller.reset,
                        child: const Text('초기화')),
                  ]))));
}
