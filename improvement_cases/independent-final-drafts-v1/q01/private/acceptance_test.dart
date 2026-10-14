import 'package:test/test.dart';
import 'package:quota_fixture/models.dart';
import 'package:quota_fixture/implementation.dart';
Matcher code(String s)=>throwsA(isA<AllocationException>().having((e)=>e.code,'code',s));
Batch batch(String id,int revision,List<Allocation> items)=>Batch(id,'t',revision,items);
const ctx=RequestContext('t','owner');
class CountingLedgerStore extends MemoryLedgerStore {
 int attempts=0;
 CountingLedgerStore(LedgerState state):super(state);
 @override void commit(LedgerState state,String id,String fingerprint,Receipt receipt){
  attempts++;super.commit(state,id,fingerprint,receipt);
 }
}
void expectStorageFailure(void Function() action,List<String> forbidden){
 Object? failure;
 try{action();}catch(error){failure=error;}
 expect(failure,isA<AllocationException>().having((e)=>e.code,'code','storage'));
 final exposed=failure.toString();
 for(final marker in forbidden){expect(exposed, isNot(contains(marker)));}
}
void main(){
 test('confirmed production decision rejects whole oversubscribed batch',(){
  final s=CountingLedgerStore(LedgerState('t',5,0,{'saved':2}));
  expect(productionShortagePolicy(),ShortagePolicy.atomic);
  final service=AllocationService(s,policy:productionShortagePolicy());
  expect(()=>service.allocate(ctx,batch('x',0,[const Allocation('a',2),const Allocation('b',2)])),code('shortage'));
  expect(s.state.allocations,{'saved':2});expect(s.state.revision,0);expect(s.attempts,0);
  expect(service.allocate(ctx,batch('x',0,[const Allocation('b',3)])).granted,{'b':3});expect(s.attempts,1);
 });
 test('alternative policy order and zero grants',(){
  final s=MemoryLedgerStore(LedgerState('t',3,0,{}));
  final r=AllocationService(s,policy:ShortagePolicy.partial).allocate(ctx,batch('x',0,[const Allocation('a',2),const Allocation('b',2),const Allocation('c',1)]));
  expect(r.granted,{'a':2,'b':1,'c':0});expect(s.state.remaining,0);
 });
 test('initially exhausted partial batch commits once and replays',(){
  final s=CountingLedgerStore(LedgerState('t',5,7,{'keep':5}));
  final svc=AllocationService(s,policy:ShortagePolicy.partial);
  final request=batch('empty',7,[const Allocation('a',2),const Allocation('b',3)]);
  final r=svc.allocate(ctx,request);
  expect(r.granted,{'a':0,'b':0});expect(r.revision,8);expect(s.state.revision,8);
  expect(s.state.allocations['keep'],5);expect(s.state.remaining,0);expect(s.attempts,1);
  final retry=AllocationService(s,policy:ShortagePolicy.partial).allocate(ctx,request);
  expect(retry.granted,r.granted);expect(retry.revision,8);expect(s.state.revision,8);expect(s.attempts,1);
 });
 test('replay survives unrelated commits and reconstruction',(){
  final s=MemoryLedgerStore(LedgerState('t',20,0,{}));
  final svc=AllocationService(s,policy:ShortagePolicy.atomic);final first=batch('x',0,[const Allocation('a',2)]);
  final r=svc.allocate(ctx,first);svc.allocate(ctx,batch('y',1,[const Allocation('b',3)]));
  final retry=AllocationService(s,policy:ShortagePolicy.atomic).allocate(const RequestContext('t','other'),first);
  expect(retry.revision,r.revision);expect(retry.granted,r.granted);expect(s.state.revision,2);
 });
 test('identity includes order units revision and policy',(){
  for(final variant in [batch('x',0,[const Allocation('b',1),const Allocation('a',1)]),batch('x',0,[const Allocation('a',2),const Allocation('b',1)]),batch('x',1,[const Allocation('a',1),const Allocation('b',1)])]){
   final s=MemoryLedgerStore(LedgerState('t',20,0,{}));final svc=AllocationService(s,policy:ShortagePolicy.atomic);
   svc.allocate(ctx,batch('x',0,[const Allocation('a',1),const Allocation('b',1)]));expect(()=>svc.allocate(ctx,variant),code('id_conflict'));
   expect(()=>AllocationService(s,policy:ShortagePolicy.partial).allocate(ctx,batch('x',0,[const Allocation('a',1),const Allocation('b',1)])),code('id_conflict'));
  }
 });
 test('authorization precedes replay conflict and invalid payload',(){
  final s=MemoryLedgerStore(LedgerState('t',20,0,{}));final svc=AllocationService(s,policy:ShortagePolicy.atomic);
  svc.allocate(ctx,batch('x',0,[const Allocation('a',1)]));
  expect(()=>svc.allocate(const RequestContext('other','owner'),batch('x',-1,[])),code('forbidden'));
  expect(()=>svc.allocate(const RequestContext('t','owner',canAllocate:false),batch('x',0,[const Allocation('a',5)])),code('forbidden'));
 });
 test('storage failure redacted retryable and preserves old receipt',(){
  final s=CountingLedgerStore(LedgerState('t',20,0,{}));final svc=AllocationService(s,policy:ShortagePolicy.atomic);
  svc.allocate(ctx,batch('old',0,[const Allocation('a',1)]));expect(s.attempts,1);s.failNextCommit=true;
  final request=batch('new',1,[const Allocation('sensitive_member_274',2)]);
  expectStorageFailure(()=>svc.allocate(ctx,request),['internal-storage-secret','sensitive_member_274']);
  expect(s.attempts,2);expect(s.state.revision,1);expect(s.state.allocations,{'a':1});
  expect(svc.allocate(ctx,request).revision,2);expect(s.attempts,3);
  expect(svc.allocate(ctx,batch('old',0,[const Allocation('a',1)])).revision,1);expect(s.attempts,3);
 });
 test('input and state boundary table',(){
  for(final b in [batch('',0,[const Allocation('a',1)]),batch('x',0,[const Allocation('a\n',1)]),batch('x',0,[const Allocation('a',0)]),batch('x',0,[const Allocation('a',1000001)]),batch('x',-1,[const Allocation('a',1)]),batch('x',0,List.generate(101,(i)=>Allocation('m$i',1)))]){
   final s=MemoryLedgerStore(LedgerState('t',200,0,{}));expect(()=>AllocationService(s,policy:ShortagePolicy.atomic).allocate(ctx,b),code('invalid'));expect(s.state.revision,0);
  }
  for(final state in [LedgerState('t',1,0,{'a':2}),LedgerState('t',1,0,{'bad!':0}),LedgerState('t',1,0,{'a':-1})]){
   expect(()=>AllocationService(MemoryLedgerStore(state),policy:ShortagePolicy.atomic).allocate(ctx,batch('x',0,[const Allocation('a',1)])),code('invalid'));
  }
 });
 test('stale is retryable and immutable results',(){
  final s=MemoryLedgerStore(LedgerState('t',20,3,{'keep':4}));final svc=AllocationService(s,policy:ShortagePolicy.atomic);
  expect(()=>svc.allocate(ctx,batch('x',2,[const Allocation('a',2)])),code('stale'));
  final r=svc.allocate(ctx,batch('x',3,[const Allocation('a',2)]));expect(s.state.allocations['keep'],4);
  expect(()=>r.granted['a']=10,throwsUnsupportedError);expect(()=>s.state.allocations['keep']=0,throwsUnsupportedError);
 });
}
