import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

void main() {
  testWidgets('sku quantities total across modules', (t) async {
    final b = Basket(const [Product('a', '노트', 125), Product('b', '노트', 250)]);
    await t.pumpWidget(ShopApp(basket: b));
    for (final sku in ['a', 'a', 'b']) {
      await t.tap(find.byKey(ValueKey('add-$sku')));
      await t.pump();
    }
    expect(b.counts, {'a': 2, 'b': 1});
    expect(find.text('노트 x2'), findsOneWidget);
    expect(find.text('노트 x1'), findsOneWidget);
    expect(find.text('총액 500 센트'), findsOneWidget);
    b.add('missing');
    await t.pump();
    expect(b.totalCents, 500);
    await t.pumpWidget(const SizedBox());
    await t.pumpWidget(ShopApp(basket: b));
    expect(find.text('총액 500 센트'), findsOneWidget);
  });
}
