import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';
import 'dart:async';

class FailingStore implements LocalStore {
  @override
  Future<String?> read() async => throw StateError('read');
  @override
  Future<void> write(String value) async => throw StateError('write');
}

class DelayedStore extends MemoryStore {
  final pending = Completer<void>();
  @override
  Future<void> write(String value) async {
    await pending.future;
    super.write(value);
  }
}

void main() {
  testWidgets('save reload preserves exact input', (t) async {
    final s = MemoryStore();
    await t.pumpWidget(MaterialApp(home: DraftPage(store: s)));
    await t.pump();
    await t.enterText(find.byKey(const Key('draft')), '  원문\n둘째 줄  ');
    await t.tap(find.byKey(const Key('save')));
    await t.pump();
    expect(s.value, '  원문\n둘째 줄  ');
    await t.pumpWidget(const SizedBox());
    await t.pumpWidget(MaterialApp(home: DraftPage(store: s)));
    await t.pump();
    expect(t.widget<TextField>(find.byKey(const Key('draft'))).controller!.text,
        s.value);
  });
  testWidgets('errors and deferred success', (t) async {
    await t.pumpWidget(MaterialApp(home: DraftPage(store: FailingStore())));
    await t.pump();
    expect(find.text('불러오기 실패'), findsOneWidget);
    await t.tap(find.byKey(const Key('save')));
    await t.pump();
    expect(find.text('저장 실패'), findsOneWidget);
    await t.pumpWidget(const SizedBox());
    final s = DelayedStore();
    await t.pumpWidget(MaterialApp(home: DraftPage(store: s)));
    await t.pump();
    await t.tap(find.byKey(const Key('save')));
    await t.pump();
    expect(find.text('저장됨'), findsNothing);
    s.pending.complete();
    await t.pump();
    expect(find.text('저장됨'), findsOneWidget);
  });
}
