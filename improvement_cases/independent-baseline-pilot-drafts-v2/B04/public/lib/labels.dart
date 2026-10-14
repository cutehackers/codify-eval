import 'models.dart';
String journeyLabel(JourneyView v)=>v.code=='decision_required'?'오프라인 경로 정책을 먼저 정하세요.':'경로를 확인할 수 없습니다. 다시 연결하세요.';
String durationLabel(List<Leg> legs)=>'${legs.fold<int>(0,(n,l)=>n+l.minutes)}분 · ${legs.length}개 구간';
