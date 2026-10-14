import 'models.dart';
String syncLabel(SyncSummary s) => '${s.sent}건 전송 · ${s.retried}건 재시도 대기 · ${s.rejected}건 확인 필요';
String assetLabel(String asset) => asset;
