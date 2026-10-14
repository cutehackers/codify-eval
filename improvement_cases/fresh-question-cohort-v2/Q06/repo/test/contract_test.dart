import 'dart:convert';
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
    final s = fixture(); final r = service(s).importBackup('w', backup([note('z', title:'메모 🌱', body:'줄1\n줄2'), note('a')]));
    expect(r.code, 'ok'); expect(r.insertedIds, ['z', 'a']); expect(r.updatedIds, isEmpty); expect(r.unchangedIds, isEmpty);
    expect(s.workspaces['w']!.notes['z']!.title, '메모 🌱'); expect(s.workspaces['w']!.notes['z']!.body, '줄1\n줄2');
    expect(s.workspaces['w']!.notes['absent']!.body, 'Keep'); expect(s.workspaces['other']!.notes['x']!.body, 'Secret');
  });
  test('P02 access denied precedes parsing and content reads', () {
    final s = fixture(); expect(service(s).importBackup('other', backup([note('new')], workspace:'other')).code, 'access_denied');
    expect(service(s).importBackup('other', 'broken').code, 'access_denied');
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
