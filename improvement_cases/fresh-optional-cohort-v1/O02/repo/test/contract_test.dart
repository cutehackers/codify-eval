import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:o02_fixture/models.dart';
import 'package:o02_fixture/export_selection.dart';
import 'package:o02_fixture/export_encoding.dart';
import 'package:o02_fixture/export_service.dart';

ExportRequest request(List<Object?> ids,{Object? revision=0,Object? workspace='w',Object? bundle='b'})=>ExportRequest(workspace,bundle,revision,ids);
MemoryDocumentReader docs() {final r=MemoryDocumentReader();r.data['w/a']=const Document('w','a','A','hello');r.data['w/z']=const Document('w','z','Z','한글😀\r\n');return r;}
Outcome run(MemoryBundleStore s,MemoryDocumentReader d,ExportRequest r,{bool allowed=true,TextBundle? Function(String,List<Document>)? encoder})=>exportTextBundle(request:r,permissions:PermissionProvider(allowed),reader:d,store:s,encoder:encoder);
void failure(Outcome r,String code){expect(r.code,code);expect(r.revision,isNull);expect(r.report,isEmpty);expect(r.message,Outcome.messages[code]);}

void main() {
  test("P01 complete UTF8 export manifest order LF and report", () {
final s=MemoryBundleStore(),d=docs();final r=run(s,d,request(['z','a']));expect(r.code,'applied');expect(r.revision,1);final b=s.data['w/b']!.bundle!;expect(b.files['documents/z.txt'],utf8.encode('한글😀\r\n'));expect(b.files['documents/a.txt'],utf8.encode('hello'));final n=utf8.encode('한글😀\r\n').length;
expect(utf8.decode(b.manifest),jsonEncode({'version':1,'workspaceId':'w','documents':[{'id':'z','title':'Z','path':'documents/z.txt','byteLength':n},{'id':'a','title':'A','path':'documents/a.txt','byteLength':5}]})+'\n');expect(r.report,[{'id':'z','path':'documents/z.txt','byteLength':n},{'id':'a','path':'documents/a.txt','byteLength':5}]);expect(d.reads,['w/z','w/a']);expect(s.loads,['w/b']);expect(s.commits,1);
  });
  test("P02 denied malformed request precedes reads", () {
final s=MemoryBundleStore(),d=docs();failure(run(s,d,request(['../x'],workspace:null,revision:-1),allowed:false),'forbidden');expect(d.reads,isEmpty);expect(s.loads,isEmpty);expect(s.commits,0);
  });
  test("P03 request grammar duplicates counts and types rejected", () {
final s=MemoryBundleStore(),d=docs();for(final r in [request([]),request(['a','a']),request(['../x']),request(['%2e']),request(['a/b']),request([4]),request(['a'],workspace:'../x'),request(['a'],bundle:'../x'),request(['a'],revision:0.0),request(List.generate(101,(i)=>'d$i'))]){failure(run(s,d,r),'invalid_request');}expect(d.reads,isEmpty);expect(s.loads,isEmpty);
  });
  test("P04 missing selection no bundle", () {
final s=MemoryBundleStore(),d=docs();failure(run(s,d,request(['a','missing'])),'not_found');expect(s.data,isEmpty);expect(s.loads,isEmpty);
  });
  test("P05 wrong workspace or ID denied", () {
for(final doc in [const Document('other','a','secret','body'),const Document('w','wrong','secret','body')]){final s=MemoryBundleStore(),d=docs();d.data['w/a']=doc;failure(run(s,d,request(['a'])),'forbidden');expect(s.commits,0);}
  });
  test("P06 current no-op stale repeated request conflicts", () {
final s=MemoryBundleStore(),d=docs();expect(run(s,d,request(['a'])).code,'applied');expect(run(s,d,request(['a'],revision:1)).code,'unchanged');failure(run(s,d,request(['a'])),'conflict');expect(s.commits,1);
  });
  test("P07 rollback and false compare preserve previous bundle", () {
for(final throwing in [true,false]){final s=MemoryBundleStore(),d=docs();run(s,d,request(['a']));final old=s.data['w/b'];s.throwCommit=throwing;s.rejectCommit=!throwing;failure(run(s,d,request(['z'],revision:1)),throwing?'storage_failure':'conflict');expect(identical(s.data['w/b'],old),isTrue);}
  });
  test("P08 record shape lengths invalid before commit", () {
for(final doc in [Document('w','a','t'*81,'body'),Document('w','a','title','b'*100001)]){final s=MemoryBundleStore(),d=docs();d.data['w/a']=doc;failure(run(s,d,request(['a'])),'invalid_request');expect(s.commits,0);expect(s.loads,isEmpty);}
  });
  test("P09 reader store encoder exceptions sanitized", () {
for(var i=0;i<3;i++){final s=MemoryBundleStore(),d=docs();if(i==0)d.throwRead=true;if(i==1)s.throwLoad=true;failure(run(s,d,request(['a']),encoder:i==2?(w,ds)=>throw StateError('private encoder secret'):null),'storage_failure');expect(s.commits,0);}
  });
  test("P10 empty body title valid unchanged exact no added LF", () {
final b=encodeTextBundle('w',[const Document('w','a','','')])!;expect(b.files['documents/a.txt'],isEmpty);expect(utf8.decode(b.manifest),'{"version":1,"workspaceId":"w","documents":[{"id":"a","title":"","path":"documents/a.txt","byteLength":0}]}\n');
  });
  test("P11 other bundle workspace preserved", () {
final s=MemoryBundleStore(),d=docs();final old=BundleSnapshot(7,encodeTextBundle('x',[const Document('x','a','x','x')]));s.data['x/b']=old;s.data['w/other']=old;run(s,d,request(['a']));expect(identical(s.data['x/b'],old),isTrue);expect(identical(s.data['w/other'],old),isTrue);expect(d.data.length,2);
  });
  test("P12 pure selection ordered validation protected helper", () {
final d=docs();final r=request(['z','a']);expect(validExportRequest(r),isTrue);expect(selectDocuments(r,d).documents.map((x)=>x.id),['z','a']);expect(validId('x'*40),isTrue);expect(validId('x'*41),isFalse);
  });
}
