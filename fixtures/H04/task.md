# H04

설정 JSON을 이전 버전과 호환되게 읽으세요. version 누락 또는 1은 mode 필드를 사용할 수 있으며 theme이 있으면 우선합니다. theme/mode 누락은 system, scale 누락은 1.0입니다. version 2도 같은 기본값을 적용합니다. 저장은 항상 version 2/theme/scale입니다. 허용 theme은 light/dark/system, scale은 0.5~2.0의 유한한 숫자입니다. 잘못된 루트, 값 또는 지원하지 않는 version은 FormatException입니다.

허용: lib/ 내부 구현 변경과 새로운 test/ 회귀 테스트 추가. 보호: pubspec.yaml, 사전 존재하는 사용자 파일. 공개 클래스와 생성자 계약을 유지하세요. 기존 테스트나 검증 도구를 약화해서 통과시키지 마세요.
