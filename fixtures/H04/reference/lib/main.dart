import 'dart:convert';

class Preferences {
  final String theme;
  final double scale;
  const Preferences(this.theme, this.scale);
  String encode() => jsonEncode({'version': 2, 'theme': theme, 'scale': scale});
}

Preferences readPreferences(String data) {
  final m = jsonDecode(data);
  if (m is! Map) throw const FormatException('expected object');
  final version = m['version'];
  if (m.containsKey('version') && version != 1 && version != 2)
    throw const FormatException('unsupported version');
  final theme = m.containsKey('theme')
      ? m['theme']
      : (m.containsKey('mode') ? m['mode'] : 'system');
  final scale = m.containsKey('scale') ? m['scale'] : 1.0;
  if (theme is! String ||
      !['light', 'dark', 'system'].contains(theme) ||
      scale is! num ||
      !scale.isFinite ||
      scale < 0.5 ||
      scale > 2.0) throw const FormatException('invalid preferences');
  return Preferences(theme, scale.toDouble());
}
