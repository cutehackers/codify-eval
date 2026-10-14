import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

void main() {
  testWidgets('filter clear empty state', (t) async {
    final items = ['Apple', 'Pineapple', 'Pear'];
    await t.pumpWidget(MaterialApp(home: CatalogPage(items: items)));
    await t.enterText(find.byKey(const Key('query')), '  APPLE  ');
    await t.pump();
    expect(find.byKey(const ValueKey('row-Apple')), findsOneWidget);
    expect(find.byKey(const ValueKey('row-Pineapple')), findsOneWidget);
    expect(find.byKey(const ValueKey('row-Pear')), findsNothing);
    await t.enterText(find.byKey(const Key('query')), 'zzz');
    await t.pump();
    expect(find.text('검색 결과 없음'), findsOneWidget);
    await t.enterText(find.byKey(const Key('query')), '');
    await t.pump();
    expect(find.byKey(const ValueKey('row-Pear')), findsOneWidget);
    expect(items, ['Apple', 'Pineapple', 'Pear']);
  });
}
