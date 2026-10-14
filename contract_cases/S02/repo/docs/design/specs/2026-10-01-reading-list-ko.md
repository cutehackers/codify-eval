# 읽기 목록
- Contract ID: READING-LIST
- Contract Status: Approved
- Intent Status: Hardened
- Created: 2026-10-01
- Source: Explicit human instruction, initial agreed fixture
- Decision Records: docs/DECISIONS.md
- Glossary: docs/design/glossary.md

## Intent and Goals
- INT-01: 사용자가 읽을 항목을 저장하고 찾는다.
- GOAL-01: URL 항목을 목록에 저장한다.
- GOAL-02: 저장한 URL 항목을 URL로 찾는다.
- GOAL-03: 목록을 JSON 파일로 내보낸다.
## Scope
In scope: URL 추가, URL 검색, JSON 내보내기.
Non-goals: 로그인, 동기화, 내용 다운로드.
## Rules
- INV-01: URL은 저장 키이며 정확히 같은 URL은 하나만 저장된다.
- INV-02: 저장과 검색은 대소문자를 구분한다.
- INV-03: JSON 내보내기는 저장된 문자열을 그대로 보존한다.
## Acceptance
- FA-01: URL을 저장하면 목록에 하나가 보인다.
- FA-02: 같은 URL로 찾으면 저장된 항목이 반환된다.
- FA-03: 내보낸 JSON은 모든 항목을 원문 그대로 포함한다.
## Decisions
D-01 exact URL key, accepted by explicit human instruction.
## Open Decisions
None.
