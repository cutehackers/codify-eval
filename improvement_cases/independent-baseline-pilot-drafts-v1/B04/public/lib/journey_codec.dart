import 'models.dart';
bool validStop(String s)=>s.isNotEmpty;
String journeyKey(Rider r,String from,String to)=>'$from/$to';
bool validJourney(Journey j,Rider r,String from,String to,int now)=>true;
Journey? decodeJourney(String raw)=>null;
String encodeJourney(Journey j)=>'{}';
