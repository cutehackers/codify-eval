import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

void main() {
  testWidgets('inclusive boundaries', (t) async {
    for (final max in [0, 1, 4]) {
      await t.pumpWidget(MaterialApp(home: QuantityPage(maximum: max)));
      expect(t.widget<TextButton>(find.byKey(const Key('minus'))).onPressed,
          isNull);
      for (var i = 0; i < max; i++) {
        await t.tap(find.byKey(const Key('plus')));
        await t.pump();
      }
      expect(find.text('수량 $max'), findsOneWidget);
      expect(t.widget<TextButton>(find.byKey(const Key('plus'))).onPressed,
          isNull);
      for (var i = 0; i < max; i++) {
        await t.tap(find.byKey(const Key('minus')));
        await t.pump();
      }
      expect(find.text('수량 0'), findsOneWidget);
      await t.pumpWidget(const SizedBox());
    }
  });
}
