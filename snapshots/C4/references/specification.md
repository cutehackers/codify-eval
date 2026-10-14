# Specification and Contract Workflow

Use this reference for parent specification creation, approval, Vertical Slice decomposition, and contract amendments.

## Artifact rules

Store normalized Codify parent specifications under `docs/design/specs/` and Vertical Slice contracts under the repository-root `.tasks/<parent-spec-name>/` directory by default, unless the user explicitly provides another destination. `<parent-spec-name>` is the normalized parent specification filename without `.md`, so the parent and its slices share one feature directory name without duplicating the feature suffix in each slice filename. Preserve file-based source proposals and unnormalized notes at their existing source path, commonly `docs/design/raw/`; this is a convention, not a prerequisite for specification. A current user prompt or attached document is also a valid initial intent source. Do not overwrite file-based sources with normalized contracts.

Decision records created during Specify are ADR-equivalent records. Before writing one, inspect all applicable project `AGENTS.md` files for the required path, filename, format, and lifecycle. A project convention overrides the generic default and may use a single file such as `docs/DECISIONS.md`. Only when no project convention exists, use `docs/design/decisions/YYYY-MM-DD-<decision>.md`. Do not silently resolve conflicting project instructions.

```text
Parent: docs/design/specs/YYYY-MM-DD-<feature-title>.md
Slice:  .tasks/YYYY-MM-DD-<feature-title>/vs-<NN>-<user-goal>.md
```

Preserve the creation date on later edits. Use lowercase ASCII kebab-case, stable zero-padded slice IDs, and observable user goals. Never use UI-only, controller-only, service-only, database-only, or other horizontal layer names. Append `-ko` only when the body is primarily Korean. Never overwrite an unrelated spec.

### Existing-contract preflight

Before writing a new parent or slice, inspect relevant parent files in `docs/design/specs/` and child files in `.tasks/` to understand prior decisions, scope, public seams, and material conflicts. An existing contract is a historical agreement, not the default destination for a new request.

- Create a new parent contract and a new child directory for each new work item, even when it relates to an existing feature.
- Amend an existing parent or child only when the user explicitly identifies that contract and asks to amend, revise, or continue it. Do not infer this authority from subject overlap.
- Do not alter an existing contract's scope, status, acceptance criteria, dependencies, or review result merely to align it with a new contract.
- If the new work overlaps or conflicts with an existing contract, state the relationship in the new contract. Preserve the prior contract until the user explicitly authorizes its replacement, retirement, or deletion.
- When the user explicitly requests a replacement, record the replacement relationship according to repository policy. Otherwise, do not mark prior contracts `Superseded` or redirect their child slices.
- Before reporting completion, verify that the new parent and its child slices point only to each other and that existing contracts remain unchanged unless explicitly amended.

Use the repository's lifecycle marker when one exists. Otherwise put `Contract Status: Proposed` or `Contract Status: Approved` near the title.

## Intent Hardening Interview

Every Specify request must pass an Intent Hardening Interview before its parent specification is normalized. The interview is allowed to create or update a working intent record, Proposed decision records, and Candidate or Open glossary entries while the conversation proceeds. The Hardening Gate establishes that the intent is ready for normalization, not that every decision is approved. Determine the parent contract status using the approval rules below. Parent approval does not approve child slices or authorize implementation.

Use [intent-interview.md](intent-interview.md) for the question groups, adversarial checks, artifact fields, state transitions, turn summaries, and Hardening Gate. Group easy questions that share a decision context so the user can decide efficiently. Split questions when they depend on one another or carry material risk. Do not force one question per turn and do not present an indiscriminate questionnaire.

Do not normalize an unresolved material decision into an apparently final requirement. If the Hardening Gate fails, record `Intent Status: Blocked` or `Draft-only` as applicable and stop before approval, slicing, or implementation.

## Specify a parent contract

After the Hardening Gate passes, convert the resolved initial intent source into one parent contract. Set its status according to the approval rules below, preserving any user request to keep it Proposed. For `Draft-only`, produce an explicitly unresolved Proposed draft without claiming the gate has passed. The source may be a file, an attached or currently discussed document, or the current user prompt. For prompt-only input, use `Source: User instruction (current request)` and normalize only the intent and constraints the user stated. Put unspecified details in Assumptions or Open Decisions instead of inventing requirements. Do not create a `docs/design/raw/` file solely to make prompt input look file-based. Include links to every decision record and glossary location created during the interview. Inspect relevant live code when the intent targets an existing repository. Do not create slices, tests, or production code.

