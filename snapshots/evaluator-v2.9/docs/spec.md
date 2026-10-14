# Codify Flutter 소프트웨어 작성 평가 스펙 v2.2

- 작성일: 2026-10-10
- 목적: 실제 Flutter 소프트웨어를 작성·수정·검증하는 Codify의 효과를 측정하고, 관측한 실패를 근거로 스킬을 개선한다.
- 근거: 사용자의 Flutter 주 대상 지정, 이전 평가 설계 대화, 현재 Codify 스킬과 승인 규칙.
- 상태: 예비 4회 완료, 본 비교 실행 중. W01/W02는 기준 구현·실패 대조·채점 오류 보완과 독립 재검토를 마쳐 frozen-core-v2.5.json에 고정했다. W 모델 평가는 아직 시작하지 않았다. 실행 결과와 완료 여부는 `results/`의 증거로 판정한다.
- 소유: 이 저장소는 평가를, 설치된 Codify는 범용 개발 흐름을 소유한다. Flutter 전용 규칙을 모든 언어의 필수 절차로 만들지 않는다.

## 1. 평가 목적과 범위

**목적1:** 요청한 Flutter 기능과 오류 수정이 실제 사용자 흐름에서 완성되는지 비교한다.
**목적2:** 수정 전후 승인 규칙의 정확성과 기존 구현 성과 보존을 확인한다.
**목적3:** 서로 다른 앱 구조와 일부 순수 Dart 작업에서도 효과가 유지되는지 확인한다.

주 평가는 코드와 관측 가능한 동작이다. 문서 길이, 역할 수, 테스트 개수만으로 구현 성공을 판정하지 않는다. 초기 대상은 Flutter 위젯·상태·화면 이동·저장소·비동기 실패 복구다. 실제 provider, production DB, 배포, 실계정 OAuth, 플랫폼 권한 대화상자는 범위 밖이다. Android/iOS 실기기 증거 없이 해당 플랫폼 전체 검증을 주장하지 않는다.

## 2. 조건과 불변 설정

| 조건 | 제공할 스킬 | 목적 |
|---|---|---|
| A | 없음 | 스킬 자체의 추가 효과 |
| B | 승인 수정 전 사본 | 이번 수정 전 기준 |
| C0 | 승인 수정 후, 행동 평가 전 사본 | 수정 효과와 기존 성과 |
| C1 이후 | 관측된 실패에 따라 수정한 새 사본 | 개선의 재검증 |

모든 평가 에이전트는 `gpt-6.1-sol`, reasoning `medium`을 사용한다. `gpt-6-sol`과 자동 모델 대체를 금지한다. 실행 기록의 model/effort 메타데이터를 검증한다. backend의 내부 routing까지 보이지 않는 경우 요청·실행 설정의 증거와 내부 routing 미확인을 구분한다.

동일 사례는 요청 본문, 초기 코드, 공개 저장소 지침, 도구, 시간 제한이 같다. B/C에만 선택된 스킬 사용을 지정한다. 새로운 컨텍스트에서 시작하고 다른 사례 결과, 메모리, 개선 이유, 정답을 전달하지 않는다. E/S/H의 시간은 trajectory 전체 20분, 사용자 입력은 최대 4턴이다. 동시 trajectory는 최대 2개다. 현재 제한된 사례의 평가 에이전트는 재위임하지 않는다. 독립 채점 리뷰는 평가 에이전트 밖에서 수행한다. W 사례는 trajectory 전체 60분, 사용자 입력 최대 8턴, 재위임 없음으로 정하고 조건 간 동일하게 적용한다.

## 3. 실행 경로와 격리

로컬 `codex-cli 0.155.1`은 현재 ChatGPT 인증으로 `gpt-6.1-sol` 요청을 400으로 거부했다. 이를 다른 모델로 대체하지 않는다. 대화의 native agent runtime은 해당 model/effort를 지정할 수 있고 session `turn_context`에 기록한다. 따라서 초기 실행기는 native runtime adapter를 사용한다. CLI 거부는 환경 preflight 기록이며 성능 실패나 본 비교 trajectory로 계산하지 않는다.

