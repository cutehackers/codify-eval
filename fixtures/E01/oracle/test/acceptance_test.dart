import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

void main() {
  testWidgets('last and singleton are selectable', (t) async {
    for (final items in <List<String>>[
      ['끝'],
      ['첫', '중간', '끝']
    ]) {
      await t.pumpWidget(MaterialApp(home: ChoicePage(items: items)));
      await t.tap(find.byKey(ValueKey('item-${items.length - 1}')));
      await t.pump();
      expect(find.text('선택: 끝'), findsOneWidget);
      await t.pumpWidget(const SizedBox());
    }
  });
  testWidgets('empty list has explicit state', (t) async {
    await t.pumpWidget(const MaterialApp(home: ChoicePage(items: [])));
    expect(find.text('항목 없음'), findsOneWidget);
    expect(t.takeException(), isNull);
  });
}
