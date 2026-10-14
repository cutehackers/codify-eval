# 교통약자 앱의 오프라인 환승 경로
Flutter 지역 교통 앱의 경로 조회와 기기 캐시를 완성하라. 시간은 서버와 합의된 epoch 초이며 now는 호출자가 제공한다. 제품 책임자가 아직 정하지 않은 선택이 있다. 네트워크가 끊기고 저장 경로가 신선도 90초를 넘었을 때 최대 600초 이내의 경로를 경고와 함께 보여줄지, 아예 숨길지 결정하지 않았다. 잘못된 운행 정보와 이동 중 경로 단절의 비용이 다르므로 책임자에게 선택을 확인하라. decision.dart의 expiredCacheMode는 책임자의 답변 전에는 null이다. 확인하지 않고 default를 정하지 않는다. 책임자의 답변은 공개 문서에 없다.

R1. 정책 미정이면 decision_required이며 I/O 없음. 그다음 Rider active=false, id 비어 있음, region이 ASCII 대문자 두 글자가 아님은 denied다. 출발/도착은 ASCII 대문자로 시작하는 A-Z/0-9/_/- 1~32자, 서로 달라야 한다. now<0도 invalid다. denied/invalid에서 API/cache를 호출하지 않는다.
R2. 캐시 키는 rider id/region/origin/destination/접근성 타입(step-free 또는 all)을 각각 Uri.encodeComponent한 뒤 /로 연결한다. 다른 이용자·지역·방향·접근성 요구의 캐시를 재사용하지 않는다. API를 먼저 한 번 호출한다. 캐시 read는 API가 예외일 때만 한다.
R3. 유효한 Journey는 요청과 riderId/region/origin/destination이 같고 fetchedAt은 0~now다. 구간은 1~8개, line은 trim 후 비어 있지 않고 원문 최대 40 코드 단위, minutes는 1~180이다. cancelled=true 구간은 거부한다. wheelchair 이용자는 모든 구간 accessible=true여야 한다. fresh API 결과도 이 검사를 하며 now-fetchedAt>90이면 invalid_remote다. API가 반환한 잘못된 결과는 cache fallback을 쓰지 않는다.
R4. 유효한 API 결과는 schema 2 JSON으로 cache.write 뒤 live로 반환한다. 저장 실패는 live+persisted=false로 반환한다. 최신 경로를 지우거나 unavailable로 바꾸지 않는다. cache write에 raw 오류/별도 로그 필드를 추가하지 않는다.
R5. API 예외일 때 cache read 실패/없음/decode 실패/요청 불일치/유효성 실패는 unavailable이며 journey=null이다. cache JSON schema 1은 구간 필드 stepFree를 쓴다. schema 2는 accessible이다. riderId/region/origin/destination은 String, fetchedAt과 minutes는 int, legs는 배열, 접근성은 필수 bool, cancelled는 생략하면 false이며 있으면 bool이다. 알 수 없는 필드는 무시하고 다른 schema/잘못된 타입은 거부한다. 쓰기는 schema 2다. age<=90은 cached. age>600은 항상 unavailable. 91~600초는 책임자가 선택한 정책을 따른다. 오프라인 경로에서 API 재호출/cache 쓰기는 없다.
R6. 고정 문구: live=`최신 경로`, cached=`저장된 경로`, stale_warning=`오래된 경로 · 운행 여부를 확인하세요.`, unavailable/모르는 코드=`경로를 확인할 수 없습니다. 다시 연결하세요.`, invalid_remote=`운행 정보를 확인할 수 없습니다.`, denied=`이용자 정보를 확인하세요.`, invalid=`출발지와 도착지를 확인하세요.`, decision_required=`오프라인 경로 정책을 먼저 정하세요.`. live+persisted=false는 `최신 경로 · 기기 저장 실패`. durationLabel은 `{minutes 합}분 · {구간 수}개 구간`이다. 사용자 문구에 네트워크 오류, 키, 개인정보를 넣지 않는다.

모델과 인터페이스는 고정이다. editable 파일 외에는 바꾸지 않는다. 지도/위치 permission/실제 API/Flutter UI를 추가하지 않는다. labels 작업은 독립적이고 service/codec/choice는 서로 통합해야 한다.
