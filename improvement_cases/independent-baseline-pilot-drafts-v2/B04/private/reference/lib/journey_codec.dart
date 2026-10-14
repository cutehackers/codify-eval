import 'dart:convert';
import 'models.dart';
bool validStop(String s)=>RegExp(r'^[A-Z][A-Z0-9_-]{0,31}$').hasMatch(s);
String journeyKey(Rider r,String from,String to)=>[r.id,r.region,from,to,r.wheelchair?'step-free':'all'].map(Uri.encodeComponent).join('/');
bool validJourney(Journey j,Rider r,String from,String to,int now){
 return j.riderId==r.id && j.region==r.region && j.origin==from && j.destination==to &&
  j.fetchedAt>=0 && j.fetchedAt<=now && j.legs.isNotEmpty && j.legs.length<=8 &&
  j.legs.every((l)=>l.line.trim().isNotEmpty && l.line.length<=40 && l.minutes>0 && l.minutes<=180 && !l.cancelled && (!r.wheelchair || l.accessible));
}
Journey? decodeJourney(String raw){
 try {
  final o=jsonDecode(raw); if(o is! Map<String,dynamic> || (o['schema']!=1 && o['schema']!=2))return null;
  for(final k in ['riderId','region','origin','destination']){if(o[k] is! String)return null;}
  if(o['fetchedAt'] is! int || o['legs'] is! List)return null;
  final legs=<Leg>[];
  for(final v in o['legs'] as List){
   if(v is! Map<String,dynamic> || v['line'] is! String || v['minutes'] is! int)return null;
   final a=o['schema']==1?v['stepFree']:v['accessible'];
   if(a is! bool || (v.containsKey('cancelled') && v['cancelled'] is! bool))return null;
   legs.add(Leg(v['line'] as String,v['minutes'] as int,accessible:a,cancelled:v['cancelled']==true));
  }
  return Journey(o['riderId'] as String,o['region'] as String,o['origin'] as String,o['destination'] as String,o['fetchedAt'] as int,legs);
 }catch(_){return null;}
}
String encodeJourney(Journey j)=>jsonEncode({'schema':2,'riderId':j.riderId,'region':j.region,'origin':j.origin,'destination':j.destination,'fetchedAt':j.fetchedAt,'legs':j.legs.map((l)=>{'line':l.line,'minutes':l.minutes,'accessible':l.accessible,'cancelled':l.cancelled}).toList()});
