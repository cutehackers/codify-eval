# Codify 평가·개선 과정 보고서

작성일: 2026-10-14. 최종 후보: C24. 상태: 사용자가 승인한 대표 6개 평가·보충 확인·설치·리소스 정리 완료.

[README](../README.md) · [사용 사례](codify-use-cases.md) · [최종 결과 보고서 v3](representative-evaluation-final-report-v3.md)

최종 repo 정리에서는 사용자 요청에 따라 실행 로그·임시 실행 코드·보존 압축본을 삭제했다. 이 보고서, 스킬·검사 소스와 핵심 결과 JSON은 보존했다. 아래 시험 과정은 평가 당시 기록이며, 삭제된 원본을 이용한 재감사는 불가능하다. [최종 보존 기록](../results/improvement-v1/repository-retention-outcome-v1.json)

## 결과와 해석

이 저장소는 Codify 지침을 개선하고, 작성된 코드와 실제 실행 기록으로 효과를 확인하기 위해 사용했다. 평가(eval)는 동일한 과제와 조건에서 스킬 없음·원본·개선본을 실행한 다음, 요청한 행동·실패 처리·파일 보존·질문·통합 결과를 외부 검사와 독립 검토로 비교하는 과정이다.

최종 비교는 R1~R6 × A/C0/C24의 **18회 담당 에이전트 실행**, 총 **216개 비공개 행동 검사**다. 세 조건 모두 통과했다. 이후 원본 코드를 보존한 R3 종료 진단과, C24의 명시적 작업자 인계를 확인하는 R6 보충 실행을 별도로 수행했다. R6 보충은 기존 14개 검사를 통과했다.

C0의 특정 비동기 종료 결함을 C24와 A가 피한 결과는 확인했다. 고정된 216개 검사에서는 품질·보안·질문 판단의 차이가 관찰되지 않았다. C24의 참고 토큰과 모델·도구 실행 시간은 C0보다 적었지만, 전체 시간은 길었고 A보다 참고 토큰과 모델·도구 실행 시간이 많았다. 이 결과를 스킬 자체의 인과적 효과나 보편적인 우수성으로 해석하지 않는다.

사용자는 추가 평가를 늘리지 않고 대표 6개 결과로 마무리하도록 선택했다. 이 승인 범위에서 작업을 종료했으며 전반적 우수성 미입증이라는 한계를 유지한다. [최종 범위 선택](../results/improvement-v1/representative-final-closure-user-amendment-v1.json), [완료 감사](../results/improvement-v1/representative-final-completion-audit-v1.json)

## 목적과 완료 범위의 변화

| 단계 | 목적·결정 | 적용 방식과 근거 |
|---|---|---|
| 단계1 | 평가 전에 스킬 흐름과 평가 항목의 적합성 점검 | 승인·계약 절차와 실제 소프트웨어 작성 성과를 구분. [항목 적합성 검토](item-suitability.md) |
| 단계2 | 원본과 후보를 비교하며 지침·실행기·사례 보완 | 원본·실패 기록을 보존하고 새 후보에 새 버전 부여. [개선 계획](improvement-spec-v1.md) |
| 단계3 | 모델 고정과 비용·출력 제한 기준 조정 | 최종 평가·검토는 `gpt-6.1-sol` / `medium`. 토큰은 최종적으로 참고 지표만 사용. [토큰 기준 변경](../results/improvement-v1/token-acceptance-user-amendment-v2.json) |
| 단계4 | 과도한 평가·실행기 확장 방지 | 대표 6개 과제로 축소. 원래 남은 18개 조건, 큰 표본의 통계 검증, 범용 실행기 확장 제외. [범위 변경](../results/improvement-v1/representative-evaluation-scope-user-amendment-v1.json) |
| 단계5 | 대표 비교와 필요한 보충 확인 후 종료 | 실제 결과와 한계를 보고하고 C24 적용·소유 리소스 정리. [최종 승인](../results/improvement-v1/representative-final-closure-user-amendment-v1.json) |

초기 E/S/W/H 평가와 개발용 D/Q/O/B 사례는 역사적 자료다. 초기 앱 작성 평가에는 Flutter 실행 앱과 저장·복구 확인이 포함됐으며, 해당 자료는 최종 Python 대표 비교와 분리한다. 초기 계획의 실행 횟수를 실제 완료 횟수로 인용하거나 서로 다른 평가의 성공률을 합치지 않는다.

