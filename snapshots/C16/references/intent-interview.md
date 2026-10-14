# Intent Hardening Interview

Use this reference for every Specify request before normalizing a parent specification. The interview sharpens the user's intent, exposes material uncertainty, and records decisions and terminology as they emerge. Completing its Hardening Gate establishes intent readiness. Apply the [parent approval rules](specification.md#approve-a-contract) separately; neither intent readiness nor parent approval approves child slices or authorizes implementation.

## Interview states

Track one of these states in the working record or proposed parent contract:

- `Interviewing`: questions remain and the intent is not ready for normalization.
- `Hardened`: the hardening gate passes and the parent contract may be normalized; its approval state is determined separately.
- `Blocked`: a material decision is unresolved and requires user judgment or external evidence.
- `Draft-only`: the user explicitly requested a fast draft before answering questions. It is not eligible for approval, slicing, or implementation.

## Stable intent and goal IDs

During the interview, assign stable IDs to the normalized intent map:

- `INT-*` identifies a parent problem or intent to solve.
- `GOAL-*` identifies an observable user or caller goal that advances an intent.

Each `GOAL-*` must reference one primary `INT-*`. Reuse IDs when the contract is amended. Do not create a slice goal without a parent mapping, and do not treat a technical layer, component, or implementation task as a goal.

## Group questions for effective decisions

Do not force every question into a separate turn. Group easy, related questions that share the same decision context and can be answered without depending on another unanswered decision. Present the group with a short explanation of why it matters and let the user answer all or part of it.

Split a question out of a group when its answer changes another question, requires different evidence, affects public behavior or risk, or would be easy to miss among lower-risk questions. Do not dump a complete questionnaire on the user. Select the next group based on uncertainty, impact, and dependency.

Use groups such as:

| Group | Verify | Example questions |
|---|---|---|
| Outcome and actors | Problem, user, trigger, observable result | Who has the problem? What starts the flow? What result proves completion? |
| Scope and state | In-scope behavior, non-goals, state changes | What is included? What is explicitly excluded? What states can the subject enter or leave? |
| Rules and acceptance | Business rules, invariants, measurable success | What must always be true? How can a test or operator observe success and failure? |
| Boundaries and failure | Invalid input, authorization, duplicate, retry, concurrency, timeout, partial failure, recovery | What happens when this input is invalid, repeated, unauthorized, interrupted, or concurrently changed? |
| Data and compatibility | Ownership, persistence, privacy, migration, compatibility | What data is created or changed? Who owns it? What existing clients or records must continue to work? |
| Alternatives and trade-offs | Material decisions and rejected options | Which options were considered? Why is the selected option preferred? What consequence is accepted? |
| Language and evidence | Ambiguous terms, sources, assumptions | What does this term mean in this product? Which statement comes from the user, repository, or external evidence? |

These are prompts, not a mandatory checklist. Skip irrelevant groups, but record why a material group does not apply when that conclusion is not obvious.

## Interview loop

1. Resolve all initial sources, inspect the relevant repository instructions, and identify the target project's applicable `AGENTS.md` files before choosing documentation paths or formats.
2. Extract the user's explicit intent, constraints, decisions, unknowns, vague terms, and possible contradictions without filling gaps from convention. Assign stable `INT-*` IDs to parent intents and `GOAL-*` IDs to their observable user or caller goals.
3. Select the highest-impact unresolved group. Combine low-risk questions when the user can decide them together.
4. After each answer, classify it as a confirmed user decision, repository fact, external evidence, assumption, or Open Decision. Do not silently convert an inference into a decision.
5. Update the working intent record, the intent-to-goal map, relevant decision records, and glossary entries before presenting the next group.
6. Restate the current intent, newly resolved decisions, remaining risks, and the next grouped questions. Continue until the hardening gate passes or a blocker is explicit.
7. Run an adversarial pass over the relevant happy path, invalid path, unauthorized path, duplicate or retry path, concurrent path, partial-failure path, and recovery path. Include migration, rollback, or compatibility scenarios when the feature touches them.

## Relentless verification rules

