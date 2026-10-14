import 'dart:convert';
import 'package:test/test.dart';
import 'package:feed_fixture/models.dart';
import 'package:feed_fixture/implementation.dart';
Map<String,dynamic> data(int seq,{String id='a',String project='p',String tenant='t',int version=1,String op='put',dynamic text='x'})=>{'seq':seq,'tenant':tenant,'project':project,'id':id,'version':version,'op':op,'text':text};
String lines(List<Map<String,dynamic>> events)=>events.map(jsonEncode).join('\n');
Matcher code(String s)=>throwsA(isA<FeedException>().having((e)=>e.code,'code',s));
class CountingStore extends MemoryFeedStore{
 int calls=0;
 CountingStore():super(FeedState('t',0,{},{}));
 @override void replace(FeedState next){calls++;super.replace(next);}
}
void expectStorageFailure(void Function() action,List<String> forbidden){
 Object? failure;
 try{action();}catch(error){failure=error;}
 expect(failure,isA<FeedException>().having((e)=>e.code,'code','storage'));
 final exposed=failure.toString();
 for(final marker in forbidden){expect(exposed,isNot(contains(marker)));}
}
void main(){
 test('validation and authorization cover whole batch before state errors',(){
  final s=CountingStore();final i=FeedImporter(s);final p=Principal('t',{'p'});
  final before=s.state;
  expect(()=>i.ingest(p,lines([data(1),data(2)..['extra']=true])),code('invalid'));
  expect(s.calls,0);expect(identical(s.state,before),isTrue);
  expect(()=>i.ingest(p,lines([data(3),data(4)..['extra']=true])),code('invalid'));
  expect(()=>i.ingest(p,lines([data(3),data(4,project:'secret')])),code('forbidden'));expect(s.calls,0);
 });
 test('staged mutations roll back after late version error and gap',(){
  for(final tail in [data(2,version:3),data(3,version:2)]){
   final s=CountingStore();final i=FeedImporter(s);
   expect(()=>i.ingest(Principal('t',{'p'}),lines([data(1),tail])),code(tail['seq']==3?'gap':'version'));
   expect(s.state.sequence,0);expect(s.state.history,isEmpty);expect(s.calls,0);
  }
 });
 test('storage failure retry and redaction',(){
  final s=CountingStore()..failNextReplace=true;final i=FeedImporter(s);final p=Principal('t',{'p'});final input=lines([data(1),data(2,version:2,text:'sensitive_text_903')]);
  expectStorageFailure(()=>i.ingest(p,input),['storage-password','sensitive_text_903']);expect(s.calls,1);expect(s.state.documents,isEmpty);expect(s.state.history,isEmpty);
  expect(i.ingest(p,input).applied,2);expect(s.calls,2);expect(s.state.sequence,2);
 });
 test('semantic replay key order new duplicates and importer restart',(){
  final s=CountingStore();final p=Principal('t',{'p'});final e=data(1);
  final reverse=Map<String,dynamic>.fromEntries(e.entries.toList().reversed);
  final r=FeedImporter(s).ingest(p,'${jsonEncode(e)}\r\n\n${jsonEncode(reverse)}\r\n');
  expect(r.applied,1);expect(r.duplicates,1);expect(s.calls,1);
  expect(FeedImporter(s).ingest(p,jsonEncode(reverse)).duplicates,1);expect(s.calls,1);
 });
 test('same tenant replay still requires project permission',(){
  final s=CountingStore();final i=FeedImporter(s);final input=lines([data(1)]);
  i.ingest(Principal('t',{'p'}),input);expect(s.calls,1);
  final before=s.state;
  expect(()=>i.ingest(Principal('t',{}),input),code('forbidden'));
  expect(s.calls,1);expect(identical(s.state,before),isTrue);
  expect(s.state.sequence,1);expect(s.state.documents,before.documents);expect(s.state.history,before.history);
 });
 test('changed replay and unknown historical entry rejected',(){
  final s=CountingStore();final i=FeedImporter(s);final p=Principal('t',{'p'});i.ingest(p,lines([data(1)]));
  for(final e in [data(1,text:'changed'),data(1,id:'b'),data(1,version:2),data(1,project:'q')]){
   expect(()=>i.ingest(Principal('t',{'p','q'}),lines([e])),code('replay_conflict'));
  }
  final missing=MemoryFeedStore(FeedState('t',1,{},{}));expect(()=>FeedImporter(missing).ingest(p,lines([data(1)])),code('replay_conflict'));
 });
 test('delete recreate old replay and unrelated document regression',(){
  final s=CountingStore();final i=FeedImporter(s);final p=Principal('t',{'p'});
  final deletion=data(3,version:2,op:'delete',text:null);
  i.ingest(p,lines([data(1),data(2,id:'keep'),deletion,data(4,text:'new')]));
  expect(s.state.documents['a']!.version,1);expect(s.state.documents['a']!.text,'new');expect(s.state.documents['keep']!.text,'x');
  expect(i.ingest(p,lines([deletion])).duplicates,1);expect(s.state.documents['a']!.text,'new');expect(s.state.history.length,4);
 });
 test('project immutable even with both permissions',(){
  final s=CountingStore();final i=FeedImporter(s);final p=Principal('t',{'p','q'});i.ingest(p,lines([data(1)]));
  expect(()=>i.ingest(p,lines([data(2,project:'q',version:2)])),code('conflict'));expect(s.state.documents['a']!.project,'p');
 });
 test('tenant denial precedes replay information',(){
  final s=CountingStore();final i=FeedImporter(s);i.ingest(Principal('t',{'p'}),lines([data(1)]));
  expect(()=>i.ingest(Principal('other',{'p'}),lines([data(1,text:'changed')])),code('forbidden'));
  expect(()=>i.ingest(Principal('t',{'p'}),lines([data(1,tenant:'other')])),code('forbidden'));
 });
 test('field and byte boundary table',(){
  final invalid=[data(1)..['seq']=1.0,data(1)..['version']='1',data(1)..['seq']=true,data(1)..['id']='a\n',data(1,op:'unknown'),data(1,op:'delete',text:''),data(1,text:'a\x00b'),data(1,text:List.filled(2049,'é').join()),data(1)..remove('text')];
  for(final e in invalid){final s=CountingStore();expect(()=>FeedImporter(s).ingest(Principal('t',{'p'}),lines([e])),code('invalid'));expect(s.calls,0);}
  for(final input in ['', ' \n\r\n',lines(List.generate(101,(n)=>data(n+1,id:'m$n'))),List.filled(65537,' ').join()]){
   expect(()=>FeedImporter(CountingStore()).ingest(Principal('t',{'p'}),input),code('invalid'));
  }
  final s=CountingStore();expect(FeedImporter(s).ingest(Principal('t',{'p'}),lines([data(1,text:List.filled(2048,'é').join())])).applied,1);
 });
 test('delete nonexistent and wrong version do not advance',(){
  final s=CountingStore();final i=FeedImporter(s);final p=Principal('t',{'p'});
  expect(()=>i.ingest(p,lines([data(1,op:'delete',text:null)])),code('version'));
  i.ingest(p,lines([data(1)]));expect(()=>i.ingest(p,lines([data(2,version:1,op:'delete',text:null)])),code('version'));expect(s.state.sequence,1);
 });
 test('state maps cannot be modified externally',(){
  final s=CountingStore();FeedImporter(s).ingest(Principal('t',{'p'}),lines([data(1)]));
  expect(()=>s.state.documents.clear(),throwsUnsupportedError);expect(()=>s.state.history.clear(),throwsUnsupportedError);
 });
}