원래 baseline 24개 배정 중 v5 개발 실행기가 지원한 것은 B01/B02 × A/C0/C23의 단독 6개 행이었다. 질문·작업자 조건 18개 행은 당시 미승인 상태였고 이후 대표 범위에서 제외됐다. 최종 R1~R6의 18회는 **별도로 준비·실행한 비교**이며 그 미승인 18개 행을 완료한 것이 아니다. [당시 경계 검토](../results/improvement-v1/baseline-development-v5-six-row-cohort-independent-review-v1.json)

## 원본과 C24의 차이

비교 기준은 보존된 [C0](../snapshots/C0/)와 [C24](../snapshots/C24/)다. C0에도 위험에 따른 검증, 중요한 질문, 파일 소유권과 최종 책임 원칙이 있었다. C24는 그 원칙을 실제 행동으로 연결하는 조건과 실패 처리 방법을 구체화했다.

| 변경 | C0의 지침 | C24의 구체화 | 확인 범위 |
|---|---|---|---|
| 개선1 탐색 | 관계 코드·지침·테스트를 읽고 저장소를 확인 | 제공된 경로부터 필요한 입력을 묶어 읽기, 중복 탐색 줄이기, 편집·검증 범위가 파악되면 종료 | 지침 변경 확인. 전체 소요 시간 개선으로 단정하지 않음 |
| 개선2 위험별 검증 | 행동 중심 테스트와 위험에 따른 범위 확장 | 서로 다른 실패 원인·오류 순서·상태 전이·동시 실행 순서 유지, 테스트 수로 범위를 대신하지 않음 | 대표 행동 검사 통과. R3의 특정 종료 차이는 별도 확인 |
| 개선3 외부 출력·복구 | 요청과 기존 동작을 보존하며 검증 | 성공한 외부 출력도 저장 전에 형식·권한·보고 조건 검사, 저장 실패·취소·늦은 결과·재시작 확인 | R1~R3 검사 통과. A/C0와의 일반적인 보안 우위는 미입증 |
| 개선4 질문 | 중요한 선택에 집중한 질문 | 관련 질문을 묶고 기존 답변·승인 재사용, 나머지 가정은 좁고 되돌릴 수 있게 유지 | R4/R5 모두 세 조건 통과. 질문 우위는 미입증 |
| 개선5 분담 | 독립성·시간에 도움이 되면 위임, 소유권과 완료 기준 지정 | 작업자 접근 확인, 실제 공개 계약·현재 버전 전달, 동시에 할 담당 작업 확인, 기여를 수락·거절한 뒤 최종 통합 | 명시적으로 요청한 단일 작업자 인계 확인. 비교 효율은 미입증 |
| 개선6 도구·실행 | 구현과 검사 결과를 근거로 완료 | 정확한 도구 스키마·인자 인용, 실행 여부 불명 시 상태 확인, 원래 핸들 유지, 실패 원인 분류 | 지침 변경 확인. 범용 인증·실행 격리까지 입증하지 않음 |
| 개선7 마무리 | 관련 검사와 diff 확인, 범위·한계 보고 | 개별 종료 상태와 실패 증거 보존, 허용된 생성 파일만 정리, 같은 소스의 유효한 결과 재사용 | 최종 scope·검사·원본 기록 확인. 재사용이 필요한 독립 검사를 대체하지 않음 |

변경 파일은 `SKILL.md`, `references/delivery.md`, `references/orchestration.md` 세 개다. `specification.md`, `intent-interview.md`, UI 메타데이터의 기존 지침은 보존했다. C0 진입 파일은 6,372바이트, C24는 8,035바이트다. 원본보다 짧아진 스킬이라고 설명하지 않으며 문서 길이를 비용 절감의 증거로 사용하지 않는다.

## 후보 개발 경과

아래는 후보 변경 기록을 묶은 개발 경과다. 후보 번호가 있다고 해서 모든 후보에 동일한 실제 비교 평가를 수행한 것은 아니다. 정적 검토·개발 실행·최종 비교를 구분한다.

