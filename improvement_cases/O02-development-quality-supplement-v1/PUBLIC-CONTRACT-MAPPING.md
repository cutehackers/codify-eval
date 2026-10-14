# O02 exposed development 보완 테스트 v1

기존 O02 공개 요청과 고정 24개 테스트를 수정하지 않는 별도 개발 검사다. held-out final이나 새 최종 평가 fixture가 아니다. 원본 request는 `improvement_cases/fresh-optional-cohort-v1/O02/public/request.md`다.

| 검사 | 공개 근거 | 성공 시 검사 |
|---|---|---|
| S01 정상 injected bundle | R4/R5/R8, request 15/17/23/31행 | absent→applied revision1, 동일 bytes→unchanged revision1, 한 번의 CAS와 완전한 report |
| S02 잘못된 manifest | R4, 15/31행 | UTF8 jsonEncode의 고정 key 순서와 정확히 하나의 LF |
| S03 traversal 파일 경로 | R3/R4, 13/15/31행 | 선택된 ID마다 `documents/<id>.txt` 한 개, 요청 순서 |
| S04 잘못된 파일 byte | R4, 15/31행 | body의 UTF8 bytes 그대로, 정확한 byteLength |
| S05 applied의 불완전 report | R8, 23/31행 | 모든 선택 항목의 id/path/byteLength를 입력 순서대로 반환 |
| S06 unchanged의 불완전 report | R5/R7/R8, 17/21/23/31행 | 동일 저장 bytes에서 새 CAS 없이 현재 revision과 완전한 report 반환 |

S02–S06은 malformed non-null encoder 반환을 거부하거나 canonical bytes/report로 정상화하는 구현을 모두 허용한다. 이 반환의 오류 코드는 공개 요청에 정해져 있지 않으므로 특정 오류 코드를 강제하지 않는다. 거부 결과에는 공개된 실패 code/message, null revision, 빈 report만 요구한다. `store.load` 이전 검증, 특정 validation 함수, encoder 재호출, canonical 재계산 방식은 요구하지 않는다.

성공을 반환한 경우에는 R4/R8의 출력 불변 조건을 만족해야 한다. absent snapshot이면 R5에 따라 applied/revision1/CAS1, 이미 동일 bytes의 revision7 snapshot이면 unchanged/revision7/CAS0을 확인한다. 저장 bundle의 내부 report 필드는 검사하지 않는다. 성공 Outcome.report와 실제 저장 manifest/files의 일치만 검사한다.

기대 bytes는 테스트 안에서 공개 format으로 만든다. 제품의 `encodeTextBundle`을 정답 생성기로 사용하지 않는다. 문서 두 개의 순서를 z/a로 고정하고 Unicode와 CR/LF를 포함해 byteLength와 report 순서를 확인한다. S01은 정상 injected encoder까지 무조건 거부하는 구현이 보완 검사만 통과하는 것을 막는 positive control이다.

파일은 O02의 기존 Flutter package에 test 파일 하나로 추가할 수 있도록 `package:o02_fixture` API와 기존 flutter_test SDK만 사용한다. root가 보존된 A/C17 산출물의 별도 복사본에 동일 overlay를 넣고 prelaunch review 후 자격 확인과 실행을 수행한다. 원본 frozen 테스트와 산출물은 바꾸지 않는다.

이번 작성 단계에서는 Dart/Flutter 분석·테스트, SDK/container/provider/model actor를 실행하지 않았다. 테스트의 실행 성공, A/C17의 새 결과, 최종 품질 우위는 아직 확정하지 않는다.
