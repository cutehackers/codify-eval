# Offline project document feed importer
Implement an offline Dart service that safely imports a bounded JSON Lines event feed into an atomic store. All product choices below are final. Proceed through implementation and verification without asking for additional product choices. Only lib/models.dart and lib/implementation.dart may change. Preserve public signatures.

The input contains 1..100 nonblank lines, separated by LF or CRLF. A trailing newline is allowed. Empty lines are ignored. The complete string must be at most 65536 UTF-8 bytes. Each nonblank line is one JSON object with EXACT keys `seq`, `tenant`, `project`, `id`, `version`, `op`, `text`. Sequence and version must be positive Dart integers, never bool, double or numeric strings. Tenant/project/id match `[A-Za-z0-9_-]{1,40}`. op is `put` or `delete`. For put, text is a string of at most 4096 UTF-8 bytes, may be empty, and cannot contain NUL. For delete, text must be null. Bad JSON, unsupported keys/types/operations, empty input and violated size/field constraints yield `FeedException('invalid')`.

Validation of every line precedes any store-dependent processing. Then authorize every event: principal tenant, store tenant and event tenant must match, and principal.writableProjects must contain each event's project. If any authorization fails, return `forbidden` before replay/version/gap errors. Never partially import.

The store starts from a valid state. documents keys are globally unique IDs within the tenant. History maps all previously committed sequence numbers to replay fingerprints. Do not trim it. A live document's project is immutable: an event for its ID under another project yields `conflict`, even if the caller can write both projects.

Process valid authorized events in their input order on a staged copy:
- For seq <= staged.sequence: identical historical event means duplicate and no effect. A missing historical record or changed event at that seq yields `replay_conflict`. Identity includes all seven semantic fields, independent of JSON key order or whitespace.
- A new event must have seq == staged.sequence+1. Otherwise `gap`. New put requires version=1 for an absent ID, or exactly existing version+1 for a live ID. A new delete requires a live ID and version exactly existing version+1. Otherwise `version`. Deletion removes the document. Recreating a deleted ID begins at version 1. Old deletion replay must never delete a recreated document.
- Successful new events update sequence and history. Count duplicate entries and applied new entries separately. New events duplicated later within the same input count as duplicates. An all-duplicate input does not call replace.
- After processing all lines, call store.replace exactly once if there are new events. On storage failure return `storage`, expose no underlying diagnostics, and leave sequence, documents and history unchanged. The same batch must be retryable. Do not retry automatically.
- Returned state collections must be immutable. Preserve unrelated documents and all history. FeedImporter recreation must preserve replay protection.

Example at empty state: put seq=1 tenant=t project=p id=a version=1 text=hello, followed by put seq=2 of a version=2 text=world yields sequence=2, applied=2, duplicates=0, a.text=world. Repeating those lines returns applied=0, duplicates=2, sequence=2.

Use only Dart standard libraries plus test. Run analyzer and public tests. No device, network, database or wall-clock dependence.
