import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

void main() {
  testWidgets('id based navigation and return', (t) async {
    final repo = EntryRepository(
        const [Entry(42, '같은 제목', '첫 본문'), Entry(91, '같은 제목', '둘째 본문')]);
    await t.pumpWidget(EntryApp(repository: repo));
    await t.tap(find.byKey(const ValueKey('entry-91')));
    await t.pumpAndSettle();
    expect(find.text('둘째 본문'), findsOneWidget);
    expect(find.text('첫 본문'), findsNothing);
    await t.pageBack();
    await t.pumpAndSettle();
    expect(find.byKey(const ValueKey('entry-42')), findsOneWidget);
  });
  testWidgets('missing record', (t) async {
    await t.pumpWidget(MaterialApp(
        home: EntryDetail(repository: EntryRepository([]), id: 999)));
    expect(find.text('찾을 수 없음'), findsOneWidget);
    expect(find.text('기록이 없습니다'), findsOneWidget);
  });
}
