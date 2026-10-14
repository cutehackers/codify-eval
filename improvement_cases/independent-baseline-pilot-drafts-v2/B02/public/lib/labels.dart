import 'models.dart';
String gateLabel(GateDecision d) => d.code=='entered' ? '입장 처리되었습니다.' : '연결을 확인하고 다시 시도하세요.';
