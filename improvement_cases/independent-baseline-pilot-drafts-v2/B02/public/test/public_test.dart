import 'package:test/test.dart';
import 'package:b02/models.dart';
import 'package:b02/labels.dart';
import 'package:b02/pass_parser.dart';
void main(){test('normal scan and label compatibility',(){
 expect(parsePass('museum-pass:Ab_12'),'Ab_12');
 expect(gateLabel(const GateDecision('entered')),'입장 처리되었습니다.');
});}
