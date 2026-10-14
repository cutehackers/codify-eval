import 'dart:async';
import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/api.dart';
import 'package:fixture_app/implementation.dart';
class Cache implements FeedCache {
 String? value; final writes = <String>[]; bool fail=false; bool readFail=false;
 Cache([this.value]);
 Future<String?> read() async {if(readFail)throw StateError("cache read");return value;}
 Future<void> write(String v) async { if(fail) throw StateError('disk'); writes.add(v); value=v; }
}
class Transport implements FeedTransport {
 final Future<Page> Function(String?) handler; Transport(this.handler);
 Future<Page> fetch(String? c)=>handler(c);
}
class DelayedCache implements FeedCache {
 String? value; final writes=<String>[]; final pending=<Completer<void>>[];
 DelayedCache(this.value);
 Future<String?> read()async=>value;
 Future<void> write(String next)async {
  writes.add(next);final gate=Completer<void>();pending.add(gate);await gate.future;value=next;
 }
}
Entry e(String id,String title,int day)=>Entry(id,title,DateTime.utc(2026,1,day));
void main() {
 test('legacy restore normalizes duplicates and immutable snapshots',() async {
  final c=Cache(jsonEncode([{'id':'b','title':'old','updatedAt':'2026-01-02T09:00:00+09:00'},{'id':'a','title':'one','updatedAt':'2026-01-02T00:00:00Z'},{'id':'b','title':'new','updatedAt':'2026-01-02T00:00:00Z'}]));
  final f=FeedController(Transport((_)async=>const Page([],null)),c); await f.restore();
  expect(f.entries.map((x)=>x.id),['a','b']); expect(f.entries.last.title,'new'); expect(f.entries.last.updatedAt.isUtc,true);
  expect(()=>f.entries.add(e('z','z',1)),throwsUnsupportedError); expect(c.writes,isEmpty);
  c.value='{"version":2,"entries":[{"id":"valid","title":"v","updatedAt":"2026-01-01"},{"id":2}]}'; await f.restore(); expect(f.entries.map((x)=>x.id),['a','b']);
 });
 test('complete pagination migration and snapshots',() async {
  final c=Cache(); final calls=<String?>[];
  final f=FeedController(Transport((cursor)async {calls.add(cursor); return cursor==null?Page([e('x','old',1),e('y','y',3)],'n'):Page([e('x','new',2),e('x','equal-last',2)],null);}),c);
  final r=await f.refresh(); expect(r.state,RefreshState.applied); expect(calls,[null,'n']); expect(r.entries.map((x)=>x.id),['y','x']); expect(r.entries.last.title,'equal-last');
  final encoded=jsonDecode(c.value!); expect(encoded['version'],2); expect(encoded['entries'].length,2);
  expect(()=>r.entries.clear(),throwsUnsupportedError);
 });
 test('failure preserves restored state and prevents partial persistence',() async {
  final c=Cache('[{"id":"keep","title":"saved","updatedAt":"2026-01-01"}]');
  var mode=0; final f=FeedController(Transport((cursor) async {if(mode==0) return Page([e('partial','p',2)],'loop'); if(mode==1) throw StateError('network'); return const Page([],null);}),c);
  await f.restore(); final cycle=await f.refresh(); expect(cycle.state,RefreshState.failed); expect(f.entries.map((entry)=>entry.id),['keep']); expect(c.writes,isEmpty);
  mode=1; expect((await f.refresh()).state,RefreshState.failed); expect(f.entries.map((entry)=>entry.id),['keep']);
  mode=2; c.fail=true; expect((await f.refresh()).state,RefreshState.failed); expect(f.entries.map((entry)=>entry.id),['keep']);
  c.fail=false; expect((await f.refresh()).state,RefreshState.applied); expect(f.entries,isEmpty);
 });
 test('overtaken network generation cannot write or publish',() async {
  final old=Completer<Page>(); var count=0; final c=Cache();
  final f=FeedController(Transport((_) {count++; return count==1?old.future:Future.value(Page([e('latest','new',2)],null));}),c);
  final first=f.refresh(); final second=await f.refresh(); old.complete(Page([e('stale','old',1)],null));
  expect((await first).state,RefreshState.superseded); expect(second.state,RefreshState.applied); expect(f.entries.single.id,'latest'); expect(c.writes.length,1);
 });
 test('valid version two restore and strict invalid payload recovery',()async {
  final c=Cache('{"version":2,"entries":[{"id":"x","title":"old","updatedAt":"2026-01-01T00:00:00Z"},{"id":"x","title":"new","updatedAt":"2026-01-03T00:00:00Z"},{"id":"a","title":"other","updatedAt":"2026-01-02T00:00:00Z"}]}');
  final f=FeedController(Transport((_)async=>const Page([],null)),c);await f.restore();expect(f.entries.map((x)=>x.id),['x','a']);expect(f.entries.first.title,'new');
  for(final bad in ['not json','null','42','{}','{"version":3,"entries":[]}','{"version":2,"entries":{}}','[{"id":"x","title":"x","updatedAt":"not a date"}]','[{"id":3,"title":"x","updatedAt":"2026-01-01"}]','[{"id":"x","title":3,"updatedAt":"2026-01-01"}]','[{"id":"x","title":"x","updatedAt":3}]','[{"id":"x","title":"x"}]','[null]']) {
   c.value=bad;await f.restore();expect(f.entries.map((x)=>x.id),['x','a'],reason:bad);expect(c.writes,isEmpty);
  }
  c.readFail=true;await f.restore();expect(f.entries.first.title,'new');expect(c.writes,isEmpty);
  c.readFail=false;c.value='[]';await f.restore();expect(f.entries,isEmpty);
 });
 test('legacy unequal timestamps normalize and newest wins regardless of order',()async{
  final c=Cache('[{"id":"x","title":"new","updatedAt":"2026-01-03T00:00:00Z"},{"id":"x","title":"old","updatedAt":"2026-01-01T00:00:00Z"}]');
  final f=FeedController(Transport((_)async=>const Page([],null)),c);await f.restore();expect(f.entries.map((entry)=>entry.title),['new']);
 });
 test('transport view result and persisted rows are normalized and stable snapshots',()async{
  final local=DateTime(2026,1,4,9);var turn=0;final c=Cache();
  final f=FeedController(Transport((_)async {turn++;return Page(turn==1?[Entry('z','local',local),e('a','utc',2)]:[e('later','replacement',5)],null);}),c);
  final first=await f.refresh();expect(first.state,RefreshState.applied);expect(first.entries.every((x)=>x.updatedAt.isUtc),true);
  expect(jsonDecode(c.value!),{'version':2,'entries':[{'id':'z','title':'local','updatedAt':local.toUtc().toIso8601String()},{'id':'a','title':'utc','updatedAt':DateTime.utc(2026,1,2).toIso8601String()}]});
  final snapshot=f.entries;await f.refresh();expect(first.entries.map((x)=>x.id),['z','a']);expect(snapshot.map((x)=>x.id),['z','a']);expect(f.entries.single.id,'later');
 });
 test('view changes only after write and overtaken pending write never republishes',()async{
  final c=DelayedCache('[{"id":"saved","title":"saved","updatedAt":"2026-01-01"}]');var turn=0;
  final f=FeedController(Transport((_)async {turn++;return Page([e(turn==1?'old':'latest','item',turn+1)],null);}),c);await f.restore();
  final first=f.refresh();await Future<void>.delayed(Duration.zero);expect(c.writes.length,1);expect(f.entries.single.id,'saved');
  final second=f.refresh();await Future<void>.delayed(Duration.zero);expect(c.writes.length,2);expect(f.entries.single.id,'saved');
  c.pending[1].complete();final newer=await second;expect(newer.state,RefreshState.applied);expect(f.entries.single.id,'latest');
  c.pending[0].complete();expect((await first).state,RefreshState.superseded);expect(f.entries.single.id,'latest');
 });
 test('separate transport error preserves view and permits recovery',()async{
  var failed=true;final c=Cache('[{"id":"saved","title":"saved","updatedAt":"2026-01-01"}]');
  final f=FeedController(Transport((_)async {if(failed)throw StateError('transport');return Page([e('new','new',2)],null);}),c);await f.restore();expect((await f.refresh()).state,RefreshState.failed);expect(f.entries.map((entry)=>entry.id),['saved']);expect(c.writes,isEmpty);
  failed=false;expect((await f.refresh()).state,RefreshState.applied);expect(f.entries.map((entry)=>entry.id),['new']);
 });

 test('cache write failure preserves the full view and a later write recovers',()async{
  final c=Cache('[{"id":"saved","title":"saved","updatedAt":"2026-01-01"}]');
  final f=FeedController(Transport((_)async=>Page([e('replacement','fresh',2)],null)),c);await f.restore();
  c.fail=true;expect((await f.refresh()).state,RefreshState.failed);expect(f.entries.map((entry)=>entry.id),['saved']);expect(c.writes,isEmpty);
  c.fail=false;expect((await f.refresh()).state,RefreshState.applied);expect(f.entries.map((entry)=>entry.id),['replacement']);expect(c.writes.length,1);
 });
 test('cursor cycle alone is a failed whole refresh without partial storage',()async{
  final c=Cache('[{"id":"saved","title":"saved","updatedAt":"2026-01-01"}]');
  final f=FeedController(Transport((_)async=>Page([e('partial','partial',2)],'same')),c);await f.restore();
  expect((await f.refresh()).state,RefreshState.failed);expect(f.entries.map((entry)=>entry.id),['saved']);expect(c.writes,isEmpty);
 });

}
