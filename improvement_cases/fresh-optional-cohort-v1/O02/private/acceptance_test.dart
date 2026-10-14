import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:o02_fixture/models.dart';
import 'package:o02_fixture/export_encoding.dart';
import 'package:o02_fixture/export_service.dart';

ExportRequest request(List<Object?> ids,{Object? revision=0,Object? workspace='w',Object? bundle='b'})=>ExportRequest(workspace,bundle,revision,ids);
MemoryDocumentReader docs() {final r=MemoryDocumentReader();r.data['w/a']=const Document('w','a','A','hello');r.data['w/z']=const Document('w','z','Z','한글😀\r\n');return r;}
Outcome run(MemoryBundleStore s,MemoryDocumentReader d,ExportRequest r,{bool allowed=true,TextBundle? Function(String,List<Document>)? encoder})=>exportTextBundle(request:r,permissions:PermissionProvider(allowed),reader:d,store:s,encoder:encoder);
void failure(Outcome r,String code){expect(r.code,code);expect(r.revision,isNull);expect(r.report,isEmpty);expect(r.message,Outcome.messages[code]);}

void main() {
  test("R01 denied valid target hides reader storage diagnostics", () {
final s=MemoryBundleStore()..throwLoad=true,d=docs()..throwRead=true;final p=PermissionProvider(false);failure(exportTextBundle(request:request(['a']),permissions:p,reader:d,store:s),'forbidden');expect(p.targets,['w']);expect(d.reads,isEmpty);expect(s.loads,isEmpty);
  });
  test("R02 invalid revisions IDs target prevent contents", () {
final s=MemoryBundleStore(),d=docs();for(final rev in [-1,'0',null,1.0]){failure(run(s,d,request(['a'],revision:rev)),'invalid_request');}for(final id in ['.','..','a\\b','a%2Fb','한글','x'*41]){failure(run(s,d,request([id])),'invalid_request');}expect(d.reads,isEmpty);
  });
  test("R03 mixed foreign selection cannot commit earlier valid document", () {
final s=MemoryBundleStore(),d=docs();d.data['w/z']=const Document('alien','z','secret','secret');failure(run(s,d,request(['a','z'])),'forbidden');expect(s.data,isEmpty);expect(s.loads,isEmpty);expect(s.commits,0);
  });
  test("R04 mixed missing selection cannot commit earlier document", () {
final s=MemoryBundleStore(),d=docs();failure(run(s,d,request(['z','missing','a'])),'not_found');expect(d.reads,['w/z','w/missing']);expect(s.commits,0);
  });
  test("R05 body UTF8 bytes versus UTF16 units exact escaping", () {
final s=MemoryBundleStore(),d=docs();d.data['w/a']=const Document('w','a','"한글"','é😀\t\r\n/');final r=run(s,d,request(['a']));final n=utf8.encode('é😀\t\r\n/').length;expect(r.report.single['byteLength'],n);final b=s.data['w/b']!.bundle!;expect(b.files.values.single,utf8.encode('é😀\t\r\n/'));expect(utf8.decode(b.manifest),jsonEncode({'version':1,'workspaceId':'w','documents':[{'id':'a','title':'"한글"','path':'documents/a.txt','byteLength':n}]})+'\n');
  });
  test("R06 100 documents maximum content and UTF16 title", () {
final s=MemoryBundleStore(),d=MemoryDocumentReader();final ids=List.generate(100,(i)=>'d$i');for(final id in ids){d.data['w/$id']=Document('w',id,'😀'*40,id=='d0'?'😀'*50000:'');}final r=run(s,d,request(ids));expect(r.code,'applied');expect(r.report.length,100);expect(r.report.first['byteLength'],200000);expect(s.commits,1);
  });
  test("R07 exact old version1 bundle no rewrite report order", () {
final s=MemoryBundleStore(),d=docs();final b=TextBundle(utf8.encode('{"version":1,"workspaceId":"w","documents":[{"id":"a","title":"A","path":"documents/a.txt","byteLength":5}]}\n'),{'documents/a.txt':utf8.encode('hello')},[]);s.data['w/b']=BundleSnapshot(6,b);final r=run(s,d,request(['a'],revision:6));expect(r.code,'unchanged');expect(r.report,[{'id':'a','path':'documents/a.txt','byteLength':5}]);expect(s.commits,0);
  });
  test("R08 stale byte identical bundle still conflict", () {
final s=MemoryBundleStore(),d=docs();run(s,d,request(['z','a']));final old=s.data['w/b'];failure(run(s,d,request(['z','a'],revision:0)),'conflict');expect(identical(s.data['w/b'],old),isTrue);expect(s.commits,1);
  });
  test("R09 atomic rollback full replacement mixed file old preserved", () {
final s=MemoryBundleStore(),d=docs();run(s,d,request(['z','a']));final old=s.data['w/b'];d.data['w/a']=const Document('w','a','new','changed');s.throwCommit=true;failure(run(s,d,request(['a'],revision:1)),'storage_failure');expect(identical(s.data['w/b'],old),isTrue);expect(s.data['w/b']!.bundle!.files.keys,['documents/z.txt','documents/a.txt']);
  });
  test("R10 exact successful report input order independent manifest", () {
final s=MemoryBundleStore(),d=docs();final r=run(s,d,request(['a','z']));expect(r.report.map((x)=>x['id']),['a','z']);for(final entry in r.report){expect(entry['byteLength'],s.data['w/b']!.bundle!.files[entry['path']]!.length);}
  });
  test("R11 existing files completeness affects no-op comparison", () {
final s=MemoryBundleStore(),d=docs();final good=encodeTextBundle('w',[d.data['w/a']!])!;s.data['w/b']=BundleSnapshot(2,TextBundle(good.manifest,{'documents/a.txt':[0],'documents/extra.txt':[1]},[]));final r=run(s,d,request(['a'],revision:2));expect(r.code,'applied');expect(r.revision,3);expect(s.data['w/b']!.bundle!.files.keys,['documents/a.txt']);
  });
  test("R12 normal validation before unexpected injected encoder", () {
final s=MemoryBundleStore(),d=docs();d.data['w/a']=Document('w','a','😀'*41,'body');var called=false;failure(run(s,d,request(['a']),encoder:(w,ds){called=true;throw StateError('secret');}),'invalid_request');expect(called,isFalse);expect(s.commits,0);
  });
}
