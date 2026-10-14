import 'models.dart';
import 'journey_codec.dart';
import 'decision.dart';
class JourneyService {
 final JourneyApi api; final JourneyCache cache;
 JourneyService(this.api,this.cache);
 Future<JourneyView> load(Rider rider,String from,String to,int now)async{
  if(expiredCacheMode==null)return const JourneyView('decision_required');
  if(!rider.active || rider.id.isEmpty || !RegExp(r'^[A-Z]{2}$').hasMatch(rider.region))return const JourneyView('denied');
  if(!validStop(from)||!validStop(to)||from==to||now<0)return const JourneyView('invalid');
  final key=journeyKey(rider,from,to);
  Journey fresh;
  try {fresh=await api.fetch(rider,from,to);}catch(_){return _offline(rider,from,to,now,key);}
  if(!validJourney(fresh,rider,from,to,now)||now-fresh.fetchedAt>90)return const JourneyView('invalid_remote');
  try{await cache.write(key,encodeJourney(fresh));}catch(_){return JourneyView('live',journey:fresh,persisted:false);}
  return JourneyView('live',journey:fresh);
 }
 Future<JourneyView> _offline(Rider rider,String from,String to,int now,String key)async{
  String? raw;try{raw=await cache.read(key);}catch(_){return const JourneyView('unavailable');}
  if(raw==null)return const JourneyView('unavailable');
  final j=decodeJourney(raw);
  if(j==null||!validJourney(j,rider,from,to,now))return const JourneyView('unavailable');
  final age=now-j.fetchedAt;
  if(age<=90)return JourneyView('cached',journey:j);
  if(age<=600 && expiredCacheMode=='warn')return JourneyView('stale_warning',journey:j);
  return const JourneyView('unavailable');
 }
}
