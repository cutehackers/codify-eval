import 'models.dart';

SearchPlan planSearchImport(ImportData data, SearchSnapshot snapshot) {
  final effects = <SavedSearch>[]; final report = <Map<String,Object>>[];
  for (final row in data.rows) {
    final old = snapshot.records[row.id];
    final action = old == null ? 'inserted' : old.title == row.title && old.expression == row.expression ? 'unchanged' : 'updated';
    if (action != 'unchanged') {
      effects.add(SavedSearch(data.workspaceId, row.id, row.title, row.expression, old?.createdAt ?? 'imported'));
    }
    report.add({'id': row.id, 'action': action});
  }
  return SearchPlan(effects, report.reversed.toList());
}
