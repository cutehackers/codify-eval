# 박물관 특별전 입장 게이트
Flutter 직원 앱의 QR 스캔 핵심을 구현하라. 네트워크 DTO와 저장소 인터페이스는 고정이다. 서버 enter는 원자적으로 재검사하므로 앱의 사전 검사만으로 입장을 성공 처리하면 안 된다.

R1. QR 형식은 `museum-pass:` 다음 ASCII A-Z/a-z/0-9/_/- 1~96자다. 공백, URI escape, 경로 구분자, query, control 문자, 다른 scheme은 invalid. 잘못된 QR은 backend와 history를 호출하지 않는다.
R2. session은 로그인 화면의 오래된 값일 수 있다. backend.staff(session.id)를 먼저 조회하라. null/비활성/role이 gate가 아님/venue가 session.venue와 다름은 denied다. staff 조회 실패는 unavailable이다. 이 경우 pass/enter/history를 호출하지 않는다.
R3. 최신 staff와 같은 venue의 pass만 허용한다. 없는 pass는 missing, 다른 venue는 denied, validThrough < now는 expired, used면 used다. 이 우선순위를 적용한다. 실패한 사전 검사에는 enter/history를 호출하지 않는다. 같은 시각의 validThrough는 유효하다.
R4. backend.enter에 최신 staff id, pass id, 최신 venue, now를 전달한다. 반환 코드는 entered/denied/expired/used/missing을 그대로 반환한다. 모르는 코드 또는 backend 예외는 unavailable이다. 원자 검사에서 실패한 결과를 이전 pass 조회로 덮어쓰지 않는다.
R5. entered에서만 history.append(venue, staffId, passId, now)를 호출한다. history 실패여도 입장은 완료된 상태이므로 entered + historySaved=false다. 사용자에게 서버/저장 오류, 원문 QR, 직원 ID를 노출하지 않는다.
R6. 고정 문구: entered=`입장 처리되었습니다.`, invalid=`입장권을 다시 스캔하세요.`, denied=`이 입장권을 처리할 권한이 없습니다.`, expired=`입장 시간이 지났습니다.`, used=`이미 사용한 입장권입니다.`, missing=`입장권을 찾을 수 없습니다.`, unavailable 또는 모르는 코드=`연결을 확인하고 다시 시도하세요.`. entered이면서 historySaved=false는 `입장 완료 · 기기 기록 저장 실패`다.

완전히 지정된 과제다. 실제 카메라, API 서비스, UI를 추가하지 않는다. parser/service는 함께 통합하고 독립 labels 작업은 선택적으로 위임할 수 있다.