| 단계 | 주요 조정 | 대표 변경 기록 |
|---|---|---|
| 개발1 C0~C1 | 원본 보존, 개발 후보와 평가 목적·조건 고정 | [개선 계획](improvement-spec-v1.md), [스냅샷](../snapshots/) |
| 개발2 C2~C8 | 필요한 소스 묶음 읽기, 탐색 종료, 조건부 참조, 검증 누락 보완 | [C2](../results/improvement-v1/C2-development-rationale-v1.json), [C8](../results/improvement-v1/C8-development-rationale-v1.json) |
| 개발3 C9~C12 | 원래 실행 핸들·종료 정리, 입력 검사의 전제, 인자 인용, 부분 실행과 실행 전 거부 구분 | [C9](../results/improvement-v1/C9-development-rationale-v1.json), [C12](../results/improvement-v1/candidate-C12-draft-intent-v1.json) |
| 개발4 C13~C16 | 의존성 준비와 증거 재사용, 서로 다른 위험 검사 유지, 관련 없는 formatting·shell 확장 방지 | [C13](../results/improvement-v1/candidate-C13-draft-v1.json), [C16](../results/improvement-v1/candidate-C16-change-record-v1.json) |
| 개발5 C17~C22 | 출력 한도 안의 입력 읽기, 외부 성공 출력 검증, 실제 계약 전달·작업자 접근·소유권·통합 | [C17](../results/improvement-v1/C17-candidate-change-v1.json), [C22](../results/improvement-v1/C22-change-intent-v1.json) |
| 개발6 C23~C24 | 중복 지침 정리, 독립 의미 검토 보완, 최종 후보 고정 | [C23](../results/improvement-v1/C23-compact-draft-author-report-v1.json), [C24 고정](../results/improvement-v1/candidate-C24-static-freeze-v1.json), [의미 검토](../results/improvement-v1/candidate-C24-independent-semantic-review-v2.json) |

정적 동결 JSON의 `behavior_qualified:false`나 `installed_or_promoted:false`는 **동결 당시 상태**다. 나중의 대표 실행·설치 결과는 별도 기록에 있다. 과거 기록을 덮어쓰거나 정적 통과를 실제 행동 성공으로 바꾸지 않았다.

## 평가 항목과 검사 범위

| 항목 | 실제 과제 | 주요 검사 | 조건당 비공개 검사 |
|---|---|---|---:|
| 평가1 R1 | 문서 내보내기 | 입력·권한 거부, 경로 경계, 성공 출력 검증, 안전한 오류, 저장·감사 효과 | 8 |
| 평가2 R2 | SQLite 작업 큐 | 영속 저장, 분리된 영역(tenant)별 중복 키, 임대·동시 claim, 실패 롤백·재시도 | 15 |
| 평가3 R3 | 공유 비동기 조회 | 중복 요청 공유, 순서, 취소 격리, 종료 정리, 실패 후 재시도 | 12 |
| 평가4 R4 | 재고 예약 정책 질문 | 질문 전 파일 보존, 동일 에이전트에 고정 답변, 답변 후 구현 | 8 |
| 평가5 R5 | 파일 스냅샷 저장 | 명시된 정책에 추가 질문 없이 구현, 원자적 교체, 손상·경로·정리 | 15 |
| 평가6 R6 | CSV 가져오기 통합 | 구문·검증 순서, 중복·행 보존, Decimal 합계, JSON 요약 | 14 |
| 합계 | 과제 6개 | 조건 A/C0/C24 각 1회 | 72 |

공개 요구사항은 [대표 사례 폴더](../representative_cases/v1/)에 있다. 비공개 검사·기준 구현은 평가 모델에 제공하지 않았다. 각 과제의 public smoke만 통과했다고 전체 동작을 인정하지 않고 외부 비공개 검사와 변경 범위를 함께 판정했다.

## 시험 과정과 판정 방법

