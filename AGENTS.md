# Codify Evaluation

This repository owns evaluation specifications, isolated fixtures, runners and evidence.
Do not edit real application repositories, the vault, or their raw sources.

- Use `gpt-6.1-sol` with `medium` reasoning for every evaluation agent. Do not substitute another model.
- Keep the Flutter software outcome evaluation separate from contract/approval checks.
- Evaluated agents receive only their task, starting repository and selected skill variant. Never provide oracle tests, references, other runs or expected answers.
- Preserve raw run evidence during evaluation. After completion, raw artifacts may be deleted only on explicit user instruction; retain reports and core result summaries, and document the loss of raw re-auditability. A timeout or unsuccessful run is not a passing result.
- Freeze case, skill, runtime and grader hashes before a comparison. A changed candidate receives a new version.
- Do not commit credentials. Do not claim mobile/device or production verification from widget tests.
- Fixture workers own fixtures; runner and specification changes remain with the root owner. Reviewers are read-only.