- Do not accept adjectives such as “fast,” “safe,” “simple,” or “scalable” without an observable interpretation. If the user does not provide a number, do not invent one. Record the missing measure as an Open Decision or validation method.
- Ask who can observe each result and what evidence distinguishes success from failure.
- Challenge each material requirement with at least one relevant counterexample or absence-of-side-effect question.
- Surface conflicts between the prompt, source files, repository behavior, and prior contracts. Report the conflict instead of choosing silently.
- Stop for user judgment when uncertainty changes public behavior, persisted data, authorization, security, migration, compatibility, monetary behavior, destructive behavior, or the acceptance result.
- Continue asking grouped questions when uncertainty is non-material but would make the contract ambiguous. Use the narrowest reversible assumption only when the consequence and validation method are recorded.

## Decision records created during the interview

Decision records are ADR-equivalent records, even when the project uses a different name or a single file.

1. Inspect all applicable project `AGENTS.md` instructions before selecting a path, filename, or format. Follow the most specific applicable convention. If project instructions conflict, stop and report the conflict.
2. Use the project-defined structure exactly. For example, if `sgp-981-app` specifies `docs/DECISIONS.md`, append the decision there rather than creating `docs/design/decisions/` files.
3. Only when no project convention exists, use `docs/design/decisions/YYYY-MM-DD-<decision>.md`.
4. Create or update a decision record as soon as a material decision is resolved. Mark it Accepted only when the user explicitly accepts the decision or the project lifecycle defines an equivalent explicit approval. A direct user instruction or an unambiguous answer selecting the decision counts as acceptance; record that source without requesting duplicate approval. Keep agent recommendations and inferences Proposed. Follow the [parent approval rules](specification.md#approve-a-contract); passing the Hardening Gate or approving the parent must not silently accept Proposed decision records.
5. Record all applicable intent-hardening content. At minimum, preserve status, parent or feature link, source and evidence, context or problem, decision, alternatives and rejected alternatives, rationale and trade-offs, consequences, affected invariants or acceptance criteria, and related Open Decisions or follow-ups. Map these fields into the project-native format without omitting them because they also appear in the parent specification.

If the project uses one decision log, keep one clearly identified ADR-equivalent entry per material decision and retain the same fields. Do not impose one-file-per-decision structure over a project rule.

## Glossary updates during the interview

Follow the project's `AGENTS.md` documentation convention when it defines a glossary location or format. If it does not, use `docs/design/glossary.md`. Add or update a term when its meaning affects scope, behavior, acceptance, or a decision.

Each entry should include the term, operational definition, scope, source, status, and links to related parent specs or decision records. Use `Candidate` or `Open` for unresolved language and `Confirmed` only when the meaning is supported by the user, repository evidence, or an explicit decision. Do not choose between competing meanings silently.

## Hardening gate

Set `Intent Status: Hardened` only when:

- the problem, primary actor, trigger, and observable outcome are stated;
- In Scope and Non-Goals are separated;
- business rules and acceptance conditions are observable;
- relevant boundary and failure behavior is answered or explicitly tracked;
- material data, authorization, security, migration, compatibility, and recovery questions are resolved or blocked explicitly;
- every `INT-*` has at least one `GOAL-*`, and each goal is stated as an observable user or caller result;
- each material decision has its alternatives, rationale, consequences, source or evidence, and linked follow-ups recorded;
- ambiguous terms are defined in the glossary or remain explicitly Open;
- assumptions are labeled with consequences and validation methods;
- no unresolved contradiction or material Open Decision is hidden in the normalized contract.

When the gate fails because of a material unresolved decision, set `Intent Status: Blocked` and do not approve, slice, or implement the parent. When the gate passes, normalize the parent specification with links to the decision records and glossary, then determine its `Contract Status` using the [parent approval rules](specification.md#approve-a-contract). Preserve `Draft-only` and requests to retain Proposed. Keep child slices subject to independent review and explicit approval.

## Turn summary

After each interview turn, report a compact state summary:

```markdown
Intent Status: Interviewing | Hardened | Blocked | Draft-only
Resolved:
- ...

Intent and goal map:
- INT-01 → GOAL-01: ...

New or updated decision records:
- ...

Glossary updates:
- ...

Open Decisions and risks:
- ...

Next question group:
1. ...
2. ...
```