| 순서 | 수행한 일 | 평가 당시 판정 근거 |
|---|---|---|
| 시험1 사례 작성 | 독립 작성자가 공개 계약·시작 코드·비공개 검사·기준 구현·잘못된 변형 작성 | 후보의 답을 요구사항으로 사용하지 않음 |
| 시험2 사례 qualification | 시작 구현 실패, 올바른 기준 구현 성공, 중요 행동을 제거한 변형 실패 확인 | 채점기가 정상·결함 구현을 구분하는지 검증. 모델 성과와 구분 |
| 시험3 도구 제어 검사 | 정상 통과·실패·잘못된 검사 수·scope 변경·원본 변경·중복 채점·가짜 종료·skip·준비 정보 변조 확인 | [9개 실제 프로세스 제어 검사](../results/improvement-v1/representative-helper-root-controls-v3.json) |
| 시험4 사전 독립 검토와 고정 | 과제·후보·인터프리터·준비/채점/계측 도구의 내용·모드·해시 고정 | [최종 사전 검토 PASS](../results/improvement-v1/representative-v1-initial-independent-review-v2.json), [고정 입력](../results/improvement-v1/representative-eval-v1-manifest.json) |
| 시험5 새 실행 준비·배정 | 초기 코드와 해당 스킬 사본만 제공, 별도 문맥·실행 경로, 원래 시간과 준비 해시 기록 | A 스킬 없음, C0 원본, C24 개선본. 최종 모델·reasoning 고정 |
| 시험6 실제 구현·질문 | R1~R6 구현, R4의 원래 에이전트에 답변 1회 전달, R5 추가 질문 여부 확인 | 원본 native 기록과 질문 전후 파일 상태 |
| 시험7 외부 채점 | 실제 unittest 정상 종료·예상 검사 수·skip 없음·scope·보호 입력·원래 기한 확인 | `unittest-completion.json`, `grading.json` |
| 시험8 계측·독립 결과 검토 | 원본 UUID별 최종 counter 1회 집계, 원본 시간 유지, 실질 결과와 범위 재검토 | [독립 결과 검토](../results/improvement-v1/representative-all18-independent-outcome-review-v1.json) |
| 시험9 보충·적용·정리 | R3 반례, R6 실제 인계, 검증된 C24 설치와 사용을 마친 소유 리소스 삭제 | 보충 기록·설치 확인·최종 승인·정리 영수증 |

사전 준비에서 수정한 문제는 R6 기준 구현의 줄바꿈 허용 오류, 출력 문자열·종료 코드만으로 검사 성공을 믿을 수 있는 문제, 변경 가능한 준비 정보로 보호 파일 범위를 넓힐 수 있는 문제였다. 기준 구현을 수정하고, 실제 unittest 완료 JSON과 원본 준비 해시·고정 행 검사를 도입했다. 이 도구 보완은 스킬의 코드 작성 우위와 구분한다. [최초 사전 검토](../results/improvement-v1/representative-v1-initial-independent-review-v1.json), [수정 후 사전 검토](../results/improvement-v1/representative-v1-initial-independent-review-v2.json)

## 실제 결과와 참고 계측

| 조건 | 통과 과제 | 비공개 검사 | 원본 토큰 합계 | 모델·도구 실행 시간 | 준비부터 채점까지 전체 시간 |
|---|---:|---:|---:|---:|---:|
| A | 6/6 | 72 | 1,075,280 | 473.667초 | 898.509초 |
| C0 | 6/6 | 72 | 1,702,323 | 659.551초 | 948.524초 |
| C24 | 6/6 | 72 | 1,467,503 | 640.460초 | 994.315초 |

원본 수치: [18회 비교 JSON](../results/improvement-v1/representative-all18-descriptive-results-v1.json)

- 결과1: C24는 C0 대비 참고 토큰 13.8%, 모델·도구 실행 시간 2.9% 감소. 전체 시간은 4.8% 증가.
- 결과2: C24는 A 대비 참고 토큰 36.5%, 모델·도구 실행 시간 35.2% 증가. A 대비 우위를 주장할 수 없음.
- 결과3: R3의 사후 진단 두 경우에서 C0는 종료된 조회에 값·다른 오류를 전달했고 A/C24는 요구된 취소 오류를 전달. 같은 결함의 두 증상이며 기존 216개 검사에 합산하지 않음.
- 결과4: R6 보충은 C24 담당 에이전트 1회·작업자 1명, 비공개 검사 14개 PASS. 참고 토큰 794,483, 전체 시간 212.535초. 기존 세 조건 비교에 합산하지 않음.

