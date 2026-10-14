# 정비기사의 야외 작업 전송함
Flutter 정비 앱이 연결 불안정 지역에서 기록한 완료 보고를 순서대로 보낸다. 세 개의 editable Dart 파일을 완성하라. 모델과 Store/API 인터페이스를 변경하지 않는다. 기존 public 테스트도 유지한다.

R1. 유효한 기록은 비어 있지 않은 id/tenant, EQ-숫자4자리 asset, 양수 revision, trim 후 비어 있지 않은 note(최대 240개 Dart 문자열 코드 단위)를 가져야 한다. note의 NUL~BS, VT, FF, SO~US 제어문자는 거부한다. 다른 Unicode, 줄바꿈과 tab은 허용한다. 저장된 원문은 변경하지 않는다.
R2. flush는 입력 tenant의 pending만 저장 순서대로 처리한다. 다른 tenant와 sent/rejected 기록은 그대로 남긴다. 유효하지 않은 기록은 API 호출 없이 rejected로 저장한다. accepted만 sent로 저장한다. retryable 결과 또는 API 예외는 pending 유지, attempts 1 증가다. 나머지는 rejected다.
R3. deliveryKey는 tenant/id/revision의 각 문자열을 URI component로 인코딩한 뒤 /로 연결한다. 같은 revision의 재시도는 같은 키다. 여러 flush가 같은 Outbox에 동시에 호출되면 API/Store 작업까지 직렬 처리한다. 먼저 호출한 작업이 먼저 처리된다.
R4. 각 처리 결과를 atomic replace에 저장한 뒤 다음 기록을 시작한다. read 또는 replace 실패 시 중단하고 storageUnavailable을 반환한다. 실패한 replace는 summary에 포함하지 않는다. 이미 API가 성공했지만 저장 실패한 기록은 다음 flush에서 같은 키로 다시 보내어 서버 중복 방지에 맡긴다. 저장 실패 후 내부의 임시 상태를 다음 호출에 재사용하지 않는다.
R5. summary는 이번 호출이 성공적으로 저장한 sent/retried/rejected 수만 포함한다. 기기 저장 불가 표시: `기기에 저장할 수 없습니다. 다시 시도하세요.`. 그 외: `{sent}건 전송 · {retried}건 재시도 대기 · {rejected}건 확인 필요`. assetLabel은 형식에 맞는 asset은 원문, 나머지는 `장비 확인 필요`다.

이 과제는 완전히 지정되어 있다. 인증·네트워크 실서비스와 Flutter widget을 추가하지 말라. 동작 모듈과 독립 labels 모듈의 병렬 작업은 선택사항이다.
