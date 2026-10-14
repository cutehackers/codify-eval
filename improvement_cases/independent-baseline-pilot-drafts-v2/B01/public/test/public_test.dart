import 'package:test/test.dart';
import 'package:b01/models.dart';
import 'package:b01/labels.dart';
void main() { test('normal Korean summary survives', () {
 expect(syncLabel(const SyncSummary(2,1,0)), '2건 전송 · 1건 재시도 대기 · 0건 확인 필요');
 expect(assetLabel('EQ-0001'),'EQ-0001');
}); }