Use this information model, adapting headings to repository convention without dropping their meaning:

The template defaults to Proposed. Set `Contract Status` and `Intent Status` from the actual interview and approval state rather than copying a successful state into every document.

```markdown
# <Feature Title>

- Contract ID: <FEATURE-ID>
- Contract Status: Proposed
- Created: YYYY-MM-DD
- Intent Status: Interviewing
- Source: <source path, attached document, or explicit user instruction; list all sources when combined>
- Decision Records: <project-native ADR or decision-log paths>
- Glossary: <project-native glossary path>

## 1. Problem and Goal
State the user problem, observable outcome, and business outcome.

### Intent and Goal IDs
- INT-01: <parent intent or problem to solve>
- GOAL-01: <observable user or caller goal that advances the intent>

## 2. Scope
### In Scope
- ...

### Non-Goals
- <excluded behavior> — <reason>

## 3. Actors and Preconditions
- Primary actor:
- Permissions:
- System preconditions:
- Data preconditions:

## 4. Confirmed Facts
- ...

## 5. Assumptions
- ASM-01: ...
  - Consequence if false:
  - Validation method:

## 6. Business Rules and Invariants
- INV-01: ...
- INV-02: ...

## 7. Observable User Flow
1. ...
2. ...

## 8. Failure and Boundary Behavior
Cover only relevant input, authorization, duplicate, idempotency, concurrency,
transaction, timeout, partial-failure, rollback, retry, compatibility, and migration behavior.

## 9. Decisions
| ID | Question | Decision | Rationale | Rejected Alternative | Consequences | Source / Evidence | Decision Record |
|---|---|---|---|---|---|---|---|
| D-01 | ... | ... | ... | ... | ... | ... | ... |

Every material decision must have a corresponding project-native ADR or decision-log entry containing the full context, decision, alternatives, rationale, consequences, source or evidence, affected invariants or acceptance criteria, and related Open Decisions or follow-ups.

## 10. Quality Constraints
Include measurable constraints only when supported by evidence.

## 11. Feature-Level Acceptance
- FA-01: THE <system> SHALL <observable result>.
- FA-02: WHEN <event>, THE <system> SHALL <observable result>.
- FA-03: IF <condition>, THEN THE <system> SHALL <observable result>.

## 12. Open Decisions
| ID | Question | Options | Trade-off | Recommendation |
|---|---|---|---|---|
| Q-01 | ... | ... | ... | ... |

## 13. Done When
State the evidence required before the feature is delivered.
```

Report the parent contract path, actual intent and approval states, confirmed scope, assumptions, decision records, glossary, and any remaining decisions or risks. Do not create slices or implementation during Specify.

## Approve a contract

For a parent contract, distinguish intent readiness from decision approval. Before recording `Contract Status: Approved`, confirm that `Intent Status: Hardened` is present, no blocking Open Decision remains, every material decision the contract depends on has an Accepted record or the repository's equivalent approval state, the contract is internally consistent, its acceptance criteria are observable and testable, and its scope complies with repository policy.

A direct user instruction or an unambiguous answer selecting a decision is explicit acceptance of that decision; record its source in the decision record and do not ask for the same approval again. Repository-defined approval requirements still apply. An agent recommendation, inference, or completion of the Hardening Gate alone is not acceptance and must not promote a Proposed decision record. Parent approval does not itself accept decision records.

| Condition | Parent state |
|---|---|
| User requests `Draft-only` | `Intent Status: Draft-only`, `Contract Status: Proposed`; no approval, slicing, or implementation |
| Material intent decision is unresolved | `Intent Status: Blocked`, `Contract Status: Proposed`; no approval, slicing, or implementation |
| Gate passes, but a required decision record lacks acceptance or the user asks to retain Proposed | `Intent Status: Hardened`, `Contract Status: Proposed`; report the approval gap without reopening resolved intent |
| Gate passes, every required decision is accepted, and no user or repository approval restriction remains | `Intent Status: Hardened`, `Contract Status: Approved`; no redundant parent approval request |

