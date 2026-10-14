import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

void main() {
  test('legacy and current migration', () {
    final defaults = readPreferences('{}');
    expect(defaults.theme, 'system');
    expect(defaults.scale, 1.0);
    final old = readPreferences('{"version":1,"mode":"dark","scale":2}');
    expect(old.theme, 'dark');
    expect(old.scale, 2.0);
    final current = readPreferences(
        '{"version":2,"theme":"light","mode":"dark","scale":0.5}');
    expect(current.theme, 'light');
    expect(jsonDecode(current.encode()),
        {'version': 2, 'theme': 'light', 'scale': 0.5});
    expect(readPreferences(current.encode()).scale, 0.5);
  });
  test('invalid values rejected', () {
    for (final value in [
      '[]',
      '{"version":9}',
      '{"theme":"other"}',
      '{"scale":0.49}',
      '{"scale":2.01}',
      '{"scale":"1"}',
      '{"theme":4}',
      '{"theme":null}',
      '{"scale":null}',
      'broken'
    ]) {
      expect(() => readPreferences(value), throwsFormatException,
          reason: value);
    }
  });
}
