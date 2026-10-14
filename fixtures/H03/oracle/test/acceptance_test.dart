import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';
import 'dart:async';

class SequenceTransport implements StatusTransport {
  int calls = 0;
  final pending = Completer<String>();
  @override
  Future<String> request() async {
    calls++;
    if (calls == 1) return '{"status":null}';
    return pending.future;
  }
}

class ValueTransport implements StatusTransport {
  final String value;
  ValueTransport(this.value);
  @override
  Future<String> request() async => value;
}

void main() {
  test('adapter shape validation', () async {
    for (final value in ['[]', '{"status":2}', '{"status":"  "}', '{}']) {
      await expectLater(
          StatusAdapter(ValueTransport(value)).fetch(), throwsFormatException);
    }
  });
  testWidgets('malformed then recovered', (t) async {
    final service = SequenceTransport();
    await t.pumpWidget(
        MaterialApp(home: StatusPage(adapter: StatusAdapter(service))));
    await t.pump();
    expect(find.text('상태 확인 실패'), findsOneWidget);
    await t.tap(find.byKey(const Key('refresh')));
    await t.pump();
    expect(find.text('확인 중'), findsOneWidget);
    expect(t.widget<TextButton>(find.byKey(const Key('refresh'))).onPressed,
        isNull);
    service.pending.complete('{"status":"  정상  "}');
    await t.pump();
    expect(find.text('  정상  '), findsOneWidget);
    expect(service.calls, 2);
  });
}