For a parent, change only the repository's approval marker or `Contract Status: Proposed` to `Contract Status: Approved` after the parent approval conditions above are met. For a Vertical Slice, make the same marker-only change only after independent review and explicit user approval. Do not alter substantive content during approval. Use amendment for substantive changes.

A Vertical Slice contract still requires `Independent Review: Passed` and an explicit user approval before approval. Parent approval does not change this slice-level gate.

## Create Vertical Slice contracts

Require an approved parent contract with no blocking Open Decision. Create one durable file per slice under `.tasks/<parent-spec-name>/`, where `<parent-spec-name>` is the parent contract filename without `.md`. Resolve the directory from the canonical parent path, create it if needed, and do not flatten the slice filename into `docs/design/specs/`.

Confirm first that the target is the only active canonical parent for its feature scope. Do not slice a contract while a sibling specification defines overlapping public behavior, migration rules, invariants, or acceptance criteria.

Each slice must contain an explicit Intent and Goal section. It must name one primary stable `INT-*` and `GOAL-*` mapping from the parent, state why the slice exists, and connect that goal to a parent feature acceptance criterion. The slice must deliver one observable user or caller outcome, cross the necessary path from entry point through domain behavior to observable result, remain independently implementable and verifiable, preserve parent invariants, and exclude unrelated goals and speculative infrastructure. A technical layer or slice title is not an intent or goal. Order slices by prerequisites, user value, and risk.

Each slice must state its verification intent before independent review: risk triggers, expected evidence, and every command that repository discovery already establishes. Do not invent commands. A command that depends on the final changed paths may be marked `Resolve after change discovery`, with its decision trigger. Before completion, delivery must replace every applicable marker with the exact command and actual evidence, or record `N/A` with a reason.

Use this information model:

```markdown
# <Feature Title> — VS-<NN> <User Goal>

- Contract ID: <FEATURE-ID>-VS-<NN>
- Contract Status: Proposed
- Independent Review: Pending
- Parent Contract: <repo-relative parent spec path>
- Created: YYYY-MM-DD

## 1. Intent and Goal
- Intent ID: <INT-01>
- Parent Intent: <the parent intent this slice advances>
- Goal ID: <GOAL-01>
- Slice Goal: <one observable user or caller goal>
- User or Caller Value: <why achieving this goal matters>
- Contribution to Parent: <how this slice advances the parent intent>
- Parent Acceptance: <FA-01 or other parent acceptance reference>

The slice must have exactly one primary Goal ID. Supporting goals may be listed only when they do not obscure the primary goal.

## 2. User Outcome
One observable result delivered by this slice.

## 3. Scope
### In Scope
- ...

### Out of Scope
- <excluded behavior> — <reason>

## 4. Preconditions
- ...

## 5. Public Seam
Describe how the behavior is invoked and observed without prescribing private structure.

## 6. Boundary Coverage
entry point → application/domain behavior → persistence or external boundary → observable result

## 7. Inherited Invariants
- INV-01: ...

## 8. Slice-Specific Rules
- BR-01: ...

## 9. Acceptance Criteria
A1. THE <system> SHALL <observable behavior>.
A2. WHEN <event>, THE <system> SHALL <observable behavior>.
A3. WHILE <state>, THE <system> SHALL <observable behavior>.
A4. IF <condition>, THEN THE <system> SHALL <observable behavior>.
A5. WHERE <feature is enabled>, THE <system> SHALL <observable behavior>.

Use only relevant EARS forms. Give each criterion one primary observable outcome.
Include material failure or absence-of-side-effect behavior when relevant.

## 10. Failure Semantics
| Condition | Observable Result | Side Effects | Recovery |
|---|---|---|---|
| ... | ... | ... | ... |

## 11. Data and Interaction Contract
Define semantic input, output, failure, persistence, and external-interaction requirements.
Do not include method bodies or private implementation design.

## 12. Test Seam and Evidence
- Public seam:
- Required test level:
- Replaceable external boundaries:
- Evidence required per criterion:

## 13. Verification Intent and Plan
Define risk triggers and expected evidence before independent review. The final plan is completed from actual changed paths before completion.

| Check | Applicability / Trigger | Known Command or Discovery Trigger | Expected Evidence | Required for Completion |
|---|---|---|---|---|
| Acceptance behavior | Always | `<repository-native command>` | Observable result for each in-scope criterion | Yes |
| Slice tests | Always | `<repository-native command>` | Slice test suite passes | Yes |
| Type, static analysis, and lint | When configured or affected | `<repository-native command>` or `N/A — <reason>` | No applicable findings | When applicable |
| Affected build | When public or compiled artifacts are affected | `<repository-native command>` or `N/A — <reason>` | Affected build succeeds | When applicable |
| Architecture and policy | When repository checks exist or boundaries change | `<repository-native command>` or `N/A — <reason>` | Relevant policy checks pass | When applicable |
| Regression | When public behavior, shared code, persisted data, or compatibility is affected | `<repository-native command>` or `N/A — <reason>` | Relevant regression suite passes | When applicable |
| Security | When authorization, authentication, secrets, privacy, or trust boundaries are affected | `<repository-native command>` or `N/A — <reason>` | Security behavior and abuse cases pass | When applicable |
| Data and migration compatibility | When schemas, persistence, serialization, or migrations are affected | `<repository-native command>` or `N/A — <reason>` | Compatibility and migration checks pass | When applicable |
| Performance and concurrency | When the contract states such a constraint or the changed path is concurrency-sensitive | `<repository-native command>` or `N/A — <reason>` | Contract-backed performance or concurrency evidence | When applicable |
| Reliability and flake | When timing, retries, async boundaries, or flaky-test history is relevant | `<repository-native command>` or `N/A — <reason>` | Stable repeated or failure-recovery evidence | When applicable |
| Coverage | When repository policy or the approved contract defines a threshold | `<repository-native command>` or `N/A — <reason>` | Required threshold or risk-based evidence | When applicable |

Do not invent numeric thresholds. Before approval, identify every applicable risk trigger and known command. Before completion, every applicable row must have an exact executed command and actual evidence. If a check is not applicable, record the reason. An unexecuted required check blocks completion.

## 14. What Could Be Wrong
- Assumption:
- Consequence:
- Validation method:

## 15. Done When
- Every criterion has passing evidence.
- Every applicable Verification Plan row has passing evidence or an explicit `N/A` reason.
- No contract requirement is weakened.
- No unrelated behavior changes.

## 16. Open Decisions
| ID | Question | Options | Trade-off | Recommendation |
|---|---|---|---|---|
| Q-01 | ... | ... | ... | ... |
```

