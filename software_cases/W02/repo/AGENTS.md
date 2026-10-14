# Existing local Todo project
Linux desktop is the fixed evaluation platform. External services and network are not required.
Current functionality: create trimmed nonempty Todo titles, toggle completion, atomically save and restore todos.json.
The public persisted file lives in EVAL_DATA_DIR/todos.json (JSON array with id, title, done).
Older records omit any new archive property. Preserve IDs, titles, completion values, and existing data.
Keep the existing entry point and public Todo/Store/Controller contracts used by protected regression tests.
You may change lib/, pubspec.yaml, linux/, add new test/ or integration_test/ files and implementation documentation.
Preserve test/existing_regression_test.dart and lib/user_banner.dart byte for byte. Never weaken existing tests.
Required checks: flutter analyze --no-pub; flutter test --no-pub; flutter build linux --release --no-pub.
Observe final user flows in the Linux app, including fresh-process persistence. No fixed new internal API or widget-key contract is imposed.

Existing accessible labels: 할 일 제목, 추가, 완료: {title}, 완료 취소: {title}. Preserve these public controls.
Filter labels: 전체, 진행 중, 완료. If the human selects archive/restore, corresponding labels are 보관함, 보관: {title}, 복원: {title}. This conditional vocabulary does not choose the policy.

저장에 실패하면 기존 데이터와 화면 목록을 유지하고 저장 완료로 표시하지 마세요. 화면에는 "저장 실패"와 "다시 시도" 버튼을 보여 주세요. 외부 파일 장애를 해제한 뒤 "다시 시도"를 누르면 실패했던 원래 동작이 완료되어야 합니다. 앱은 아직 존재하지 않는 EVAL_DATA_DIR도 직접 생성해야 합니다.
