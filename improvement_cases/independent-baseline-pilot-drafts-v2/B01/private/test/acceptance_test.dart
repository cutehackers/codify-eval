import 'dart:async';
import 'package:test/test.dart';
import 'package:b01/models.dart';
import 'package:b01/job_rules.dart';
import 'package:b01/outbox.dart';
import 'package:b01/labels.dart';
class Memory implements OutboxStore {
 List<Job> jobs; int writes=0; int? failAt; bool readFail=false;
 Memory(this.jobs);
 Future<List<Job>> read() async { if(readFail) throw StateError('disk'); return List.of(jobs); }
 Future<void> replace(List<Job> next) async {
  writes++; if(writes==failAt) throw StateError('disk'); jobs=List.of(next);
 }
}
class Api implements RepairApi {
 final List<String> calls=[],keys=[]; final Map<String,SendResult> answers;
 Completer<void>? hold;
 Api([this.answers=const {}]);
 Future<SendResult> send(Job j,String key) async {
  calls.add(j.id); keys.add(key);
  if(hold!=null) await hold!.future;
  if(j.id=='throw') throw StateError('token:do-not-expose');
  return answers[j.id]??const SendResult('accepted');
 }
}
Job j(String id,{String tenant='a',String state='pending',String note='교체 완료'}) =>
 Job(id,tenant,'EQ-0001',note,state:state);
void main() {
 test('r1 rejects boundaries but preserves ordinary text',(){
  for(final note in ['', ' '*3, 'x'*241, 'a\x00b', 'a\x0Bb']) expect(validJob(j('x',note:note)),false);
  expect(validJob(j('x',note:'한글\n\t✅')),true);
  expect(validJob(const Job('x','a','EQ-12','done')),false);
  expect(validJob(const Job('x','a','EQ-0001','done',revision:0)),false);
 });
 test('r2 scope sequence and outcomes',() async {
  final m=Memory([j('one'),j('foreign',tenant:'b'),j('retry'),j('throw'),j('denied'),j('invalid',note:''),j('old',state:'sent')]);
  final a=Api({'retry':const SendResult('busy',retryable:true),'denied':const SendResult('permission')});
  final s=await Outbox(m,a).flush('a');
  expect(a.calls,['one','retry','throw','denied']);
  expect([s.sent,s.retried,s.rejected],[1,2,2]);
  expect(m.jobs.map((x)=>x.state).toList(),['sent','pending','pending','pending','rejected','rejected','sent']);
  expect(m.jobs[2].attempts,1); expect(m.jobs[3].attempts,1); expect(m.jobs[1].attempts,0);
 });
 test('r3 serialized concurrent flush and stable scoped key',() async {
  final m=Memory([j('id/1',tenant:'team/a')]); final a=Api()..hold=Completer<void>(); final o=Outbox(m,a);
  final f=o.flush('team/a'); final g=o.flush('team/a');
  await Future<void>.delayed(Duration.zero); expect(a.calls.length,1);
  a.hold!.complete(); await f; final s=await g;
  expect(a.calls.length,1); expect(s.sent,0); expect(a.keys.single,'team%2Fa/id%2F1/1');
  expect(deliveryKey(const Job('id/1','team/a','EQ-0001','done',revision:2)),'team%2Fa/id%2F1/2');
 });
 test('r4 durable checkpoint recovery and no later side effect',() async {
  final m=Memory([j('one'),j('two'),j('three')])..failAt=2; final a=Api(); final o=Outbox(m,a);
  final s=await o.flush('a'); expect([s.sent,s.retried,s.rejected],[1,0,0]); expect(s.storageUnavailable,true);
  expect(a.calls,['one','two']); expect(m.jobs[1].state,'pending');
  m.failAt=null; await o.flush('a'); expect(a.calls,['one','two','two','three']); expect(a.keys[1],a.keys[2]);
  m.readFail=true; final z=await o.flush('a'); expect(z.storageUnavailable,true); expect(a.calls.length,4);
 });
 test('r5 labels do not show identifiers or errors',(){
  expect(syncLabel(const SyncSummary(3,2,1)),'3건 전송 · 2건 재시도 대기 · 1건 확인 필요');
  expect(syncLabel(const SyncSummary(0,0,0,storageUnavailable:true)),'기기에 저장할 수 없습니다. 다시 시도하세요.');
  expect(assetLabel('password=bad'),'장비 확인 필요');
 });
}
