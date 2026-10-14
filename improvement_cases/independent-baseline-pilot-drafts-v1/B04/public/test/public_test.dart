import 'package:test/test.dart';
import 'package:b04/models.dart';
import 'package:b04/labels.dart';
void main(){test('journey summary compatibility',(){
 expect(durationLabel([const Leg('버스',12),const Leg('도보',3)]),'15분 · 2개 구간');
 expect(journeyLabel(const JourneyView('decision_required')),'오프라인 경로 정책을 먼저 정하세요.');
});}
