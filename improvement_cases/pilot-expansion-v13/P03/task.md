# P03: streamed release archive import

Implement exactly `lib/manifest_codec.dart` and `lib/archive_importer.dart`. Other repository files are protected, including dependency files, API, and tests. Pure Dart business logic only. No filesystem, UI, devices, providers, network, clocks, or secrets are needed. Run `dart analyze` and `flutter test --reporter expanded` offline when available. The inherited package name is intentionally unchanged to preserve the supplied offline dependency lock.

A release deployment service receives an authenticated JSON manifest and a decoded archive stream. Implement manifest validation and staged atomic import using the protected public declarations in `lib/contracts.dart`. This fixture does not ask you to implement ZIP parsing or cryptography.

## R1: manifest contract

`ManifestCodec(Integrity integrity)` exposes `Manifest decode(String text, String tag)` and static `bool validPath(String path)`. All invalid manifests throw `InvalidManifest`. No other decode errors escape. Decode has no storage access.

First reject text whose UTF-8 encoding exceeds 16,384 bytes without calling integrity. Then call the trusted `verifyManifest(text, tag)` exactly once on the exact original text and tag. A false value fails before parsing JSON. The verifier never throws. Do not replace this callback with local hashing. JSON uses SDK `jsonDecode` semantics: duplicate keys take their last effective value. No canonical whitespace or field order requirement exists.

The effective root has exactly `version` and `files`. Version is Dart int 1, not floating 1.0. Files is a list of 1..64 objects. Every object has exactly string `path`, Dart int `size`, and string `digest`. Size is 0..65,536 bytes inclusive. The sum of sizes is at most 262,144 bytes inclusive. Digest is exactly 64 lowercase hexadecimal characters. Paths are unique and case sensitive. No file path may be a directory prefix of another file path, e.g. `a` and `a/b` conflict. A valid returned Manifest preserves list order and contains an unmodifiable defensive copy.

A path is 1..160 ASCII characters and consists of slash-separated nonempty segments. Each segment matches `[A-Za-z0-9][A-Za-z0-9._-]{0,39}`. Thus absolute paths, backslashes, drive prefixes, empty segments, `.` and `..` segments, percent encodings, control characters, and non-ASCII are rejected. Do not trim, decode, case-fold, or normalize paths. A dot inside a segment, e.g. `v1.2/a.txt`, is valid. Apply exactly the same policy to manifest and archive paths.

## R2: importer entry point and precedence

`ArchiveImporter({required ImportStore store, required Integrity integrity})` exposes `Future<ImportResult> import(String manifest, String tag, Stream<ArchiveEntry> entries, Cancellation cancellation)`.

The constructor performs no I/O. The importer has one per-instance busy flag. An overlapping call immediately returns busy without verifying, subscribing to source, or calling storage, even if its token is cancelled. Different instances are independent. Hold busy until the first operation including rollback has finished, then release it for reuse.

After busy acquisition, check cancellation, decode the entire manifest, check cancellation, call begin exactly once, and check cancellation after successful begin. Do not subscribe to the archive before successful begin. An initially cancelled call does not verify or access source/store. Invalid manifests do not access source/store. Errors return a code, never raw exception text. Every failure has zero files and zero bytes.

## R3: streamed bounded entry processing

Process archive entries in stream order and each entry's chunks in stream order. After receiving each entry, check cancellation. Before subscribing to its chunks, reject invalid path, any kind other than exact `file` (including directories and symlinks), a path absent from the manifest, or a repeated path. They all yield invalidEntry. Empty archives and missing manifested files yield invalidEntry after normal end. Ordering need not match the manifest.

After receiving each chunk, check cancellation. Each element must be int 0..255. Invalid bytes yield invalidEntry before size checks or write. Empty chunks are allowed. Check cumulative file and total bytes before writing the chunk. Exceeding the declared file size, 65,536 per file, or 262,144 total yields limitExceeded. Never write any bytes from an invalid or over-limit chunk. Do not collect the whole archive before writes. Each valid chunk produces exactly one awaited write with a defensive immutable copy and the exact manifest path, then a cancellation check. Bounded per-file buffering up to the declared limit is allowed for the supplied digest callback.

After normal file end, check cancellation. A short file or digest mismatch yields integrityMismatch. Call trusted sha256Hex once for each normally completed file whose size matches, including a zero-byte file. It returns 64 lowercase hex characters and never fails for valid bytes. Compare exact digest, do not implement alternate hashing. After validating an empty file, perform one additional empty write so the staged file exists, then check cancellation. Nonempty files get no extra empty write.

## R4: publication, cancellation, rollback, and reuse

After normal archive end, check cancellation then verify every manifested file was received. Call publish exactly once only when all entries, lengths, and digests pass. Success reports exact file count and total bytes. Publish atomically replaces the complete live release with the stage, removing old live files. There are no incremental live updates. A successful publication returns ok even if cancellation changed during publish. No cancellation check follows successful publish. Never rollback a successful publication.

Before publication, cancellation observed at the specified checkpoints returns cancelled. There is no separate race or active subscription interruption requirement while an awaited source/store operation is pending. A failing await's exception takes precedence over cancellation changed during that await. Archive or chunk streams throw only SourceUnavailable. Store begin/write/publish throw only StorageUnavailable, before side effects for that failing call. These map to sourceUnavailable and storageUnavailable. Store methods are otherwise reliable. Rollback cannot throw and deletes the stage without changing live data. Begin creates an empty private stage and returns a unique opaque ID. Write appends bytes to a staged file, creates a missing file even for an empty chunk, and copies input before its Future completes. Publish consumes the stage. No ambiguous commit acknowledgement exists.

For every failure after a successful begin, await exactly one rollback with that stage ID before returning the result. A failed begin has no stage and receives no rollback. A failing stage must not contaminate a later successful import on the same instance. Never call publish following a failed entry. Preserve the previous live release on all failures. Source streams need not be re-readable and must be subscribed at most once. Streams may have side effects, so rejected entry bodies must never be subscribed. Do not access disk directly.
