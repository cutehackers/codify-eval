import 'models.dart';
String syncLabel(SyncSummary s) => s.storageUnavailable ? '기기에 저장할 수 없습니다. 다시 시도하세요.' :
    '${s.sent}건 전송 · ${s.retried}건 재시도 대기 · ${s.rejected}건 확인 필요';
String assetLabel(String asset) => RegExp(r'^EQ-[0-9]{4}$').hasMatch(asset) ? asset : '장비 확인 필요';