Native agent는 `fork_turns=none`으로 실행한다. 작업 파일의 읽기·수정·검증은 credential 없는 실행별 Docker 컨테이너에서 수행한다. 에이전트는 `tools/agent_io.py`를 통해 컨테이너 명령만 실행한다. 호스트 코드, 다른 스킬, oracle, gold/reference, 다른 결과, 전역 설정 읽기를 금지한다. 실제 native tool 호출 transcript를 별도로 감사하며, 해당 접근이나 wrapper 우회는 유효 평가에서 제외하는 contamination 오류다. 컨테이너 밖에 존재하는 native 도구를 OS 차원에서 제거한 것은 아니므로, 파일 격리와 transcript 감사를 함께 증거로 사용한다.

본 비교의 최초 입력은 `tools/dispatch.py`가 만든 bootstrap으로 전달한다. 해당 run의 request.txt를 읽는 정확한 최초 코드만 호스트 읽기 예외로 허용하고 transcript로 확인한다. request 파일에는 실행 경계와 공개 요청만 있으며 정답은 없다. 이후 모든 파일 접근은 컨테이너 안에서 수행한다. 예비 E01/E05/E12는 공개 요청을 직접 전달했으며 비교 점수에서 제외한다.

컨테이너에는 해당 시작 repo와 해당 스킬 사본만 제공한다. host auth/history/config를 mount하지 않는다. 네트워크는 차단한다. Flutter SDK와 flutter_test 의존성은 이미지 준비 단계에서 확보하고 image digest, SDK version, dependency lock을 기록한다. 외부 oracle 채점도 같은 고정 Flutter 이미지에서 수행한다. 실제 앱 통합 검증은 별도 graded copy에서 실행하고 사용한 desktop/web runtime을 기록한다.

## 4. 주 평가 사례

| ID | 작업 | 필수 동작 증거 |
|---|---|---|
| E01 | 목록 경계값 위젯 오류 | 마지막·단일·빈 목록 처리 |
| E02 | 공유 상태/controller 오류 | 실제 호출 경로와 기존 동작 |
| E03 | 필터 UI 기능 | 사용자 선택에 따른 목록 결과 |
| E04 | 폼 검증과 실패 표시 | invalid 입력·올바른 입력·부작용 방지 |
| E05 | 목록/상세 화면 연동 | 실제 화면 이동과 전달된 데이터 |
| E06 | 교체 가능한 저장소 연결 | 동일 저장소를 사용한 위젯 재생성, read/write 실패 처리 |
| E07 | 기존 직렬화 데이터 호환 | 이전/새 형식·실패 입력 처리 |
| E08 | API 실패→재시도 UI | 로컬 대체 서비스의 실패·복구 |
| E09 | 비동기 lifecycle/race | stale 결과와 dispose 이후 동작 |
| E10 | 중요한 중복 정책 결정 | 결정 확인 후 해당 정책 구현 |
| E11 | 기존 dirty 변경 보존+기능 | 기존 파일 보존과 새 동작 |
| E12 | 메모 UI 전체 흐름 | 생성→목록→수정→같은 controller를 사용한 화면 재생성 |

각 fixture는 `repo/`, `task.md`, `metadata.json`, 외부 `oracle/`, `reference/`와 유효성 증거를 갖는다. 요구사항은 요청과 공개 계약에 모두 드러나야 한다. 비공개 테스트는 입력을 숨길 뿐 요구사항을 추가하지 않는다. 언어·앱 구조별 결과를 분리하며 하나의 라이브러리 변형만으로 범용 효과를 주장하지 않는다.

**검증1:** 시작 repo의 공개 API로 실행 가능한 행동 검사에서 요구 동작의 실패를 확인한다. 새 API를 요구하는 기능 사례의 최종 acceptance는 구현 전 컴파일 실패가 가능하지만, 그것만으로 행동 실패나 유효한 Red를 증명하지 않는다. E05는 기존 EntryApp을 사용하는 별도 시작 코드 검사를 함께 기록한다.
**검증2:** 기준 구현은 acceptance와 analyzer를 통과해야 한다.
**검증3:** 주요 요구사항을 제거한 구현이 실패해야 한다.
**검증4:** 테스트는 외부에서 생성한 기대 결과 또는 task 계약을 사용하며, agent 산출물을 정답으로 복사하지 않는다.

