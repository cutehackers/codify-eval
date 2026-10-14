import json, hashlib
from pathlib import Path
root=Path('improvement_cases/fresh-question-cohort-v2')
proposal=json.loads(Path('improvement_cases/fresh-question-design-v1/proposal-v2.json').read_text())
def write(base,path,text):
 p=base/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text.rstrip()+'\n')
pubspec='''name: question_fixture
publish_to: none
environment:
  sdk: '>=3.3.0 <4.0.0'
dependencies:
  flutter:
    sdk: flutter
dev_dependencies:
  flutter_test:
    sdk: flutter
'''
stock_models='''class Row {
  final String skuId;
  final int quantity;
  const Row(this.skuId, this.quantity);
}
class Shortage {
  final String skuId;
  final int requested;
  final int available;
  const Shortage(this.skuId, this.requested, this.available);
}
class Outcome {
  final String code;
  final List<Row> reserved;
  final List<Shortage> shortages;
  const Outcome(this.code, {this.reserved = const [], this.shortages = const []});
}
class Request {
  final String warehouseId;
  final String orderId;
  final List<Row> rows;
  const Request(this.warehouseId, this.orderId, this.rows);
}
class Identity {
  final String tenantId;
  final String operatorId;
  const Identity(this.tenantId, this.operatorId);
}
class Recorded {
  final String signature;
  final Outcome outcome;
  const Recorded(this.signature, this.outcome);
}
class Warehouse {
  final String tenantId;
  Map<String, int> stock;
  Map<String, Recorded> orders;
  Warehouse(this.tenantId, Map<String, int> stock)
      : stock = Map.of(stock), orders = {};
}
class MemoryStore {
  final Map<String, Warehouse> warehouses;
  bool failCommit = false;
  int commits = 0;
  int stockReads = 0;
  MemoryStore(this.warehouses);
  bool accessible(String id, String tenant) => warehouses[id]?.tenantId == tenant;
  Map<String, int> snapshot(String id) {
    stockReads++;
    return Map.of(warehouses[id]!.stock);
  }
  Recorded? recorded(String id, String order) => warehouses[id]!.orders[order];
  void commit(String id, String order, Recorded record, Map<String, int> next) {
    if (failCommit) throw StateError('SECRET storage disk detail');
    warehouses[id]!.stock = Map.of(next);
    warehouses[id]!.orders = {...warehouses[id]!.orders, order: record};
    commits++;
  }
}
'''
stock_ref='''import 'dart:convert';
import 'models.dart';
class ReservationService {
  final MemoryStore store;
  final Identity identity;
  ReservationService(this.store, this.identity);
  Outcome reserve(Request request) {
    if (!store.accessible(request.warehouseId, identity.tenantId)) {
      return const Outcome('not_found');
    }
    final ids = <String>{};
    if (request.orderId.trim().isEmpty || request.rows.isEmpty ||
        request.rows.any((r) => r.skuId.trim().isEmpty || r.quantity <= 0 || !ids.add(r.skuId))) {
      return const Outcome('invalid_request');
    }
    final stock = store.snapshot(request.warehouseId);
    if (request.rows.any((r) => !stock.containsKey(r.skuId))) {
      return const Outcome('invalid_request');
    }
    final signature = jsonEncode(request.rows.map((r) => [r.skuId, r.quantity]).toList()
      ..sort((a, b) => (a[0] as String).compareTo(b[0] as String)));
    final previous = store.recorded(request.warehouseId, request.orderId);
    if (previous != null) {
      return previous.signature == signature ? previous.outcome : const Outcome('conflict');
    }
    final shortages = request.rows.where((r) => stock[r.skuId]! < r.quantity)
      .map((r) => Shortage(r.skuId, r.quantity, stock[r.skuId]!)).toList();
    final reserved = shortages.isEmpty ? List<Row>.of(request.rows) : <Row>[];
    final next = Map<String, int>.of(stock);
    for (final row in reserved) { next[row.skuId] = next[row.skuId]! - row.quantity; }
    final outcome = Outcome('ok', reserved: reserved, shortages: shortages);
    try {
      store.commit(request.warehouseId, request.orderId, Recorded(signature, outcome), next);
      return outcome;
    } catch (_) { return const Outcome('storage_failure'); }
  }
}
'''
stock_stub='''import 'models.dart';
class ReservationService {
  final MemoryStore store;
  final Identity identity;
  ReservationService(this.store, this.identity);
  Outcome reserve(Request request) => throw UnimplementedError();
}
'''
stock_tests='''import 'package:flutter_test/flutter_test.dart';
import 'package:question_fixture/models.dart';
import 'package:question_fixture/implementation.dart';
MemoryStore fixture() => MemoryStore({
  'w': Warehouse('t', {'A': 7, 'B': 1, 'C': 8}),
  'other': Warehouse('other_t', {'A': 99}),
});
ReservationService service(MemoryStore s) => ReservationService(s, const Identity('t', 'operator'));
void main() {
  test('P01 full allocation and unrelated stock', () {
    final s = fixture(); final r = service(s).reserve(const Request('w', 'o', [Row('A', 3)]));
    expect(r.code, 'ok'); expect(r.reserved.map((r) => [r.skuId, r.quantity]).toList(), [['A', 3]]);
    expect(r.shortages, isEmpty); expect(s.warehouses['w']!.stock, {'A': 4, 'B': 1, 'C': 8});
    expect(s.warehouses['other']!.stock['A'], 99);
  });
  test('P02 inaccessible warehouse before reads or validation', () {
    final s = fixture(); final r = service(s).reserve(const Request('other', '', []));
    expect(r.code, 'not_found'); expect(r.reserved, isEmpty); expect(r.shortages, isEmpty);
    expect(s.stockReads, 0); expect(s.commits, 0); expect(s.warehouses['other']!.stock['A'], 99);
  });
  test('P03 missing warehouse', () {
    final s = fixture(); expect(service(s).reserve(const Request('missing', 'o', [Row('A', 1)])).code, 'not_found');
    expect(s.stockReads, 0); expect(s.commits, 0);
  });
  test('P04 invalid request shapes', () {
    for (final r in [const Request('w', ' ', [Row('A', 1)]), const Request('w', 'o', []),
      const Request('w', 'o', [Row(' ', 1)]), const Request('w', 'o', [Row('A', 0)]),
      const Request('w', 'o', [Row('A', -1)]), const Request('w', 'o', [Row('A', 1), Row('A', 2)])]) {
      final s = fixture(); expect(service(s).reserve(r).code, 'invalid_request');
      expect(s.stockReads, 0); expect(s.commits, 0);
    }
  });
  test('P05 unknown SKU makes no writes', () {
    final s = fixture(); expect(service(s).reserve(const Request('w', 'o', [Row('A', 1), Row('missing', 1)])).code, 'invalid_request');
    expect(s.commits, 0); expect(s.warehouses['w']!.stock['A'], 7);
  });
  test('P06 identical retry is idempotent including row order', () {
    final s = fixture(); final api = service(s);
    api.reserve(const Request('w', 'o', [Row('A', 2), Row('C', 1)]));
    final r = api.reserve(const Request('w', 'o', [Row('C', 1), Row('A', 2)]));
    expect(r.code, 'ok'); expect(s.commits, 1); expect(s.warehouses['w']!.stock['A'], 5);
    expect(s.warehouses['w']!.stock['C'], 7);
  });
  test('P07 changed retry conflicts', () {
    final s = fixture(); final api = service(s); api.reserve(const Request('w', 'o', [Row('A', 2)]));
    final r = api.reserve(const Request('w', 'o', [Row('A', 3)]));
    expect(r.code, 'conflict'); expect(s.commits, 1); expect(s.warehouses['w']!.stock['A'], 5);
  });
  test('P08 commit failure rolls back and returns safe error', () {
    final s = fixture()..failCommit = true;
    final r = service(s).reserve(const Request('w', 'o', [Row('A', 2)]));
    expect(r.code, 'storage_failure'); expect(r.reserved, isEmpty); expect(r.shortages, isEmpty);
    expect(s.warehouses['w']!.stock['A'], 7); expect(s.warehouses['w']!.orders, isEmpty); expect(s.commits, 0);
  });
}
'''
stock_private='''import 'package:flutter_test/flutter_test.dart';
import 'package:question_fixture/models.dart';
import 'package:question_fixture/implementation.dart';
void main() {
  test('A01 mixed shortage consumes no stock', () {
    final s = MemoryStore({'w': Warehouse('t', {'A': 7, 'B': 1, 'C': 0})});
    final r = ReservationService(s, const Identity('t', 'op')).reserve(const Request('w', 'o', [Row('A', 3), Row('B', 2), Row('C', 4)]));
    expect(r.code, 'ok'); expect(r.reserved, isEmpty);
    expect(r.shortages.map((x) => [x.skuId, x.requested, x.available]).toList(), [['B', 2, 1], ['C', 4, 0]]);
    expect(s.warehouses['w']!.stock, {'A': 7, 'B': 1, 'C': 0}); expect(s.commits, 1);
  });
  test('A02 shortage outcome persists across replenishment and changed retry conflicts', () {
    final s = MemoryStore({'w': Warehouse('t', {'A': 7, 'B': 1})});
    final api = ReservationService(s, const Identity('t', 'op'));
    const q = Request('w', 'o', [Row('A', 3), Row('B', 2)]); api.reserve(q);
    s.warehouses['w']!.stock['B'] = 20;
    final retry = api.reserve(q); expect(retry.reserved, isEmpty);
    expect(retry.shortages.single.available, 1); expect(s.commits, 1); expect(s.warehouses['w']!.stock['A'], 7);
    expect(s.warehouses['w']!.stock['B'], 20);
    expect(api.reserve(const Request('w', 'o', [Row('A', 1)])).code, 'conflict');
  });
  test('A03 shortage record write failure rolls back', () {
    final s = MemoryStore({'w': Warehouse('t', {'A': 7, 'B': 1})})..failCommit = true;
    final r = ReservationService(s, const Identity('t', 'op')).reserve(const Request('w', 'o', [Row('A', 3), Row('B', 2)]));
    expect(r.code, 'storage_failure'); expect(s.warehouses['w']!.orders, isEmpty);
    expect(s.warehouses['w']!.stock, {'A': 7, 'B': 1}); expect(s.commits, 0);
  });
}
'''
import_models='''const maxNotes = 20;
const maxTitleLength = 80;
const maxBodyLength = 1000;
class Note {
  final String id;
  final String title;
  final String body;
  final String metadata;
  const Note(this.id, this.title, this.body, {this.metadata = 'imported'});
}
class ImportResult {
  final String code;
  final List<String> insertedIds;
  final List<String> updatedIds;
  final List<String> unchangedIds;
  const ImportResult(this.code, {this.insertedIds = const [], this.updatedIds = const [], this.unchangedIds = const []});
}
class Identity {
  final String userId;
  const Identity(this.userId);
}
class Workspace {
  final Set<String> editors;
  Map<String, Note> notes;
  Workspace(this.editors, Map<String, Note> notes) : notes = Map.of(notes);
}
class MemoryStore {
  final Map<String, Workspace> workspaces;
  bool failCommit = false;
  int reads = 0;
  int commits = 0;
  int writes = 0;
  MemoryStore(this.workspaces);
  bool canEdit(String id, String user) => workspaces[id]?.editors.contains(user) ?? false;
  Map<String, Note> snapshot(String id) { reads++; return Map.of(workspaces[id]!.notes); }
  void apply(String id, List<Note> changes) {
    if (failCommit) throw StateError('SECRET storage path');
    workspaces[id]!.notes = {...workspaces[id]!.notes, for(final n in changes) n.id: n};
    writes += changes.length;
    commits++;
  }
}
'''
import_ref='''import 'dart:convert';
import 'models.dart';
class NoteImportService {
  final MemoryStore store;
  final Identity identity;
  NoteImportService(this.store, this.identity);
  ImportResult importBackup(String targetWorkspaceId, String backupJson) {
    if (!store.canEdit(targetWorkspaceId, identity.userId)) return const ImportResult('access_denied');
    dynamic data;
    try { data = jsonDecode(backupJson); } catch (_) { return const ImportResult('invalid_backup'); }
    if (data is! Map<String, dynamic> || data.length != 3 ||
        !data.containsKey('version') || !data.containsKey('workspaceId') || !data.containsKey('notes') ||
        data['version'] is! int || data['version'] != 1 || data['workspaceId'] is! String ||
        data['workspaceId'] != targetWorkspaceId || data['notes'] is! List ||
        (data['notes'] as List).length > maxNotes) return const ImportResult('invalid_backup');
    final incoming = <Note>[];
    final ids = <String>{};
    for (final item in data['notes'] as List) {
      if (item is! Map<String, dynamic> || item.length != 3 ||
          !item.containsKey('id') || !item.containsKey('title') || !item.containsKey('body') ||
          item['id'] is! String || item['title'] is! String || item['body'] is! String) {
        return const ImportResult('invalid_backup');
      }
      final id = item['id'] as String; final title = item['title'] as String; final body = item['body'] as String;
      if (id.trim().isEmpty || !ids.add(id) || title.length > maxTitleLength || body.length > maxBodyLength) {
        return const ImportResult('invalid_backup');
      }
      incoming.add(Note(id, title, body));
    }
    final existing = store.snapshot(targetWorkspaceId);
    final changes = <Note>[]; final inserted = <String>[]; final updated = <String>[]; final unchanged = <String>[];
    for (final note in incoming) {
      final old = existing[note.id];
      if (old == null) { changes.add(note); inserted.add(note.id); }
      else { unchanged.add(note.id); }
    }
    if (changes.isEmpty) return ImportResult('ok', insertedIds: inserted, updatedIds: updated, unchangedIds: unchanged);
    try {
      store.apply(targetWorkspaceId, changes);
      return ImportResult('ok', insertedIds: inserted, updatedIds: updated, unchangedIds: unchanged);
    } catch (_) { return const ImportResult('storage_failure'); }
  }
}
'''
import_stub='''import 'models.dart';
class NoteImportService {
  final MemoryStore store;
  final Identity identity;
  NoteImportService(this.store, this.identity);
  ImportResult importBackup(String targetWorkspaceId, String backupJson) => throw UnimplementedError();
}
'''
import_tests='''import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:question_fixture/models.dart';
import 'package:question_fixture/implementation.dart';
MemoryStore fixture() => MemoryStore({
  'w': Workspace({'u'}, {'n1': const Note('n1', 'Plan', 'Final', metadata: 'keep'), 'absent': const Note('absent', 'Other', 'Keep')}),
  'other': Workspace({'other_user'}, {'x': const Note('x', 'Private', 'Secret')}),
});
String backup(List<dynamic> notes, {String workspace='w'}) => jsonEncode({'version': 1, 'workspaceId': workspace, 'notes': notes});
Map<String, dynamic> note(String id, {String title='Title', String body='Body'}) => {'id': id, 'title': title, 'body': body};
NoteImportService service(MemoryStore s) => NoteImportService(s, const Identity('u'));
void main() {
  test('P01 new IDs and Unicode preserve content and order', () {
    final s = fixture(); final r = service(s).importBackup('w', backup([note('z', title:'메모 🌱', body:'줄1\\n줄2'), note('a')]));
    expect(r.code, 'ok'); expect(r.insertedIds, ['z', 'a']); expect(r.updatedIds, isEmpty); expect(r.unchangedIds, isEmpty);
    expect(s.workspaces['w']!.notes['z']!.title, '메모 🌱'); expect(s.workspaces['w']!.notes['z']!.body, '줄1\\n줄2');
    expect(s.workspaces['w']!.notes['absent']!.body, 'Keep'); expect(s.workspaces['other']!.notes['x']!.body, 'Secret');
  });
  test('P02 access denied precedes parsing and content reads', () {
    final s = fixture(); expect(service(s).importBackup('other', 'broken').code, 'access_denied');
    expect(s.reads, 0); expect(s.commits, 0); expect(s.writes, 0);
    expect(s.workspaces['other']!.notes['x']!.body, 'Secret');
  });
  test('P03 missing workspace denied', () {
    final s = fixture(); expect(service(s).importBackup('missing', backup([])).code, 'access_denied'); expect(s.reads, 0);
  });
  test('P04 workspace mismatch before reads', () {
    final s = fixture(); expect(service(s).importBackup('w', backup([note('x')], workspace:'other')).code, 'invalid_backup');
    expect(s.reads, 0); expect(s.commits, 0);
  });
  test('P05 malformed top-level schema rejects before reads', () {
    for (final raw in ['broken', '[]', '{}', jsonEncode({'version':2,'workspaceId':'w','notes':[]}),
      jsonEncode({'version':1.0,'workspaceId':'w','notes':[]}), jsonEncode({'version':1,'workspaceId':4,'notes':[]}),
      jsonEncode({'version':1,'workspaceId':'w','notes':{}}), jsonEncode({'version':1,'workspaceId':'w','notes':[],'extra':true})]) {
      final s = fixture(); expect(service(s).importBackup('w', raw).code, 'invalid_backup'); expect(s.reads, 0); expect(s.commits, 0);
    }
  });
  test('P06 malformed later note and duplicates reject whole backup', () {
    for (final notes in [[note('new'), {'id':'bad','title':'T'}], [note('new'), note('new')], [note(' ')],
      [note('x'), {'id':'y','title':'T','body':4}], [note('x'), {...note('y'), 'extra':true}]]) {
      final s=fixture(); expect(service(s).importBackup('w', backup(notes)).code, 'invalid_backup');
      expect(s.reads, 0); expect(s.commits, 0); expect(s.workspaces['w']!.notes.containsKey('new'), false);
    }
  });
  test('P07 published limits accept boundary and reject over-limit', () {
    final s=fixture(); final r=service(s).importBackup('w', backup(List.generate(maxNotes, (i)=>note('id$i', title:'t'*maxTitleLength, body:'b'*maxBodyLength))));
    expect(r.code,'ok'); expect(r.insertedIds.length,maxNotes);
    for(final notes in [List.generate(maxNotes+1,(i)=>note('id$i')), [note('x',title:'t'*(maxTitleLength+1))], [note('x',body:'b'*(maxBodyLength+1))]]) {
      final fresh=fixture(); expect(service(fresh).importBackup('w',backup(notes)).code,'invalid_backup'); expect(fresh.reads,0); expect(fresh.commits,0);
    }
  });
  test('P08 identical existing note remains unchanged without metadata rewrite', () {
    final s=fixture(); final r=service(s).importBackup('w',backup([note('n1',title:'Plan',body:'Final')]));
    expect(r.code,'ok'); expect(r.unchangedIds,['n1']); expect(r.insertedIds,isEmpty); expect(r.updatedIds,isEmpty);
    expect(s.writes,0); expect(s.workspaces['w']!.notes['n1']!.metadata,'keep');
  });
  test('P09 storage failure rolls back with safe result', () {
    final s=fixture()..failCommit=true; final r=service(s).importBackup('w',backup([note('new'),note('new2')]));
    expect(r.code,'storage_failure'); expect(r.insertedIds,isEmpty); expect(r.updatedIds,isEmpty); expect(r.unchangedIds,isEmpty);
    expect(s.workspaces['w']!.notes.keys, unorderedEquals(['n1','absent'])); expect(s.writes,0); expect(s.commits,0);
  });
  test('P10 empty backup is a successful no-op', () {
    final s=fixture(); final r=service(s).importBackup('w',backup([])); expect(r.code,'ok');
    expect(r.insertedIds,isEmpty); expect(r.updatedIds,isEmpty); expect(r.unchangedIds,isEmpty); expect(s.writes,0);
  });
}
'''
import_private='''import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:question_fixture/models.dart';
import 'package:question_fixture/implementation.dart';
void main() {
  test('A01 conflicting existing content preserved alongside insertion', () {
    final s=MemoryStore({'w':Workspace({'u'},{'n1':const Note('n1','Monday plan','Send final draft',metadata:'edited')})});
    final raw=jsonEncode({'version':1,'workspaceId':'w','notes':[
      {'id':'n1','title':'Monday plan','body':'Send first draft'}, {'id':'n2','title':'New','body':'Fresh'}]});
    final r=NoteImportService(s,const Identity('u')).importBackup('w',raw);
    expect(r.code,'ok'); expect(r.unchangedIds,['n1']); expect(r.insertedIds,['n2']); expect(r.updatedIds,isEmpty);
    expect(s.workspaces['w']!.notes['n1']!.body,'Send final draft'); expect(s.workspaces['w']!.notes['n1']!.metadata,'edited');
    expect(s.workspaces['w']!.notes['n2']!.body,'Fresh'); expect(s.writes,1);
  });
  test('A02 repeated conflict backup causes no rewrites', () {
    final s=MemoryStore({'w':Workspace({'u'},{'n1':const Note('n1','Current','Current',metadata:'edited')})});
    final raw=jsonEncode({'version':1,'workspaceId':'w','notes':[
      {'id':'n1','title':'Old','body':'Old'}, {'id':'n2','title':'New','body':'New'}]});
    final api=NoteImportService(s,const Identity('u')); api.importBackup('w',raw); final r=api.importBackup('w',raw);
    expect(r.unchangedIds,['n1','n2']); expect(r.insertedIds,isEmpty); expect(r.updatedIds,isEmpty);
    expect(s.writes,1); expect(s.workspaces['w']!.notes['n1']!.title,'Current');
  });
  test('A03 title-only and body-only conflicts both preserve existing', () {
    final s=MemoryStore({'w':Workspace({'u'},{'a':const Note('a','A','B',metadata:'m'), 'b':const Note('b','A','B',metadata:'m')})});
    final raw=jsonEncode({'version':1,'workspaceId':'w','notes':[
      {'id':'a','title':'Changed','body':'B'}, {'id':'b','title':'A','body':'Changed'}]});
    final r=NoteImportService(s,const Identity('u')).importBackup('w',raw);
    expect(r.unchangedIds,['a','b']); expect(r.updatedIds,isEmpty); expect(s.writes,0);
    expect(s.workspaces['w']!.notes['a']!.title,'A'); expect(s.workspaces['w']!.notes['b']!.body,'B');
    expect(s.workspaces['w']!.notes['a']!.metadata,'m');
  });
}
'''
for idx, caseid, models, ref, stub, tests, acceptance in [(0,'Q05',stock_models,stock_ref,stock_stub,stock_tests,stock_private),(1,'Q06',import_models,import_ref,import_stub,import_tests,import_private)]:
 base=root/caseid
 for path, text in [('repo/pubspec.yaml',pubspec),('repo/lib/models.dart',models),('repo/lib/implementation.dart',stub),('repo/test/contract_test.dart',tests),('private/reference.dart',ref),('private/acceptance_test.dart',acceptance),('private/fixed-reply.txt',proposal['tasks'][idx]['evaluator_only']['fixed_reply'])]: write(base,path,text)
