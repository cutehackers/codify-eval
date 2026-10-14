import 'dart:convert';
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
