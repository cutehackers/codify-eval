# J01: Tenant-scoped job leasing

Status: `authored_unqualified`.

Public actor material: `task.md` and `repo/`. Private qualification material: `private/`. Never expose reference, oracle, negative controls, or requirement map to an implementation actor.

Authoring used only the repository AGENTS.md, improvement-spec-v1.md, and the public S02 pubspec/metadata layout. No earlier implementation, oracle, result, snapshot, candidate, or runtime trace was inspected.

For independent qualification, stage a fresh copy of `repo/`, replace only its implementation with the chosen reference/negative file, and copy `private/acceptance_test.dart` into its test directory. Run the public and private tests offline. Preserve raw output outside actor material. The stub should fail functional behavior. The reference should pass all checks. Each negative should fail its mapped behavioral test without a compile/runtime infrastructure failure.

The controls remove tenant binding (N01), current lease-ID matching (N02), CAS success enforcement (N03), or third-expiry exhaustion (N04). They retain executable service behavior rather than throwing injected failures.

Author checks are preliminary implementation sanity checks. Independent requirement/oracle review, qualification, difficulty pilot, cohort decisions, and freeze remain with the root. No actual model evaluation or Docker work is part of authoring.

Authoring revision 2 addresses semantic-review F1/F2 without changing the public task. Current preliminary evidence is `private/author_checks_v2/`; `private/author_checks/` and `private/historical/` retain historical revision-1 receipts and hashes. Supplemental probes demonstrate benign diagnostic acceptance, sensitive-payload rejection, and clock-before-guard rejection. They are oracle regression probes, separate from the four registered N01–N04 controls. The initial clock probe log is retained as an explicitly historical interim receipt in the v2 summary. Independent v2 review remains pending.

Authoring revision 3 changes only N03 executable source: remove its unreachable retry loop and busy return while retaining one CAS followed by unconditional proposed-result success. `private/historical/N03-v2.dart` preserves prior bytes. Bounded current N03 host analyzer/behavior checks are in `private/author_checks_v3/`. Earlier v2 N03 receipts are historical for that prior source; v2 reference and other-control receipts remain bound to their unchanged source hashes. Public task, oracle, reference, other registered controls, and original receipts are unchanged. Independent review and exact-source Docker qualification of revised N03 remain with the root.
