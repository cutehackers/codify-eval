import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

void main() {
  testWidgets('shared state updates and recreation', (t) async {
    final c = CounterController();
    await t.pumpWidget(CounterApp(controller: c));
    await t.tap(find.byKey(const Key('add')));
    await t.pump();
    expect(find.text('합계 1'), findsOneWidget);
    expect(find.text('미리보기 1'), findsOneWidget);
    c.increment();
    await t.pump();
    expect(find.text('합계 2'), findsOneWidget);
    await t.pumpWidget(const SizedBox());
    await t.pumpWidget(CounterApp(controller: c));
    expect(find.text('미리보기 2'), findsOneWidget);
    await t.tap(find.byKey(const Key('reset')));
    await t.pump();
    expect(find.text('합계 0'), findsOneWidget);
    expect(find.text('미리보기 0'), findsOneWidget);
    c.dispose();
  });
}
