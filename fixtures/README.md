# Flutter task fixtures

These 16 fixtures were authored for this evaluation, rather than copied from a public benchmark or production repository. E01–E12 are development cases. H01–H04 are held out from skill improvement. Each case has an independent starting program, a Korean task, a complete gold reference, metadata, and external acceptance tests. Twelve cases exercise Flutter UI or app flows and four exercise Dart data or asynchronous controllers.

| ID | Principal acceptance |
| --- | --- |
| E01 | Inclusive last-item and singleton selection, empty list |
| E02 | Shared controller notifications and app recreation |
| E03 | Trimmed case-insensitive filtering, empty result, clear |
| E04 | Form validation, pending state, save failure, retry, disposal |
| E05 | ID-based list/detail navigation across modules, missing ID |
| E06 | Replaceable local store, exact multiline save/reload, failures |
| E07 | Historical task serialization compatibility, typed rejection |
| E08 | Fake remote adapter, loading, failure, retry and empty success |
| E09 | Newest-request wins, stale failure, retry and disposal |
| E10 | Explicit duplicate-policy decision and chosen replacement |
| E11 | UI checkbox repair with pre-existing dirty file preserved |
| E12 | Create, list, edit and recreate the app with the same controller |
| H01 | Quantity widget boundaries including maximum zero |
| H02 | Separate catalog, basket and summary modules with SKU totals |
| H03 | JSON adapter validation and retry after malformed response |
| H04 | Historical preference serialization compatibility |

## External grader interface

Only expose `repo/`, `task.md`, and the public portion of metadata to an evaluated agent. Keep `oracle/`, `reference/`, and evidence outside its filesystem. The agent may implement within `lib/**` and add new `test/**` files. It must not weaken existing tests or change protected files.

1. Copy `fixtures/<ID>/repo/` into an isolated writable work directory and initialize Git.
2. For E11, commit `metadata.initial_dirty.head_content` at its path first, then restore `working_content` before the agent starts. Preserve that dirty file byte for byte through the run.
3. For E10, wait for the required decision request and deliver the explicit `decision_rules[].choice` as the user's response. The initial task deliberately does not reveal that choice.
4. After the agent completes, copy its repo into a fresh grader directory. Add `oracle/test/acceptance_test.dart` to `test/acceptance_test.dart` in that copy, retaining any additional tests the agent wrote.
5. Run `flutter pub get --offline`, `flutter test test/acceptance_test.dart`, and `flutter analyze --no-pub`. Compare protected bytes and allowed paths separately. Every command must finish and its exit code must be recorded.

Oracle tests use starting public APIs, keys, and constructors, except `EntryDetail`, which E05 explicitly requests. Hidden input values exercise disclosed behavior. The tests do not impose a visual pixel target or depend on any external provider. E06 uses an in-memory replaceable store. E12 recreation preserves a controller, without disk persistence.

`python3 tools/fixtures.py build` regenerates authored programs and formats Dart files, preserving E11's exact user bytes. `python3 tools/fixtures.py verify` grades baseline and reference copies on the host. `--ids E01 E05 E12` selects pilots. Set `FLUTTER_BIN` to select another compatible Flutter installation.

Each `evidence.json` records successful offline dependency resolution, failing baseline acceptance, passing gold acceptance, and passing gold static analysis. This host evidence uses Flutter 3.47.2 / Dart 3.13.2. Container evidence must be recorded separately for the actual evaluator runtime. Baseline failure demonstrates that omitting the principal behavior is detected. E05 also fails compilation because its required public detail widget has not yet been implemented. Gold success is fixture validity evidence, not evaluated-model success.

These small independent programs evaluate bounded repair and feature tasks. They do not establish production readiness, device performance, live network behavior, platform builds, deployment, or durable disk/database persistence.
