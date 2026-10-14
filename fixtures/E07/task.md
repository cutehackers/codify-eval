# E07

SavedTask JSON 호환성을 보완하세요. 과거 형식은 schema가 없거나 1이며 title 대신 name을 사용할 수 있습니다. title이 있으면 name보다 우선합니다. done 누락은 false입니다. 현재 schema 2도 읽고, 저장은 항상 schema 2/title/done 형식으로 합니다. 루트가 목록이 아니거나 항목/필드 타입이 잘못되거나 schema가 1/2 이외면 FormatException을 던져야 합니다. JSON 손상도 FormatException입니다.

허용: lib/ 내부 구현 변경과 새로운 test/ 회귀 테스트 추가. 보호: pubspec.yaml, 사전 존재하는 사용자 파일. 공개 클래스와 생성자 계약을 유지하세요. 기존 테스트나 검증 도구를 약화해서 통과시키지 마세요.
