import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';
import 'dart:async';

void main() {
  testWidgets('validation failure retry pending', (t) async {
    int calls = 0;
    String? received;
    Completer<void>? pending;
    await t.pumpWidget(MaterialApp(home: NameForm(save: (name) async {
      calls++;
      received = name;
      if (calls == 1) throw StateError('disk');
      pending = Completer<void>();
      await pending!.future;
    })));
    await t.enterText(find.byKey(const Key('name')), '  ');
    await t.tap(find.byKey(const Key('submit')));
    await t.pump();
    expect(calls, 0);
    expect(find.text('이름을 입력하세요'), findsOneWidget);
    await t.enterText(find.byKey(const Key('name')), '  민수  ');
    await t.tap(find.byKey(const Key('submit')));
    await t.pump();
    expect(received, '민수');
    expect(find.text('저장 실패. 다시 시도하세요'), findsOneWidget);
    await t.tap(find.byKey(const Key('submit')));
    await t.pump();
    expect(find.text('저장 중'), findsOneWidget);
    expect(t.widget<TextButton>(find.byKey(const Key('submit'))).onPressed,
        isNull);
    pending!.complete();
    await t.pump();
    expect(find.text('저장 완료'), findsOneWidget);
    await t.tap(find.byKey(const Key('submit')));
    await t.pump();
    await t.pumpWidget(const SizedBox());
    pending!.complete();
    await t.pump();
    expect(t.takeException(), isNull);
  });
}
