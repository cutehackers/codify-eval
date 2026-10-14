import 'dart:convert';
import 'package:test/test.dart';
import 'package:b04/models.dart';
import 'package:b04/journey_codec.dart';
import 'package:b04/decision.dart';
import 'package:b04/journey_service.dart';
import 'package:b04/labels.dart';
const branch=String.fromEnvironment('OWNER_BRANCH');
const unresolvedDecision=bool.fromEnvironment('UNRESOLVED_DECISION');
const rider=Rider('u/1','KR',wheelchair:true);
Journey route({int at=1000,String uid='u/1',String region='KR',String from='A',String to='B',bool accessible=true,bool cancelled=false})=>Journey(uid,region,from,to,at,[Leg('101번',20,accessible:accessible,cancelled:cancelled)]);
class Api implements JourneyApi {
 bool fail=false; Journey value=route(); int calls=0;
 Future<Journey> fetch(Rider r,String from,String to)async{calls++;if(fail)throw StateError('secret');return value;}
}
class Cache implements JourneyCache {
 String? raw=encodeJourney(route()); bool failRead=false,failWrite=false;int reads=0,writes=0;String? key;
 Future<String?> read(String k)async{reads++;key=k;if(failRead)throw StateError('secret');return raw;}
 Future<void> write(String k,String value)async{key=k;if(failWrite)throw StateError('secret');writes++;raw=value;}
}
Future<JourneyView> offline(Journey j,int now)async{final a=Api()..fail=true;final c=Cache()..raw=encodeJourney(j);return JourneyService(a,c).load(rider,'A','B',now);}
void main(){
 if(unresolvedDecision){
  test('unresolved decision blocks every cache and network operation',()async{
   expect(expiredCacheMode,null);
   final a=Api();final c=Cache();final before=c.raw;
   final result=await JourneyService(a,c).load(rider,'A','B',1000);
   expect(result.code,'decision_required');expect(result.journey,null);
   expect(a.calls,0);expect(c.reads,0);expect(c.writes,0);expect(c.raw,before);
  });
  return;
 }
 test('qualification owner branch is admitted',(){expect(['warn','hide'],contains(branch));});
 test('r1 invalid requests do not touch IO',()async{
  for(final r in [const Rider('u','KR',active:false),const Rider('','KR'),const Rider('u','kr')]){final a=Api();final c=Cache();expect((await JourneyService(a,c).load(r,'A','B',1000)).code,'denied');expect(a.calls+c.reads+c.writes,0);}
  for(final stops in [['a','B'],['A','A'],['A/1','B'],['A','B '*20]]){final a=Api();final c=Cache();expect((await JourneyService(a,c).load(rider,stops[0],stops[1],1000)).code,'invalid');expect(a.calls+c.reads+c.writes,0);}
  final a=Api();final c=Cache();expect((await JourneyService(a,c).load(rider,'A','B',-1)).code,'invalid');expect(a.calls+c.reads+c.writes,0);
 });
 test('r2 isolated directional accessible keys and API precedence',()async{
  expect(journeyKey(rider,'A','B'),'u%2F1/KR/A/B/step-free');
  final keys=[journeyKey(rider,'A','B'),journeyKey(const Rider('u/2','KR',wheelchair:true),'A','B'),journeyKey(const Rider('u/1','JP',wheelchair:true),'A','B'),journeyKey(rider,'B','A'),journeyKey(const Rider('u/1','KR'),'A','B')];expect(keys.toSet().length,5);
  final a=Api();final c=Cache();expect((await JourneyService(a,c).load(rider,'A','B',1000)).code,'live');expect(a.calls,1);expect(c.reads,0);expect(c.key,keys.first);
 });
 test('r3 unauthorized or unsafe live routes never fallback',()async{
  for(final j in [route(uid:'foreign'),route(region:'JP'),route(from:'C'),route(to:'C'),route(at:1001),route(at:909),route(accessible:false),route(cancelled:true),Journey('u/1','KR','A','B',1000,[]),Journey('u/1','KR','A','B',1000,[const Leg('x',0)])]){
   final a=Api()..value=j;final c=Cache();final v=await JourneyService(a,c).load(rider,'A','B',1000);expect(v.code,'invalid_remote');expect(v.journey,null);expect(c.reads+c.writes,0);
  }
  expect(validJourney(route(at:910),rider,'A','B',1000),true);
  expect(validJourney(Journey('u/1','KR','A','B',1000,List.filled(9,const Leg('x',1))),rider,'A','B',1000),false);
 });
 test('r4 storage failure preserves usable live result',()async{
  final a=Api();final c=Cache()..failWrite=true;final v=await JourneyService(a,c).load(rider,'A','B',1000);expect(v.code,'live');expect(v.persisted,false);expect(v.journey!.legs.single.minutes,20);expect(journeyLabel(v),'최신 경로 · 기기 저장 실패');
  final cache=Cache();await JourneyService(Api(),cache).load(rider,'A','B',1000);final out=jsonDecode(cache.raw!);expect(out['schema'],2);expect(out['legs'][0]['accessible'],true);expect(out['legs'][0].containsKey('stepFree'),false);
 });
 test('r5 legacy codec types cache isolation and failures',()async{
  final old=jsonDecode(encodeJourney(route())) as Map<String,dynamic>;old['schema']=1;old['legs'][0]['stepFree']=old['legs'][0].remove('accessible');
  expect(decodeJourney(jsonEncode(old))!.legs.single.accessible,true);
  for(final schema in [1,2]){
   final omitted=jsonDecode(encodeJourney(route())) as Map<String,dynamic>;
   omitted['schema']=schema;
   final leg=omitted['legs'][0] as Map<String,dynamic>;
   if(schema==1)leg['stepFree']=leg.remove('accessible');
   leg.remove('cancelled');expect(decodeJourney(jsonEncode(omitted))!.legs.single.cancelled,false);
   leg['cancelled']=null;expect(decodeJourney(jsonEncode(omitted)),null);
   final a=Api()..fail=true;final c=Cache()..raw=jsonEncode(omitted);final before=c.raw;
   final view=await JourneyService(a,c).load(rider,'A','B',1000);
   expect(view.code,'unavailable');expect(view.journey,null);expect(a.calls,1);expect(c.writes,0);expect(c.raw,before);
  }
  for(final patch in [{'schema':5},{'fetchedAt':1000.5},{'riderId':1},{'legs':[]},{'legs':[{'line':'101','minutes':20,'stepFree':'true'}]}]){
   final copy=jsonDecode(jsonEncode(old)) as Map<String,dynamic>;copy.addAll(patch);final a=Api()..fail=true;final c=Cache()..raw=jsonEncode(copy);expect((await JourneyService(a,c).load(rider,'A','B',1000)).code,'unavailable');expect(c.writes,0);expect(a.calls,1);
  }
  for(final j in [route(uid:'other'),route(at:1001),route(accessible:false),route(cancelled:true)]){final v=await offline(j,1000);expect(v.code,'unavailable');expect(v.journey,null);}
  for(final state in ['readFailure','missing','badJson']){final a=Api()..fail=true;final c=Cache();if(state=='readFailure')c.failRead=true;if(state=='missing')c.raw=null;if(state=='badJson')c.raw='token=secret';expect((await JourneyService(a,c).load(rider,'A','B',1000)).code,'unavailable');expect(c.writes,0);expect(a.calls,1);}
 });
 test('r5 owner policy obeys inclusive age boundaries and hard ceiling',()async{
  expect((await offline(route(at:910),1000)).code,'cached');
  for(final at in [909,400]){final v=await offline(route(at:at),1000);expect(v.code,branch=='warn'?'stale_warning':'unavailable');expect(v.journey==null,branch!='warn');}
  final tooOld=await offline(route(at:399),1000);expect(tooOld.code,'unavailable');expect(tooOld.journey,null);
  expect((await offline(route(at:1000),1000)).code,'cached');
 });
 test('r6 presentation redacts diagnostics and sums legs',(){
  const texts={'live':'최신 경로','cached':'저장된 경로','stale_warning':'오래된 경로 · 운행 여부를 확인하세요.','unavailable':'경로를 확인할 수 없습니다. 다시 연결하세요.','invalid_remote':'운행 정보를 확인할 수 없습니다.','denied':'이용자 정보를 확인하세요.','invalid':'출발지와 도착지를 확인하세요.'};
  for(final e in texts.entries)expect(journeyLabel(JourneyView(e.key)),e.value);
  expect(journeyLabel(const JourneyView('secret=token')),texts['unavailable']);expect(durationLabel([]),'0분 · 0개 구간');
 });
}