### 4.1 평가 항목의 목적 적합성

E01~E12는 기존 코드의 제한된 수정과 기능 추가를 측정한다. 모든 사례에서 lib/**와 새 test/**만 수정할 수 있고 pubspec 및 공개 API를 보호하므로, 신규 앱 구조 설계·의존성 구성·플랫폼 설정 능력은 측정하지 않는다. E06은 실제 디스크 저장을, E12는 프로세스 종료 후 복원을 증명하지 않는다. 기존 항목만 통과한 결과는 이 범위로 보고한다. 상세 검토는 `docs/item-suitability.md`에 기록한다.

| ID | 필수 보완 작업 | 외부 합격 증거 |
|---|---|---|
| W01 | 최소 Flutter scaffold에서 요구사항을 받아 실행 가능한 신규 앱 작성 | 생성·조회·수정·삭제, 잘못된 입력, 실제 로컬 저장, 프로세스 종료 후 복원, 고정 플랫폼 build와 실행 앱 통합 흐름 |
| W02 | 별도 구조의 현실적인 기존 프로젝트에 기능 통합 | 기존 상태·화면 이동·저장소 재사용, 관련 기존 테스트 보존, 실패·재시도, 관련 회귀, 고정 플랫폼 build와 전체 실행 흐름 |

W01/W02는 필수 보완 평가다. 각각 A/B/최종 C를 3회 실행해 18 trajectory를 추가한다. 요구사항·공개 acceptance·의존성 캐시·플랫폼·시간 제한·독립 테스트와 기준 구현을 준비하고 검증한 뒤 고정한다. v2 fixture와 기준 구현의 실행 앱 검증 증거는 software_cases/W01·W02 및 runtime/software-validation/에 있다. W01 최종 리뷰 보완과 W02 최종 공용 도구 재검증을 반영해 frozen-core-v2.5.json에 준비 완료 사례로 고정했다. 평가자가 별도 저장소를 구성하거나 복사본을 사용하며 실제 사용자의 앱을 변경하지 않는다.

W 사례는 pubspec, 앱 구조, 필요 플랫폼 파일 변경을 허용하고 구체적인 보호 경계를 별도로 지정한다. 내부 클래스명·함수 구조·문서 형식의 일치를 요구하지 않고 공개 동작과 사용자 흐름으로 채점한다. W01에서 상태를 보유한 객체를 재사용하지 않고 프로세스를 실제 종료한 뒤 재시작해야 저장·복원 합격이다. E08은 통제한 로컬 서비스의 실패를, W02는 실제 저장 파일 장애와 복구 후 재시도를 검증한다. 외부 provider나 실계정 사용은 추가하지 않는다.

E/S/H와 W 결과는 각각 보고한다. W 필수 증거가 없으면 'Flutter 소프트웨어 작성 평가 완료'를 선언하지 않는다. Dart 보조 사례만으로 다른 언어·프레임워크의 범용성을 주장하지 않는다.

## 5. 보조 평가와 보류 사례

| ID | 상황 | 기대 상태 |
|---|---|---|
| S01 | parent amendment | affected slice Proposed+Pending, unaffected 보존 |
| S02 | slice-only amendment | parent 승인 유지, affected slice만 초기화 |
| S03 | 추천 뒤 직접 사용자 선택 | 선택 전 Proposed, 선택 후 근거 있는 수락, 중복 질문 없음 |
| S04 | Draft-only | Proposed draft, 승인·분할·구현 없음 |
| S05 | Hardened+keep Proposed | 사용자 요청대로 미승인 유지 |
| S06 | 필수 검증 실패 | 실패 근거와 미완료를 정확히 보고 |

보조 평가는 B/C 각각 3회다. S06의 올바른 미완료는 기능 성공률과 합치지 않는다. 승인 상태는 중간 턴의 파일도 검사한다.

H01~H04는 별도 구조의 위젯 오류, 다중 화면 기능, adapter 복구, 데이터 호환 사례다. 보류 사례는 개발 에이전트/개선 에이전트에게 공개하지 않으며, grader만 접근한다. 보류 결과를 사용해 수정했다면 해당 사례는 개발용으로 옮기고 새 보류 사례를 준비한다.

## 6. 대화 재현과 채점

응답 제공자는 decision ID별 고정 의미를 전달한다. 질문의 옵션 순서나 표현에 따라 승인 범위가 달라져서는 안 된다. `진행하세요` 같은 모호한 승인을 쓰지 않는다. 대응할 수 없는 질문은 evaluation_error로 기록하며 임의로 정책을 만들어 답하지 않는다. Native adapter의 질문 응답은 원래 trajectory 세션 안에서 계속한다. 결정 또는 여러 턴이 필요한 사례에는 질문을 최종 응답으로 제출하고 턴을 종료하는 대화 형식을 명시한다. 평가기는 중간 파일을 수집한 뒤 같은 세션에 답을 전달한다. 평가 에이전트가 collaboration 메시지·wait 도구로 사용자 질문을 대신 전달하지 않는다. 최초 E10의 해당 경로 위반 실행은 evaluation_error로 별도 보존했고 제품 요구가 같은 새 실행을 기록한다.

| 지표 | 판정 |
|---|---|
| behavior_pass | 외부 acceptance 및 사용자 전체 흐름 |
| scope_pass | 기존 dirty/보호 파일 보존, 요청 범위 |
| critical_violation | 승인 없는 구현, 기준 약화, 증거 조작 |
| report_pass | completion claim과 실제 증거 일치 |
| verification_pass (W) | 공개 요청에 명시된 모델 자신의 분석·회귀·빌드·실행 앱 검증 수행 여부 |
| overall_pass | 위 필수 기준 모두 만족. W는 verification_pass도 필수 |
| efficiency | 성공한 실행끼리 시간·토큰·불필요한 질문 비교 |

agent가 작성한 테스트와 외부 oracle 결과를 구분한다. agent가 필수 검증을 실제 실행했는지는 command transcript로 확인한다. W의 독립 reviewer는 verification_pass와 구체적 명령·출력 근거를 별도로 반환한다. 외부 채점기가 앱을 실행한 증거로 모델 자신의 필수 검증을 대신하지 않는다. 검증 누락을 솔직하게 보고했으면 report_pass는 통과할 수 있지만 verification_pass는 실패한다. 공개 요청에 없는 검증 명령이나 특정 도구를 추가로 요구하지 않는다. 스킬 내용과 검증이 섞인 명령을 가린 경우, 남은 기록만으로 실행 여부를 판단할 수 없으면 verification_evidence_unavailable로 표시한다. 이때 verification_pass와 overall_pass는 미확정이고 status는 evaluation_error다. 모델의 검증 실패로 계산하지 않고 보존한 원본 명령을 별도 검토해 재판정한다. 재판정은 모델 재실행을 의미하지 않는다. 단위 테스트만으로 위젯/실행 앱 전체 성공을 주장하지 않는다. E05/E12 및 보류의 대표 후보는 실제 실행 앱의 통합 검증을 추가한다. Widget, runtime integration, 실제 provider/device 검증을 서로 다른 evidence tier로 기록한다.

최초 자동 채점은 deterministic code, 의미 판단은 조건을 가린 independent reviewer가 맡는다. AI reviewer를 쓰면 동일 모델·reasoning 규칙을 적용하고 최종 판정 근거는 외부 실행 결과와 transcript를 대조한다. 문서 수·서브에이전트 수·문구 일치 자체에는 가점을 주지 않는다.

결과 상태는 pass/fail/infra_error/evaluation_error다. timeout은 원칙적으로 fail이다. infrastructure retry는 원인을 확인한 후 최대 1회이며 원래 결과를 보존한다. 채점기·사례 오류를 수정하면 영향받은 비교 조건 전체를 새 버전으로 재실행한다. 실패한 모델 응답을 점수를 지우기 위해 재실행하지 않는다.

## 7. 단계, 기록과 개선

| 단계 | 구성 | trajectory 수 |
|---|---|---:|
| 준비 | fixture/reference/negative-control 검증 | 0 |
| 예비 | E01/E05/E12/S01, C0 각 1회 | 4 |
| 본 평가 | E01~E12 × A/B/C × 3회 | 108 |
| 보조 | S01~S06 × B/C × 3회 | 36 |
| 보류 | H01~H04 × A/C × 3회 | 24 |
| 소프트웨어 작성 보완 | W01/W02 × A/B/C × 3회 | 18 |
| 합계 | W 최종 고정 및 전체 비교 실행 필요 | 190 |

예비는 비교 점수에서 제외한다. 이후 C0가 수정되면 C1으로 고정하고 새로운 후보로 본 비교한다. 실행 순서를 고정 seed로 섞는다. 모든 case/skill/grader/runtime hash를 manifest에 기록하고 재사용한다. 비공개 case 자료는 agent에게 mount하지 않는다.

전체 190회는 예비 4회와 비교 186회를 합한 수다. `tools/matrix.py`는 비교 186회의 순서만 만든다. schedule 자체는 실행 계획이며 사례 검증 증거가 아니다. W 사례·runtime 고정 증거는 frozen-core-v2.5.json과 연결된 실제 검증·독립 리뷰 파일이고 최신 채점 도구 버전은 frozen-core-v2.8.json이다.

각 run은 실행 요청, model/effort transcript, commands와 종료 결과, 중간 파일 스냅샷, 최종 파일, 외부 test/analyzer, scope 검사, 보고 판단, usage와 elapsed를 보관한다. native session metadata는 requested execution model의 증거이며 provider 내부 routing까지 관측했다고 주장하지 않는다. 알 수 없는 하위 usage는 0이 아니라 unavailable이다. 관측한 성공 횟수와 실패 유형을 제시하고 반복 3회의 작은 차이에 통계적 확신을 부여하지 않는다.

실패는 구현 누락/잘못된 계약/검증 부족/보고 오류/환경/평가기 문제로 분리한다. Codify 수정은 실행 transcript와 재현 가능한 실패가 근거일 때만 한다. 우선 작은 범용 규칙 또는 조건부 Flutter guidance를 고치고, 영향을 받은 개발 사례와 기존 성공 사례로 재검증한다. 수정된 후보는 보류 결과까지 확인한다.

## 8. 완료 기준

- 스펙, fixtures, 채점기, 실행 경로가 저장되어 재실행할 수 있다.
- 본/보조/보류 평가에서 누락된 run 또는 판단 불가능한 필수 증거가 없다.
- 대표 Flutter 앱의 실제 runtime 통합 흐름을 검증했다.
- W01/W02의 신규 앱 작성·기존 프로젝트 통합·실제 저장·재시작·선택 플랫폼 build 증거가 있다.
- 관측된 실패를 반영한 Codify 후보의 독립 리뷰·회귀·보류 결과가 있다.
- 설치된 스킬과 최종 평가 후보의 hash가 같고 `quick_validate.py`가 성공한다.
- 결과 보고서가 성공·실패·환경 오류·미검증 범위를 숨기지 않는다.

단순히 green test가 많거나 계획과 fixture가 만들어졌다는 이유로 목표 완료를 선언하지 않는다. 판단할 근거가 부족하면 다음 실행을 계속한다.

## 공식 참고

- [OpenAI Skill Evals](https://developers.openai.com/blog/eval-skills): 실행 기록과 산출물을 기준으로 평가한다.
- [Flutter Testing](https://docs.flutter.dev/testing/overview): unit/widget/integration evidence를 구분한다.
- [Flutter Integration Tests](https://docs.flutter.dev/testing/integration-tests): 실제 실행 앱의 흐름을 검증한다.
