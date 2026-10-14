import 'dart:convert';
import 'models.dart';

ImportData? decodeSearchImport(Object? value) {
  if (value is! Map || value.keys.any((k) => k is! String)) return null;
  final version = value['version'];
  if (version is! int || (version != 1 && version != 2)) return null;
  final collection = version == 1 ? 'searches' : 'items';
  if (value.length != 3 || !value.containsKey('workspaceId') || !value.containsKey(collection)) return null;
  final workspace = value['workspaceId']; final rows = value[collection];
  if (!validId(workspace) || rows is! List || rows.length > 100) return null;
  final ids = <String>{}; final result = <PortableSearch>[];
  for (final row in rows) {
    if (row is! Map || row.length != 3 || !row.containsKey('id')) return null;
    final titleKey = version == 1 ? 'label' : 'title';
    final expressionKey = version == 1 ? 'query' : 'expression';
    if (!row.containsKey(titleKey) || !row.containsKey(expressionKey)) return null;
    final id = row['id'], title = row[titleKey], expression = row[expressionKey];
    if (!validId(id) || title is! String || title.isEmpty || title.length > 80 ||
        expression is! String || expression.isEmpty || expression.length > 2000 || !ids.add(id as String)) return null;
    result.add(PortableSearch(id, title, version == 1 ? title : expression));
  }
  return ImportData(workspace as String, result);
}
String encodeSearchExport(ImportData data) => '${jsonEncode({
  'version': 2, 'workspaceId': data.workspaceId,
  'items': data.rows.map((r) => {'id': r.id, 'title': r.title, 'expression': r.expression}).toList(),
})}\n';
