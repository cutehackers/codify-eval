# Document export boundary
Implement `document_export.export_document(request, actor, repository, renderer, storage, audit)`.
Only `document_export.py` may be edited. Dependencies are standard-library only.
Run `python3 -B -m unittest discover -s . -p 'test_smoke.py' -v` in public/.

The caller passes untrusted `request`. Return a dictionary, never an exception.
- INPUT: Require a dict containing exactly doc_id and filename. doc_id is a string matching `[a-z0-9][a-z0-9-]{0,31}`. filename is a string matching `[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}\.json`. Reject paths, extra fields, missing fields and wrong types with `{status: 'invalid_request'}` before calling any dependency.
- AUTH: Call `repository.can_export(actor, doc_id)` once before reading document content. Only the literal boolean True grants access. A denial returns `{status: 'forbidden'}` without calling get, renderer, storage or audit.
- READ: Call `repository.get(doc_id)` once after authorization. None means `{status: 'not_found'}`. A document has exactly id, title and text string fields, id equals doc_id. Invalid repository data returns `{status: 'unavailable'}` without rendering.
- OUTPUT: Call `renderer(document)` once. It must return bytes containing a UTF-8 JSON object with exactly id, title and text string fields matching the repository document. Invalid bytes, malformed JSON, extra fields and altered content return `{status: 'invalid_output'}` before storage or audit. Whitespace and key ordering are irrelevant. Preserve valid renderer bytes exactly.
- EFFECTS: Call `storage.write(filename, bytes)` once, then append `{actor: actor, doc_id: doc_id, filename: filename}` to audit, then return `{status: 'ok', filename: filename, size: len(bytes)}`. audit is a supplied list. No other dependency calls or mutation are permitted. Renderer must receive an independent dictionary so mutations cannot change repository data or the expected export.
- ERRORS: Any dependency exception returns `{status: 'unavailable'}` without exception text or extra fields. Rendering/storage failures produce no audit entry. No filesystem/network IO except the supplied storage. Storage controls persistence and may raise before writing.

Acceptance checks exercise malformed external input, strict permission results, inaccessible/missing documents, mutated renderer inputs, valid and invalid injected output, and dependency failures. Public smoke tests are examples, not exhaustive acceptance.
