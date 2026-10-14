from pathlib import Path
import json
BASE=Path(__file__).resolve().parent.parent

def write(c,p,t):
 q=BASE/c/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(t.strip()+'\n')
header1='''import 'dart:convert';
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
'''
public1=[
('P01 mixed effects preserve metadata and unlisted workspaces', '''final s=MemorySearchStore();
s.data['w']=SearchSnapshot(4,{'a':const SavedSearch('w','a','Old','q','keep'), 'b':const SavedSearch('w','b','Same','same','old'), 'z':const SavedSearch('w','z','Leave','alone','z')});
s.data['other']=SearchSnapshot(9,{'a':const SavedSearch('other','a','Other','x','o')});
final r=run(s,payload([row('b',title:'Same',expression:'same'),row('a'),row('c')]),revision:4);
expect(r.code,'applied');expect(r.revision,5);expect(r.report,[{'id':'b','action':'unchanged'},{'id':'a','action':'updated'},{'id':'c','action':'inserted'}]);
expect(s.data['w']!.records['a']!.createdAt,'keep');expect(s.data['w']!.records['c']!.createdAt,'imported');expect(s.data['w']!.records['z']!.title,'Leave');expect(s.data['other']!.revision,9);expect(s.loads,['w']);expect(s.commits,1);'''),
('P02 permission denial precedes malformed request and all reads','''final s=MemorySearchStore();failure(run(s,'{bad',target:'../x',revision:-1,allowed:false),'forbidden');expect(s.loads,isEmpty);expect(s.commits,0);'''),
('P03 invalid target revision payload scope and schema precede reads','''for(final call in [() => run(MemorySearchStore(),'{}',target:'../x'),() => run(MemorySearchStore(),'{}',revision:0.0)]){failure(call(),'invalid_import');}
final s=MemorySearchStore();for(final text in [payload([],workspace:'other'),'{"version":2,"workspaceId":"w","items":[],"extra":true}',payload([{'id':'a','title':'ok','expression':'q','createdAt':'hack'}])]){failure(run(s,text),'invalid_import');}expect(s.loads,isEmpty);'''),
('P04 v1 v2 equivalence and exact v2 key order LF', '''final v1=payload([{'id':'a','label':' 한글 ','query':'x\\r\\ny'}],version:1);final v2=payload([row('a',title:' 한글 ',expression:'x\\r\\ny')]);
final a=MemorySearchStore(),b=MemorySearchStore();expect(run(a,v1).report,run(b,v2).report);expect(a.data['w']!.records['a']!.expression,b.data['w']!.records['a']!.expression);
expect(encodeSearchExport(decodeSearchImport(decodePortableJson(v1))!),v2+'\\n');'''),
('P05 current no-op no transaction but stale no-op conflicts','''final s=MemorySearchStore();s.data['w']=SearchSnapshot(3,{'a':const SavedSearch('w','a','Title','query','old')});
expect(run(s,payload([row('a')]),revision:3).code,'unchanged');failure(run(s,payload([row('a')]),revision:2),'conflict');expect(s.commits,0);'''),
('P06 empty collection is valid no-op with revision check','''final s=MemorySearchStore();expect(run(s,payload([])).code,'unchanged');failure(run(s,payload([]),revision:1),'conflict');expect(s.commits,0);'''),
('P07 duplicate JSON keys malformed JSON duplicate IDs invalid','''final s=MemorySearchStore();for(final t in ['{"version":2,"version":2,"workspaceId":"w","items":[]}','{bad',payload([row('a'),row('a')])]){failure(run(s,t),'invalid_import');}expect(s.loads,isEmpty);'''),
('P08 foreign workspace and mismatched record key rejected','''for(final bad in [const SavedSearch('other','a','x','y','t'),const SavedSearch('w','wrong','x','y','t')]){final s=MemorySearchStore();s.data['w']=SearchSnapshot(0,{'a':bad});failure(run(s,payload([row('b')])),'forbidden');expect(s.commits,0);}'''),
('P09 false CAS safe conflict and rollback failure sanitized','''for(final fail in [false,true]){final s=MemorySearchStore();s.data['w']=SearchSnapshot(0,{'z':const SavedSearch('w','z','keep','q','t')});s.rejectCommit=!fail;s.throwCommit=fail;
failure(run(s,payload([row('a'),row('b')])),fail?'storage_failure':'conflict');expect(s.data['w']!.revision,0);expect(s.data['w']!.records.keys,['z']);expect(s.commits,1);}'''),
('P10 UTF16 limits whitespace preserved and unsafe IDs rejected','''final s=MemorySearchStore();final r=run(s,payload([row('safe_-9',title:' '*80,expression:'😀'*1000)]));expect(r.code,'applied');expect(s.data['w']!.records['safe_-9']!.expression.length,2000);
for(final id in ['../x','a/b','%2F','', 'x'*41]){failure(run(MemorySearchStore(),payload([row(id)])),'invalid_import');}failure(run(MemorySearchStore(),payload([row('a',title:'😀'*41)])),'invalid_import');'''),
('P11 codec strict types and cardinality', '''for(final data in [{'version':2.0,'workspaceId':'w','items':[]},{'version':3,'workspaceId':'w','items':[]},{'version':2,'workspaceId':'w','items':List.generate(101,(i)=>row('a$i'))},{'version':2,'workspaceId':'w','items':[{'id':'a','title':3,'expression':'q'}]}]){expect(decodeSearchImport(data),isNull);}'''),
('P12 pure planner stable order and store read exception', '''final data=ImportData('w',[const PortableSearch('b','B','q'),const PortableSearch('a','A','p')]);final p=planSearchImport(data,SearchSnapshot(0,{}));expect(p.effects.map((r)=>r.id),['b','a']);expect(p.report.map((r)=>r['id']),['b','a']);final s=MemorySearchStore()..throwLoad=true;failure(run(s,payload([row('a')])),'storage_failure');'''),
]
private1=[
('R01 denied valid import hides foreign malformed data','''final s=MemorySearchStore()..throwLoad=true;final p=PermissionProvider(false);final r=importSavedSearches(targetWorkspaceId:'w',expectedRevision:0,jsonText:payload([row('a')],workspace:'other'),permissions:p,store:s);failure(r,'forbidden');expect(p.targets,['w']);expect(s.loads,isEmpty);'''),
('R02 foreign unlisted snapshot record rejects entire import before revision','''final s=MemorySearchStore();s.data['w']=SearchSnapshot(7,{'unlisted':const SavedSearch('alien','unlisted','secret','q','t')});failure(run(s,payload([]),revision:0),'forbidden');expect(s.commits,0);'''),
('R03 full limit ID title expression accepted boundary plus over rejected','''final rows=List.generate(100,(i)=>row('id$i',title:'t'*80,expression:'q'*2000));final s=MemorySearchStore();expect(run(s,payload(rows)).report.length,100);expect(s.commits,1);for(final r in [row('a',title:''),row('a',expression:''),row('a',expression:'q'*2001)]){failure(run(MemorySearchStore(),payload([r])),'invalid_import');}'''),
('R04 metadata injection and noninteger revision rejected before reads','''final s=MemorySearchStore();for(final rev in [-1,1.0,'0',null]){failure(run(s,payload([]),revision:rev),'invalid_import');}failure(run(s,payload([{'id':'a','title':'t','expression':'q','createdAt':'t'}])),'invalid_import');expect(s.loads,isEmpty);'''),
('R05 escaped duplicate JSON keys rejected protected decoder','''final s=MemorySearchStore();failure(run(s,r'{"version":2,"workspaceId":"w","items":[{"id":"a","title":"t","expression":"q","\\u0069d":"b"}]}'),'invalid_import');expect(s.loads,isEmpty);'''),
('R06 rollback mixed effects retains exact old snapshot','''final s=MemorySearchStore();final old=SearchSnapshot(5,{'a':const SavedSearch('w','a','Old','old','stamp'),'b':const SavedSearch('w','b','Title','query','stampB')});s.data['w']=old;s.throwCommit=true;failure(run(s,payload([row('a'),row('b'),row('c')]),revision:5),'storage_failure');expect(identical(s.data['w'],old),isTrue);expect(s.commits,1);'''),
('R07 v1 imported expression title retain different text','''final s=MemorySearchStore();expect(run(s,payload([{'id':'one','label':'Label','query':'title != label'}],version:1)).code,'applied');expect(s.data['w']!.records['one']!.expression,'title != label');'''),
('R08 exact serialized escapes Unicode slash CR LF final single LF','''final data=ImportData('w',[const PortableSearch('x','"한글"','a/b\\r\\n\\t\\\\')]);final expected=jsonEncode({'version':2,'workspaceId':'w','items':[{'id':'x','title':'"한글"','expression':'a/b\\r\\n\\t\\\\'}]})+'\\n';expect(encodeSearchExport(data),expected);final decoded=decodeSearchImport(decodePortableJson(expected))!;expect(decoded.rows.single.expression,data.rows.single.expression);'''),
('R09 report mixed ordering all once and no-op metadata untouched','''final s=MemorySearchStore();const old=SavedSearch('w','z','Title','query','original');s.data['w']=SearchSnapshot(1,{'z':old,'m':const SavedSearch('w','m','old','q','meta')});final r=run(s,payload([row('n'),row('z'),row('m')]),revision:1);expect(r.report,[{'id':'n','action':'inserted'},{'id':'z','action':'unchanged'},{'id':'m','action':'updated'}]);expect(identical(s.data['w']!.records['z'],old),isTrue);'''),
('R10 stale mutation blocks transaction and reports','''final s=MemorySearchStore();s.data['w']=SearchSnapshot(9,{});failure(run(s,payload([row('a')]),revision:8),'conflict');expect(s.commits,0);expect(s.data['w']!.records,isEmpty);'''),
('R11 valid target access identity excludes payload workspace','''final s=MemorySearchStore();final p=PermissionProvider(true);failure(importSavedSearches(targetWorkspaceId:'w',expectedRevision:0,jsonText:payload([],workspace:'x'),permissions:p,store:s),'invalid_import');expect(p.targets,['w']);expect(s.loads,isEmpty);'''),
('R12 unknown row and top schema prevent reads and failure detail leakage','''final s=MemorySearchStore();for(final text in ['[]','null',payload([{'id':'a','title':'t','expression':false}]),'{"version":1,"workspaceId":"w","items":[]}']){final r=run(s,text);failure(r,'invalid_import');expect(r.message, 'Invalid import');}expect(s.loads,isEmpty);'''),
]
header2='''import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:o02_fixture/models.dart';
import 'package:o02_fixture/export_selection.dart';
import 'package:o02_fixture/export_encoding.dart';
import 'package:o02_fixture/export_service.dart';

ExportRequest request(List<Object?> ids,{Object? revision=0,Object? workspace='w',Object? bundle='b'})=>ExportRequest(workspace,bundle,revision,ids);
MemoryDocumentReader docs() {final r=MemoryDocumentReader();r.data['w/a']=const Document('w','a','A','hello');r.data['w/z']=const Document('w','z','Z','한글😀\\r\\n');return r;}
Outcome run(MemoryBundleStore s,MemoryDocumentReader d,ExportRequest r,{bool allowed=true,TextBundle? Function(String,List<Document>)? encoder})=>exportTextBundle(request:r,permissions:PermissionProvider(allowed),reader:d,store:s,encoder:encoder);
void failure(Outcome r,String code){expect(r.code,code);expect(r.revision,isNull);expect(r.report,isEmpty);expect(r.message,Outcome.messages[code]);}
'''
public2=[
('P01 complete UTF8 export manifest order LF and report','''final s=MemoryBundleStore(),d=docs();final r=run(s,d,request(['z','a']));expect(r.code,'applied');expect(r.revision,1);final b=s.data['w/b']!.bundle!;expect(b.files['documents/z.txt'],utf8.encode('한글😀\\r\\n'));expect(b.files['documents/a.txt'],utf8.encode('hello'));final n=utf8.encode('한글😀\\r\\n').length;
expect(utf8.decode(b.manifest),jsonEncode({'version':1,'workspaceId':'w','documents':[{'id':'z','title':'Z','path':'documents/z.txt','byteLength':n},{'id':'a','title':'A','path':'documents/a.txt','byteLength':5}]})+'\\n');expect(r.report,[{'id':'z','path':'documents/z.txt','byteLength':n},{'id':'a','path':'documents/a.txt','byteLength':5}]);expect(d.reads,['w/z','w/a']);expect(s.loads,['w/b']);expect(s.commits,1);'''),
('P02 denied malformed request precedes reads','''final s=MemoryBundleStore(),d=docs();failure(run(s,d,request(['../x'],workspace:null,revision:-1),allowed:false),'forbidden');expect(d.reads,isEmpty);expect(s.loads,isEmpty);expect(s.commits,0);'''),
('P03 request grammar duplicates counts and types rejected','''final s=MemoryBundleStore(),d=docs();for(final r in [request([]),request(['a','a']),request(['../x']),request(['%2e']),request(['a/b']),request([4]),request(['a'],workspace:'../x'),request(['a'],bundle:'../x'),request(['a'],revision:0.0),request(List.generate(101,(i)=>'d$i'))]){failure(run(s,d,r),'invalid_request');}expect(d.reads,isEmpty);expect(s.loads,isEmpty);'''),
('P04 missing selection no bundle','''final s=MemoryBundleStore(),d=docs();failure(run(s,d,request(['a','missing'])),'not_found');expect(s.data,isEmpty);expect(s.loads,isEmpty);'''),
('P05 wrong workspace or ID denied','''for(final doc in [const Document('other','a','secret','body'),const Document('w','wrong','secret','body')]){final s=MemoryBundleStore(),d=docs();d.data['w/a']=doc;failure(run(s,d,request(['a'])),'forbidden');expect(s.commits,0);}'''),
('P06 current no-op stale repeated request conflicts','''final s=MemoryBundleStore(),d=docs();expect(run(s,d,request(['a'])).code,'applied');expect(run(s,d,request(['a'],revision:1)).code,'unchanged');failure(run(s,d,request(['a'])),'conflict');expect(s.commits,1);'''),
('P07 rollback and false compare preserve previous bundle','''for(final throwing in [true,false]){final s=MemoryBundleStore(),d=docs();run(s,d,request(['a']));final old=s.data['w/b'];s.throwCommit=throwing;s.rejectCommit=!throwing;failure(run(s,d,request(['z'],revision:1)),throwing?'storage_failure':'conflict');expect(identical(s.data['w/b'],old),isTrue);}'''),
('P08 record shape lengths invalid before commit','''for(final doc in [Document('w','a','t'*81,'body'),Document('w','a','title','b'*100001)]){final s=MemoryBundleStore(),d=docs();d.data['w/a']=doc;failure(run(s,d,request(['a'])),'invalid_request');expect(s.commits,0);expect(s.loads,isEmpty);}'''),
('P09 reader store encoder exceptions sanitized','''for(var i=0;i<3;i++){final s=MemoryBundleStore(),d=docs();if(i==0)d.throwRead=true;if(i==1)s.throwLoad=true;failure(run(s,d,request(['a']),encoder:i==2?(w,ds)=>throw StateError('private encoder secret'):null),'storage_failure');expect(s.commits,0);}'''),
('P10 empty body title valid unchanged exact no added LF','''final b=encodeTextBundle('w',[const Document('w','a','','')])!;expect(b.files['documents/a.txt'],isEmpty);expect(utf8.decode(b.manifest),'{"version":1,"workspaceId":"w","documents":[{"id":"a","title":"","path":"documents/a.txt","byteLength":0}]}\\n');'''),
('P11 other bundle workspace preserved','''final s=MemoryBundleStore(),d=docs();final old=BundleSnapshot(7,encodeTextBundle('x',[const Document('x','a','x','x')]));s.data['x/b']=old;s.data['w/other']=old;run(s,d,request(['a']));expect(identical(s.data['x/b'],old),isTrue);expect(identical(s.data['w/other'],old),isTrue);expect(d.data.length,2);'''),
('P12 pure selection ordered validation protected helper','''final d=docs();final r=request(['z','a']);expect(validExportRequest(r),isTrue);expect(selectDocuments(r,d).documents.map((x)=>x.id),['z','a']);expect(validId('x'*40),isTrue);expect(validId('x'*41),isFalse);'''),
]
private2=[
('R01 denied valid target hides reader storage diagnostics','''final s=MemoryBundleStore()..throwLoad=true,d=docs()..throwRead=true;final p=PermissionProvider(false);failure(exportTextBundle(request:request(['a']),permissions:p,reader:d,store:s),'forbidden');expect(p.targets,['w']);expect(d.reads,isEmpty);expect(s.loads,isEmpty);'''),
('R02 invalid revisions IDs target prevent contents','''final s=MemoryBundleStore(),d=docs();for(final rev in [-1,'0',null,1.0]){failure(run(s,d,request(['a'],revision:rev)),'invalid_request');}for(final id in ['.','..','a\\\\b','a%2Fb','한글','x'*41]){failure(run(s,d,request([id])),'invalid_request');}expect(d.reads,isEmpty);'''),
('R03 mixed foreign selection cannot commit earlier valid document','''final s=MemoryBundleStore(),d=docs();d.data['w/z']=const Document('alien','z','secret','secret');failure(run(s,d,request(['a','z'])),'forbidden');expect(s.data,isEmpty);expect(s.loads,isEmpty);expect(s.commits,0);'''),
('R04 mixed missing selection cannot commit earlier document','''final s=MemoryBundleStore(),d=docs();failure(run(s,d,request(['z','missing','a'])),'not_found');expect(d.reads,['w/z','w/missing']);expect(s.commits,0);'''),
('R05 body UTF8 bytes versus UTF16 units exact escaping','''final s=MemoryBundleStore(),d=docs();d.data['w/a']=const Document('w','a','"한글"','é😀\\t\\r\\n/');final r=run(s,d,request(['a']));final n=utf8.encode('é😀\\t\\r\\n/').length;expect(r.report.single['byteLength'],n);final b=s.data['w/b']!.bundle!;expect(b.files.values.single,utf8.encode('é😀\\t\\r\\n/'));expect(utf8.decode(b.manifest),jsonEncode({'version':1,'workspaceId':'w','documents':[{'id':'a','title':'"한글"','path':'documents/a.txt','byteLength':n}]})+'\\n');'''),
('R06 100 documents maximum content and UTF16 title','''final s=MemoryBundleStore(),d=MemoryDocumentReader();final ids=List.generate(100,(i)=>'d$i');for(final id in ids){d.data['w/$id']=Document('w',id,'😀'*40,id=='d0'?'😀'*50000:'');}final r=run(s,d,request(ids));expect(r.code,'applied');expect(r.report.length,100);expect(r.report.first['byteLength'],200000);expect(s.commits,1);'''),
('R07 exact old version1 bundle no rewrite report order','''final s=MemoryBundleStore(),d=docs();final b=TextBundle(utf8.encode('{"version":1,"workspaceId":"w","documents":[{"id":"a","title":"A","path":"documents/a.txt","byteLength":5}]}\\n'),{'documents/a.txt':utf8.encode('hello')},[]);s.data['w/b']=BundleSnapshot(6,b);final r=run(s,d,request(['a'],revision:6));expect(r.code,'unchanged');expect(r.report,[{'id':'a','path':'documents/a.txt','byteLength':5}]);expect(s.commits,0);'''),
('R08 stale byte identical bundle still conflict','''final s=MemoryBundleStore(),d=docs();run(s,d,request(['z','a']));final old=s.data['w/b'];failure(run(s,d,request(['z','a'],revision:0)),'conflict');expect(identical(s.data['w/b'],old),isTrue);expect(s.commits,1);'''),
('R09 atomic rollback full replacement mixed file old preserved','''final s=MemoryBundleStore(),d=docs();run(s,d,request(['z','a']));final old=s.data['w/b'];d.data['w/a']=const Document('w','a','new','changed');s.throwCommit=true;failure(run(s,d,request(['a'],revision:1)),'storage_failure');expect(identical(s.data['w/b'],old),isTrue);expect(s.data['w/b']!.bundle!.files.keys,['documents/z.txt','documents/a.txt']);'''),
('R10 exact successful report input order independent manifest','''final s=MemoryBundleStore(),d=docs();final r=run(s,d,request(['a','z']));expect(r.report.map((x)=>x['id']),['a','z']);for(final entry in r.report){expect(entry['byteLength'],s.data['w/b']!.bundle!.files[entry['path']]!.length);}'''),
('R11 existing files completeness affects no-op comparison','''final s=MemoryBundleStore(),d=docs();final good=encodeTextBundle('w',[d.data['w/a']!])!;s.data['w/b']=BundleSnapshot(2,TextBundle(good.manifest,{'documents/a.txt':[0],'documents/extra.txt':[1]},[]));final r=run(s,d,request(['a'],revision:2));expect(r.code,'applied');expect(r.revision,3);expect(s.data['w/b']!.bundle!.files.keys,['documents/a.txt']);'''),
('R12 normal validation before unexpected injected encoder','''final s=MemoryBundleStore(),d=docs();d.data['w/a']=Document('w','a','😀'*41,'body');var called=false;failure(run(s,d,request(['a']),encoder:(w,ds){called=true;throw StateError('secret');}),'invalid_request');expect(called,isFalse);expect(s.commits,0);'''),
]
for c,header,public,private in [('O01',header1,public1,private1),('O02',header2,public2,private2)]:
 for path,tests in [('repo/test/contract_test.dart',public),('private/acceptance_test.dart',private)]:
  text=header+'\nvoid main() {\n'+''.join("  test("+json.dumps(name)+", () {\n"+body+"\n  });\n" for name,body in tests)+'}\n'
  write(c,path,text)
