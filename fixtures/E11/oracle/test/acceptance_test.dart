import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

void main() {
  testWidgets('toggle and existing banner', (t) async {
    await t.pumpWidget(const TodoPage());
    expect(find.text('사용자가 작성한 문구: 오늘도 꾸준히'), findsOneWidget);
    await t.tap(find.byKey(const Key('done')));
    await t.pump();
    expect(find.text('완료'), findsOneWidget);
    await t.tap(find.byKey(const Key('done')));
    await t.pump();
    expect(find.text('진행 중'), findsOneWidget);
  });
}
