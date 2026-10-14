---
name: codify
description: Deliver a requested code change through evidence-led, risk-adaptive development with focused parallel orchestration. Use $codify when the user wants Codex to take a feature or proposal from intent through verified delivery, with stronger contracts only when the change warrants them.
---

# Codify

Turn a user request into a scoped, verified result. Use Codex's repository understanding, tools, and long-running execution to finish ordinary work directly. Add durable contracts, independent review, and approval gates only when their absence could change a consequential outcome.

## Resolve the work

Infer the target from an explicit path or ID, an attached or discussed document, the current request, the sole matching artifact, or the next incomplete artifact of the active feature. Inspect the repository before asking. Ask one focused question only when the answer materially changes public behavior, persisted data, authorization, security, money, destructive effects, compatibility, or the acceptance result.

Read applicable repository instructions, architecture and testing contracts, neighboring code and tests, validation commands, and relevant working-tree changes before asserting repository facts or editing files. Preserve unrelated changes and use repository conventions over generic ones.

## Choose the smallest useful mode

Classify the requested change after discovery:

| Risk | Use when | Workflow |
|---|---|---|
| Low | Local, reversible behavior with clear acceptance and no sensitive boundary | Inspect → implement → focused verification → diff inspection |
| Medium | Multiple modules, shared behavior, ambiguous rules resolved by repository evidence, or meaningful regression risk | Write a compact implementation contract → implement → risk-triggered verification → diff inspection |
| High | Public API, persisted data or migration, authorization or privacy, money, destructive behavior, compatibility, or unresolved product decisions | Clarify consequential uncertainty → record a durable contract when useful → independent review when it can expose material risk → implement and verify |

Do not create a specification, decision record, glossary entry, slice, or approval pause merely because the request is code work. Create durable artifacts only for product, architecture, policy, or interface decisions that must remain understandable after the current task.

For an explicit request to specify, slice, amend, approve, verify, or report status, honor that requested mode. Read [references/specification.md](references/specification.md) for durable contracts, [references/intent-interview.md](references/intent-interview.md) when hardening intent is needed, and [references/delivery.md](references/delivery.md) for delivery or verification.

## Model-neutral execution

Keep one coherent owner for scope interpretation, implementation, test-failure diagnosis, and final diff inspection. The owner may be the current session agent or an explicitly assigned implementation agent. The workflow must remain valid regardless of the model selected for that agent.

Delegate only when it materially improves independence or elapsed time:

- use a read-only reviewer for a high-risk contract or a meaningful independent challenge to a proposed diff;
- parallelize non-overlapping repository discovery when its result will inform the same decision;
- use a bounded implementation worker only when its file boundary, acceptance criteria, and merge responsibility are explicit;
- use a mechanical worker only for bounded command execution or result collection.

Treat model selection as an execution setting, not a Codify policy. Use the runtime's explicit spawn setting, custom agent configuration, or agent defaults to choose a model and reasoning effort. Do not infer a model from this skill or require a named model to make the workflow valid.

When delegation is useful, follow the runtime's model policy and read [references/orchestration.md](references/orchestration.md) for role boundaries and review questions. A delegated result is evidence; the owner still decides what to implement and what verification supports completion.

## Evidence-led implementation

Implement the smallest complete behavior supported by the request and repository evidence. Use behavior-focused tests for new or changed behavior when they provide meaningful proof. Apply Red → Green to a coherent observable behavior, not mechanically to every sentence of an acceptance list. Do not add tests that only duplicate trivial, reversible implementation details.

Build the verification plan after discovery and refine it once the changed paths are known. Run focused checks first, then broaden only when the changed behavior, repository policy, a failure, or an unresolved risk requires it. Every completion claim needs current inspectable evidence; report any required but unexecuted check and why.

## Deliver complete slices

For multi-slice or sustained implementation, track progress against the original user outcomes and acceptance criteria from the start. Keep one active implementation slice by default and finish its user-visible path before starting adjacent improvements. Record defects outside that path for later; pull them into the active slice only when they block its correctness or completion. Do not replace an unmet requirement with an easier case or a narrower completion claim.

Use [references/delivery.md](references/delivery.md) for the acceptance evidence map, repeated-gap diagnosis, and slice closure. When independent review is warranted, [references/orchestration.md](references/orchestration.md) distinguishes implementation review from outcome review. Passing a diff review does not prove that a slice delivers its intended outcome.

## Authority and completion

Resolve conflicts in this order: current user instruction, explicitly approved contract, repository architecture and policy, existing public behavior and tests, then local convention. Report a real conflict instead of silently changing intended behavior. Keep assumptions narrow, reversible, and visible.

Lead with the delivered outcome. State the changed behavior, evidence and commands run, remaining risk or unexecuted checks, and any durable artifact created. Distinguish proposed, approved, and implemented work.
