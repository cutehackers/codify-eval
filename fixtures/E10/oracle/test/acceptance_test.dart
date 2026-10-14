import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

void main() {
  testWidgets('chosen replacement semantics', (t) async {
    final c = ShelfController();
    await t.pumpWidget(ShelfApp(controller: c));
    for (final data in [
      ['A', '처음'],
      ['B', '둘째'],
      ['A', '개정']
    ]) {
      await t.enterText(find.byKey(const Key('isbn')), data[0]);
      await t.enterText(find.byKey(const Key('title')), data[1]);
      await t.tap(find.byKey(const Key('add')));
      await t.pump();
    }
    expect(c.books.map((b) => b.isbn), ['A', 'B']);
    expect(c.books.map((b) => b.title), ['개정', '둘째']);
    expect(find.text('A: 개정'), findsOneWidget);
    expect(find.text('A: 처음'), findsNothing);
  });
}
