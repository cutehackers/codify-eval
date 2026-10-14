import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';
import 'dart:async';

class ScriptService implements RemoteService {
  int calls = 0;
  final pending = Completer<List<String>>();
  @override
  Future<List<String>> fetch() async {
    calls++;
    if (calls == 1) throw StateError('offline');
    if (calls == 2) return pending.future;
    return [];
  }
}

void main() {
  testWidgets('failure recovery and empty', (t) async {
    final service = ScriptService();
    await t
        .pumpWidget(MaterialApp(home: NewsPage(adapter: NewsAdapter(service))));
    await t.pump();
    expect(find.text('소식을 불러오지 못했습니다'), findsOneWidget);
    await t.tap(find.byKey(const Key('retry')));
    await t.pump();
    expect(find.text('불러오는 중'), findsOneWidget);
    expect(
        t.widget<TextButton>(find.byKey(const Key('retry'))).onPressed, isNull);
    expect(service.calls, 2);
    service.pending.complete(['복구 소식', '두 번째']);
    await t.pump();
    expect(find.text('복구 소식'), findsOneWidget);
    expect(find.text('소식을 불러오지 못했습니다'), findsNothing);
    await t.tap(find.byKey(const Key('retry')));
    await t.pump();
    expect(find.text('소식 없음'), findsOneWidget);
  });
}
