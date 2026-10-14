import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:o01_fixture/models.dart';
import 'package:o01_fixture/search_codec.dart';
import 'package:o01_fixture/search_import_service.dart';

String payload(List<Map<String,Object>> rows, {int version=2,String workspace='w'}) => jsonEncode({
 'version':version,'workspaceId':workspace,version==1?'searches':'items':rows});
Map<String,Object> row(String id,{String title='Title',String expression='query'}) => {'id':id,'title':title,'expression':expression};
Outcome run(MemorySearchStore store,String text,{Object? revision=0,Object? target='w',bool allowed=true}) => importSavedSearches(
 targetWorkspaceId:target,expectedRevision:revision,jsonText:text,permissions:PermissionProvider(allowed),store:store);
void failure(Outcome result,String code) { expect(result.code,code);expect(result.revision,isNull);expect(result.report,isEmpty);expect(result.message,Outcome.messages[code]); }

void main() {
  test("R01 denied valid import prevents reads despite storage faults", () {
final s=MemorySearchStore()..throwLoad=true;final p=PermissionProvider(false);final r=importSavedSearches(targetWorkspaceId:'w',expectedRevision:0,jsonText:payload([row('a')]),permissions:p,store:s);failure(r,'forbidden');expect(p.targets,['w']);expect(s.loads,isEmpty);
  });
  test("R02 foreign unlisted snapshot record rejects entire import before revision", () {
final s=MemorySearchStore();s.data['w']=SearchSnapshot(7,{'unlisted':const SavedSearch('alien','unlisted','secret','q','t')});failure(run(s,payload([]),revision:0),'forbidden');expect(s.commits,0);
  });
  test("R03 full limit ID title expression accepted boundary plus over rejected", () {
final rows=List.generate(100,(i)=>row('id$i',title:'t'*80,expression:'q'*2000));final s=MemorySearchStore();expect(run(s,payload(rows)).report.length,100);expect(s.commits,1);for(final r in [row('a',title:''),row('a',expression:''),row('a',expression:'q'*2001)]){failure(run(MemorySearchStore(),payload([r])),'invalid_import');}
  });
  test("R04 metadata injection and noninteger revision rejected before reads", () {
final s=MemorySearchStore();for(final rev in [-1,1.0,'0',null]){failure(run(s,payload([]),revision:rev),'invalid_import');}failure(run(s,payload([{'id':'a','title':'t','expression':'q','createdAt':'t'}])),'invalid_import');expect(s.loads,isEmpty);
  });
  test("R05 escaped duplicate JSON keys rejected protected decoder", () {
final s=MemorySearchStore();failure(run(s,r'{"version":2,"workspaceId":"w","items":[{"id":"a","title":"t","expression":"q","\u0069d":"b"}]}'),'invalid_import');expect(s.loads,isEmpty);
  });
  test("R06 rollback mixed effects retains exact old snapshot", () {
final s=MemorySearchStore();final old=SearchSnapshot(5,{'a':const SavedSearch('w','a','Old','old','stamp'),'b':const SavedSearch('w','b','Title','query','stampB')});s.data['w']=old;s.throwCommit=true;failure(run(s,payload([row('a'),row('b'),row('c')]),revision:5),'storage_failure');expect(identical(s.data['w'],old),isTrue);expect(s.commits,1);
  });
  test("R07 v1 imported expression title retain different text", () {
final s=MemorySearchStore();expect(run(s,payload([{'id':'one','label':'Label','query':'title != label'}],version:1)).code,'applied');expect(s.data['w']!.records['one']!.expression,'title != label');
  });
  test("R08 exact serialized escapes Unicode slash CR LF final single LF", () {
final data=ImportData('w',[const PortableSearch('x','"한글"','a/b\r\n\t\\')]);final expected=jsonEncode({'version':2,'workspaceId':'w','items':[{'id':'x','title':'"한글"','expression':'a/b\r\n\t\\'}]})+'\n';expect(encodeSearchExport(data),expected);final decoded=decodeSearchImport(decodePortableJson(expected))!;expect(decoded.rows.single.expression,data.rows.single.expression);
  });
  test("R09 report mixed ordering all once and no-op metadata untouched", () {
final s=MemorySearchStore();const old=SavedSearch('w','z','Title','query','original');s.data['w']=SearchSnapshot(1,{'z':old,'m':const SavedSearch('w','m','old','q','meta')});final r=run(s,payload([row('n'),row('z'),row('m')]),revision:1);expect(r.report,[{'id':'n','action':'inserted'},{'id':'z','action':'unchanged'},{'id':'m','action':'updated'}]);expect(identical(s.data['w']!.records['z'],old),isTrue);
  });
  test("R10 stale mutation blocks transaction and reports", () {
final s=MemorySearchStore();s.data['w']=SearchSnapshot(9,{});failure(run(s,payload([row('a')]),revision:8),'conflict');expect(s.commits,0);expect(s.data['w']!.records,isEmpty);
  });
  test("R11 valid target access identity excludes payload workspace", () {
final s=MemorySearchStore();final p=PermissionProvider(true);failure(importSavedSearches(targetWorkspaceId:'w',expectedRevision:0,jsonText:payload([],workspace:'x'),permissions:p,store:s),'invalid_import');expect(p.targets,['w']);expect(s.loads,isEmpty);
  });
  test("R12 unknown row and top schema prevent reads and failure detail leakage", () {
final s=MemorySearchStore();for(final text in ['[]','null',payload([{'id':'a','title':'t','expression':false}]),'{"version":1,"workspaceId":"w","items":[]}']){final r=run(s,text);failure(r,'invalid_import');expect(r.message, 'Invalid import');}expect(s.loads,isEmpty);
  });
}
