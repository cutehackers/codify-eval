# Workspace note backup import

Implement `NoteImportService.importBackup` for restoring a workspace note backup. Users restore backups into an existing workspace and continue editing its notes. A backup can be older than notes already present.

For example, a workspace contains note n-1 titled Monday plan with body Send final draft. A backup contains n-1 titled Monday plan with body Send first draft, and a new note n-2.

Parse the JSON, check workspace access, and import the notes consistently. Return the supplied report for the UI. Edit only `lib/implementation.dart`. Models, schema constants and the in-memory transactional store are protected. Add no dependencies and run the supplied Dart/Flutter checks. No device, network or provider is required.

## Contract

- C01: Before parsing or note reads, require the current supplied identity user to have edit permission for the requested target workspace. Missing workspaces and denied permission return `access_denied`. Never derive identity from JSON.
- C02: Parse a JSON object containing exactly `version`, `workspaceId`, and `notes`. Version must be the integer 1, workspaceId a string exactly equal to the requested target, and notes a list. Reject malformed JSON, unsupported versions, wrong types, missing fields and additional fields with `invalid_backup` before note reads or writes.
- C03: Each note must be an object containing exactly string `id`, `title`, and `body`. Reject a whitespace-only ID, duplicate exact IDs, wrong types, missing or additional fields. IDs are compared exactly, with trimming only for blank detection. Validate every note before note reads or writes. A bad later note rejects the whole backup.
- C04: Maximum notes is 20, title length 80 and body length 1000. Length means Dart String.length (UTF-16 code units). Limits are inclusive. Empty title/body and empty note list are valid. Preserve accepted strings exactly, including Unicode and line breaks. Do not normalize content.
- C05: Insert IDs absent from the target workspace with their incoming title/body exactly. The supplied Note constructor's default metadata applies to a new note. Existing notes with identical title/body remain unchanged, including metadata, with no rewrite.
- C06: Return `ok` for successful imports. Each incoming ID occurs exactly once across insertedIds, updatedIds and unchangedIds. Each list follows input order and describes actual persisted effects. Notes absent from the backup and other workspaces stay unchanged.
- C07: Apply changes using the atomic store operation only after validation. Storage failure returns `storage_failure` with all report lists empty, leaves all notes unchanged and does not expose exception text. A successful no-change import must not rewrite notes. No store apply is required when no notes change.
- C08: The operation is synchronous. Store snapshots are isolated copies and apply is atomic. UI, backup filesystem, live persistence, encryption and adapter construction are outside the change.

Validation order is C01, JSON and top-level schema including target match, C03/C04 for every record, note snapshot, import planning, C07. Complete result codes are `ok`, `access_denied`, `invalid_backup`, `storage_failure`. Every error result has empty report lists.
