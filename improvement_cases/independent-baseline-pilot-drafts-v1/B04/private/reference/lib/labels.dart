import 'models.dart';
String journeyLabel(JourneyView v){
 if(v.code=='live'&&!v.persisted)return '최신 경로 · 기기 저장 실패';
 const texts={'live':'최신 경로','cached':'저장된 경로','stale_warning':'오래된 경로 · 운행 여부를 확인하세요.',
 'unavailable':'경로를 확인할 수 없습니다. 다시 연결하세요.','invalid_remote':'운행 정보를 확인할 수 없습니다.',
 'denied':'이용자 정보를 확인하세요.','invalid':'출발지와 도착지를 확인하세요.','decision_required':'오프라인 경로 정책을 먼저 정하세요.'};
 return texts[v.code]??texts['unavailable']!;
}
String durationLabel(List<Leg> legs)=> '${legs.fold<int>(0,(n,l)=>n+l.minutes)}분 · ${legs.length}개 구간';