Do not set `Independent Review: Passed` when verification intent is missing, a material risk trigger has no resolution path, expected evidence is absent, or a triggered specialized check is omitted.

After drafting all slices, run the independent Contract Reviewer defined in [orchestration.md](orchestration.md). The reviewer must inspect the approved parent and the complete slice set together so omissions, overlaps, and cross-slice dependencies are visible.

The reviewer does not edit or approve contracts. The main agent may correct proposed slice contracts when findings expose a mismatch with the approved parent, then rerun review. Set `Independent Review: Passed` only when no blocking or material unresolved finding remains. Do not approve or implement generated slices. Report their ordered paths, dependencies, review result, Open Decisions, and the recommended first slice.

## Amend an approved contract

Identify the exact affected clauses, new evidence or user decision, and impact on child slices, tests, public behavior, persisted data, and compatibility. If the amendment changes the hardened intent, rerun the relevant Intent Hardening Interview and update its decision records and glossary entries. Remove contradictory old text.

- For a parent amendment, return the parent to `Contract Status: Proposed`, setting `Intent Status: Interviewing` when intent must be re-hardened. Reapprove it only when the parent approval conditions above are met.
- For a slice-only amendment that remains within the unchanged parent's scope, invariants, and acceptance criteria, preserve the parent's state. If the change requires altering the parent, obtain authority to amend that parent and follow the parent amendment flow.
- Reset the amended slice and every other affected slice to both `Contract Status: Proposed` and `Independent Review: Pending`; prior approval and review do not cover the amended requirements. Preserve unaffected slices and record why they are unaffected.

Affected slices require renewed independent review and explicit approval covering the amended content before implementation or resumed delivery. Do not change production code during amendment.

When a later contract replaces the original wholesale, create the replacement using the durable naming pattern and retire the original according to repository lifecycle policy.
