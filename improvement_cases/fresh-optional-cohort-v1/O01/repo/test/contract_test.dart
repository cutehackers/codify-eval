import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:o01_fixture/models.dart';
import 'package:o01_fixture/search_codec.dart';
import 'package:o01_fixture/search_plan.dart';
import 'package:o01_fixture/search_import_service.dart';

String payload(List<Map<String,Object>> rows, {int version=2,String workspace='w'}) => jsonEncode({
 'version':version,'workspaceId':workspace,version==1?'searches':'items':rows});
Map<String,Object> row(String id,{String title='Title',String expression='query'}) => {'id':id,'title':title,'expression':expression};
Outcome run(MemorySearchStore store,String text,{Object? revision=0,Object? target='w',bool allowed=true}) => importSavedSearches(
 targetWorkspaceId:target,expectedRevision:revision,jsonText:text,permissions:PermissionProvider(allowed),store:store);
void failure(Outcome result,String code) { expect(result.code,code);expect(result.revision,isNull);expect(result.report,isEmpty);expect(result.message,Outcome.messages[code]); }

void main() {
  test("P01 mixed effects preserve metadata and unlisted workspaces", () {
final s=MemorySearchStore();
s.data['w']=SearchSnapshot(4,{'a':const SavedSearch('w','a','Old','q','keep'), 'b':const SavedSearch('w','b','Same','same','old'), 'z':const SavedSearch('w','z','Leave','alone','z')});
s.data['other']=SearchSnapshot(9,{'a':const SavedSearch('other','a','Other','x','o')});
final r=run(s,payload([row('b',title:'Same',expression:'same'),row('a'),row('c')]),revision:4);
expect(r.code,'applied');expect(r.revision,5);expect(r.report,[{'id':'b','action':'unchanged'},{'id':'a','action':'updated'},{'id':'c','action':'inserted'}]);
expect(s.data['w']!.records['a']!.createdAt,'keep');expect(s.data['w']!.records['c']!.createdAt,'imported');expect(s.data['w']!.records['z']!.title,'Leave');expect(s.data['other']!.revision,9);expect(s.loads,['w']);expect(s.commits,1);
  });
  test("P02 permission denial precedes malformed request and all reads", () {
final s=MemorySearchStore();failure(run(s,'{bad',target:'../x',revision:-1,allowed:false),'forbidden');failure(run(s,payload([row('a')]),allowed:false),'forbidden');expect(s.loads,isEmpty);expect(s.commits,0);
  });
  test("P03 invalid target revision payload scope and schema precede reads", () {
for(final call in [() => run(MemorySearchStore(),'{}',target:'../x'),() => run(MemorySearchStore(),'{}',revision:0.0)]){failure(call(),'invalid_import');}
final s=MemorySearchStore();for(final text in [payload([],workspace:'other'),'{"version":2,"workspaceId":"w","items":[],"extra":true}',payload([{'id':'a','title':'ok','expression':'q','createdAt':'hack'}])]){failure(run(s,text),'invalid_import');}expect(s.loads,isEmpty);
  });
  test("P04 v1 v2 equivalence and exact v2 key order LF", () {
final v1=payload([{'id':'a','label':' 한글 ','query':'x\r\ny'}],version:1);final v2=payload([row('a',title:' 한글 ',expression:'x\r\ny')]);
final a=MemorySearchStore(),b=MemorySearchStore();expect(run(a,v1).report,run(b,v2).report);expect(a.data['w']!.records['a']!.expression,b.data['w']!.records['a']!.expression);
expect(encodeSearchExport(decodeSearchImport(decodePortableJson(v1))!),v2+'\n');
  });
  test("P05 current no-op no transaction but stale no-op conflicts", () {
final s=MemorySearchStore();s.data['w']=SearchSnapshot(3,{'a':const SavedSearch('w','a','Title','query','old')});
expect(run(s,payload([row('a')]),revision:3).code,'unchanged');failure(run(s,payload([row('a')]),revision:2),'conflict');expect(s.commits,0);
  });
  test("P06 empty collection is valid no-op with revision check", () {
final s=MemorySearchStore();expect(run(s,payload([])).code,'unchanged');failure(run(s,payload([]),revision:1),'conflict');expect(s.commits,0);
  });
  test("P07 duplicate JSON keys malformed JSON duplicate IDs invalid", () {
final s=MemorySearchStore();for(final t in ['{"version":2,"version":2,"workspaceId":"w","items":[]}','{bad',payload([row('a'),row('a')])]){failure(run(s,t),'invalid_import');}expect(s.loads,isEmpty);
  });
  test("P08 foreign workspace and mismatched record key rejected", () {
for(final bad in [const SavedSearch('other','a','x','y','t'),const SavedSearch('w','wrong','x','y','t')]){final s=MemorySearchStore();s.data['w']=SearchSnapshot(0,{'a':bad});failure(run(s,payload([row('b')])),'forbidden');expect(s.commits,0);}
  });
  test("P09 false CAS safe conflict and rollback failure sanitized", () {
for(final fail in [false,true]){final s=MemorySearchStore();s.data['w']=SearchSnapshot(0,{'z':const SavedSearch('w','z','keep','q','t')});s.rejectCommit=!fail;s.throwCommit=fail;
failure(run(s,payload([row('a'),row('b')])),fail?'storage_failure':'conflict');expect(s.data['w']!.revision,0);expect(s.data['w']!.records.keys,['z']);expect(s.commits,1);}
  });
  test("P10 UTF16 limits whitespace preserved and unsafe IDs rejected", () {
final s=MemorySearchStore();final r=run(s,payload([row('safe_-9',title:' '*80,expression:'😀'*1000)]));expect(r.code,'applied');expect(s.data['w']!.records['safe_-9']!.expression.length,2000);
for(final id in ['../x','a/b','%2F','', 'x'*41]){failure(run(MemorySearchStore(),payload([row(id)])),'invalid_import');}failure(run(MemorySearchStore(),payload([row('a',title:'😀'*41)])),'invalid_import');
  });
  test("P11 codec strict types and cardinality", () {
for(final data in [{'version':2.0,'workspaceId':'w','items':[]},{'version':3,'workspaceId':'w','items':[]},{'version':2,'workspaceId':'w','items':List.generate(101,(i)=>row('a$i'))},{'version':2,'workspaceId':'w','items':[{'id':'a','title':3,'expression':'q'}]}]){expect(decodeSearchImport(data),isNull);}
  });
  test("P12 pure planner stable order and store read exception", () {
final data=ImportData('w',[const PortableSearch('b','B','q'),const PortableSearch('a','A','p')]);final p=planSearchImport(data,SearchSnapshot(0,{}));expect(p.effects.map((r)=>r.id),['b','a']);expect(p.report.map((r)=>r['id']),['b','a']);final s=MemorySearchStore()..throwLoad=true;failure(run(s,payload([row('a')])),'storage_failure');
  });
}
