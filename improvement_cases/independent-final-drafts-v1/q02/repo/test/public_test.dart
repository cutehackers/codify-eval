import 'dart:convert';
import 'package:test/test.dart';
import 'package:feed_fixture/models.dart';
import 'package:feed_fixture/implementation.dart';
String event(int seq,int version,String text)=>jsonEncode({'seq':seq,'tenant':'t','project':'p','id':'a','version':version,'op':'put','text':text});
void main(){
 test('example and semantic replay',(){
  final s=MemoryFeedStore(FeedState('t',0,{},{}));final importer=FeedImporter(s);final p=Principal('t',{'p'});
  final input='${event(1,1,"hello")}\n${event(2,2,"world")}\n';
  final r=importer.ingest(p,input);expect(r.applied,2);expect(r.sequence,2);expect(s.state.documents['a']!.text,'world');
  final replay=importer.ingest(p,input);expect(replay.applied,0);expect(replay.duplicates,2);
 });
 test('invalid JSON changes nothing',(){
  final s=MemoryFeedStore(FeedState('t',0,{},{}));
  expect(()=>FeedImporter(s).ingest(Principal('t',{'p'}),'not-json'),throwsA(isA<FeedException>().having((e)=>e.code,'code','invalid')));expect(s.state.sequence,0);
 });
 test('project authorization is required',(){
  final s=MemoryFeedStore(FeedState('t',0,{},{}));
  expect(()=>FeedImporter(s).ingest(Principal('t',{}),event(1,1,'x')),throwsA(isA<FeedException>().having((e)=>e.code,'code','forbidden')));expect(s.state.documents,isEmpty);
 });
 test('sequence gap is recoverable',(){
  final s=MemoryFeedStore(FeedState('t',0,{},{}));final i=FeedImporter(s);final p=Principal('t',{'p'});
  expect(()=>i.ingest(p,event(2,1,'x')),throwsA(isA<FeedException>().having((e)=>e.code,'code','gap')));
  expect(i.ingest(p,event(1,1,'x')).sequence,1);
 });
}