R3 근거: [진단](../results/improvement-v1/representative-R3-close-diagnostic-v1.json), [독립 검토](../results/improvement-v1/representative-R3-close-diagnostic-independent-review-v1.json)

R6 근거: [별도 고정 시나리오](../results/improvement-v1/representative-R6-handoff-freeze-v1.json), [독립 결과 검토](../results/improvement-v1/representative-R6-handoff-independent-outcome-review-v1.json)

토큰은 참고 지표이며 청구 금액을 관측하지 않았다. 캐시 입력·reasoning 출력은 총량의 부분집합으로 중복 합산하지 않는다. 모델·도구 실행 시간에는 질문 답변 대기를 분리하고, 전체 시간에는 준비·담당 대기·채점을 포함한다. 작업자 시간은 담당 시간과 겹치므로 두 값을 더해 전체 소요 시간으로 표시하지 않는다. 평가 준비·리뷰 등 연구 비용은 제품 실행 수치와 별개이며 전체 연구 비용의 완전한 집계는 없다.

## 사용한 리소스와 정리

| 리소스 | 사용 목적 | 평가 종료 후 상태 |
|---|---|---|
| native 에이전트 실행 | 별도 문맥의 실제 구현·질문·인계와 독립 검토 | 결과·계측 요약 보존. 원본 실행 로그 삭제 |
| Python 3.12.14 | 최종 대표 구현과 외부 unittest | Codex 번들 인터프리터 사용. SDK 자체는 공유 런타임이므로 삭제하지 않음 |
| Flutter SDK·고정 평가 이미지 | 이전 앱 작성·실행 앱·복구 검사 | 사용을 마친 소유 평가 이미지 삭제. 최종 대표 비교는 Python 표준 라이브러리 사용 |
| Docker 컨테이너·빌드 캐시 | 초기 격리 실행과 Flutter 환경 준비 | 정리 기록 기준 컨테이너·볼륨·빌드 캐시 0. 다른 프로젝트 node 이미지 보존 |
| `runtime/` | 실행 코드, 질문 상태, 원본 native, 채점된 실행 파일 | 최종 repo 정리에서 전체 삭제 |
| `results/` | 고정 입력, qualification, 판정, 리뷰, 설치·정리 증거 | 문서가 참조하는 핵심 JSON만 보존. 원본 로그·보존 아카이브 삭제 |
| `snapshots/` | 원본·후보·설치 전 복원본 | C0~C24와 설치 전 복원본 보존 |

최종 대표 인터프리터의 평가 당시 경로는 `~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`이며 버전과 해시는 고정 입력 JSON에 기록했다. 호스트의 다른 Python을 동일한 환경으로 간주하지 않는다.

후속 정리에서 생성 캐시 디렉터리 **1,215개**, 논리 파일 크기 **20.212755GiB**와 평가용 Docker 빌드 캐시 **14개**를 삭제했다. 정리 당시 Docker 빌드 캐시는 약 1.071GB였다. 당시에는 캐시 외 runtime 파일과 스킬·스냅샷·문서를 보존했다. 이후 최종 repo 정리에서는 runtime 전체와 보존 압축본을 삭제했다.

삭제한 생성 캐시와 Docker 리소스의 내역은 아래 정리 기록에서 확인한다. [정리 요약](../results/improvement-v1/post-evaluation-resource-cleanup-summary-v1.json), [호스트 정리 상세](../results/improvement-v1/post-evaluation-cache-cleanup-outcome-v1.json), [Docker 정리 상세](../results/improvement-v1/post-evaluation-Docker-cache-cleanup-outcome-v1.json)

정리 검증 중 C24의 Finder 메타데이터 `.DS_Store`가 동결 당시 해시와 다른 것을 확인했다. 삭제 전 기록에도 같은 차이가 있었고 스킬 지침·과제 입력은 일치했다. 기존 고정 입력을 수정하거나 전체 manifest가 현재도 일치한다고 표시하지 않았다. 최종 repo 정리에서 Finder 파일과 qualification 로그도 삭제했다. 기존 manifest는 평가 당시 기록이며, 재평가에는 현재 입력을 기준으로 새 manifest가 필요하다.

## 설치와 사용

