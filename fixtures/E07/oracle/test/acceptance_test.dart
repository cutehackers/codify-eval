import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

void main() {
  test('legacy migration and current roundtrip', () {
    final values = decodeTasks(
        '[{"name":"옛 기록"},{"schema":1,"name":"이전","done":true},{"schema":2,"title":"새 기록","name":"무시","done":false}]');
    expect(values.map((v) => v.title), ['옛 기록', '이전', '새 기록']);
    expect(values.map((v) => v.done), [false, true, false]);
    final encoded = jsonDecode(encodeTasks(values)) as List;
    expect(encoded.first, {'schema': 2, 'title': '옛 기록', 'done': false});
    expect(decodeTasks(encodeTasks(values)).length, 3);
  });
  test('invalid shape uses stable error type', () {
    for (final input in [
      '{}',
      '[4]',
      '[{"name":4}]',
      '[{"title":"x","done":"yes"}]',
      '[{"schema":3,"title":"x"}]',
      '[{"title":null,"name":"x"}]',
      '[{"title":"x","done":null}]',
      'broken'
    ]) {
      expect(() => decodeTasks(input), throwsFormatException, reason: input);
    }
  });
}
