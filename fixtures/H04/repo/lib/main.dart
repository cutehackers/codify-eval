import 'dart:convert';

class Preferences {
  final String theme;
  final double scale;
  const Preferences(this.theme, this.scale);
  String encode() => jsonEncode({'version': 2, 'theme': theme, 'scale': scale});
}

Preferences readPreferences(String data) {
  final m = jsonDecode(data) as Map<String, dynamic>;
  return Preferences(m['theme'] as String, (m['scale'] as num).toDouble());
}