설치 위치는 `~/.agents/skills/codify/`다. 검증된 C24 지침을 복사하고 내용·모드와 스킬 형식을 확인했다. 설치 전 C0 복원본은 [별도 스냅샷](../snapshots/installed-pre-C24-v1/)으로 남겼다. [설치 기록](../results/improvement-v1/representative-C24-installation-v1.json)

요청에는 `$codify`를 명시한다. 일반 구현은 진입 지침을 사용하고, 계약·지속 작업·실제 분담에 필요한 경우 해당 참조를 읽는다. 스킬은 모델 정책을 정하지 않고 실행 환경의 정책을 따른다. [구체적인 사용 예시](codify-use-cases.md)

## 입증하지 않은 것

| 한계 | 해석 |
|---|---|
| 한계1 표본과 조건 | 과제별·조건별 1회이며 일부 조건은 같은 호스트에서 동시 실행. 통계적·인과적 우위로 확대하지 않음 |
| 한계2 질문 | R4 공개 계약이 질문을 요구. 숨은 정책 누락 발견이나 A/C0 대비 질문 우위는 미입증 |
| 한계3 분담 | 원래 R6는 세 조건 모두 단독 구현. 보충은 명시적 단일 작업자 인계만 확인 |
| 한계4 비용·속도 | 토큰은 금액이 아니며, 전체 시간은 C0보다 길고 A보다 모델·도구 시간이 많음 |
| 한계5 환경·보안 | 대표 검사에서 운영·실계정·모바일 기기·모든 경합 순서·공격자 호스트 격리를 검증하지 않음 |
| 한계6 공개 범위 | 사용자 승인으로 남은 원래 18개 조건·대규모 통계 검증·범용 실행기 확장은 제외 |

## 저장소에서 관리하는 방법

- 관리1: [README](../README.md)를 진입 문서로 유지하고, 사용 예시는 [사용 사례](codify-use-cases.md), 과정·수치는 이 보고서로 나눈다.
- 관리2: 핵심 결과·고정 입력의 당시 기록·최종 보고서를 유지한다. 후속 평가에는 새 후보·사례·실행 경로와 새 고정 입력을 만들고 근거 링크를 추가한다. 원본 실행 자료의 보존 기간은 평가 후 별도로 정한다.
- 관리3: 정적 검토, 사례 qualification, 실제 모델 실행, 보충 진단, 설치·정리의 상태를 각각 기록한다. 다른 단계의 통과로 아직 확인하지 않은 행동을 완료 처리하지 않는다.
- 관리4: 문서·스킬·테스트 코드·핵심 결과 JSON을 Git에서 관리한다. `runtime/`과 새 원본 로그·압축본은 Git 제외이며, 현재 과거 실행 자료는 삭제된 상태다.
- 관리5: 이후 문서를 갱신할 때는 원본 JSON·실행·검토를 먼저 확인하고 비교 조건, 측정 정의, 승인 범위와 한계를 함께 갱신한다. 새 자료 없이 우수성 표현을 강화하지 않는다.

## 근거 찾기

| 확인할 내용 | 근거 |
|---|---|
| 최종 결과와 해석 | [최종 결과 v3](representative-evaluation-final-report-v3.md), [18회 수치](../results/improvement-v1/representative-all18-descriptive-results-v1.json) |
| 공개 계약·시작 코드·비공개 검사 | [대표 사례](../representative_cases/v1/) |
| 고정 환경과 채점기 | [대표 manifest](../results/improvement-v1/representative-eval-v1-manifest.json), [준비·채점 도구](../tools/representative_eval_v1.py), [unittest 완료 도구](../tools/representative_unittest_runner_v1.py) |
| 계측 정의 | [native 사용량 도구](../tools/representative_native_cost_v1.py) |
| 과거 실행 자료 | runtime과 원본 로그는 삭제. 동작·시간·사용량은 보존한 결과 요약에서 확인 |
| 범위·완료 결정 | [대표 범위](../results/improvement-v1/representative-evaluation-scope-user-amendment-v1.json), [마무리 선택](../results/improvement-v1/representative-final-closure-user-amendment-v1.json) |
| 최신 리소스 정리 기록 | [정리 요약](../results/improvement-v1/post-evaluation-resource-cleanup-summary-v1.json) |
