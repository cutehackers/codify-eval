import 'models.dart';
String gateLabel(GateDecision d) {
 const labels={'entered':'입장 처리되었습니다.','invalid':'입장권을 다시 스캔하세요.',
 'denied':'이 입장권을 처리할 권한이 없습니다.','expired':'입장 시간이 지났습니다.',
 'used':'이미 사용한 입장권입니다.','missing':'입장권을 찾을 수 없습니다.',
 'unavailable':'연결을 확인하고 다시 시도하세요.'};
 if(d.code=='entered' && !d.historySaved) return '입장 완료 · 기기 기록 저장 실패';
 return labels[d.code]??labels['unavailable']!;
}
