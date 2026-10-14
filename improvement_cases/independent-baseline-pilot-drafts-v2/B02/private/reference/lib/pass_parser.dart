String? parsePass(String raw) {
 // URI query decoding turns literal + into space, so the path is decoded directly.
 if (!raw.startsWith('museum-pass:')) return null;
 final payload=raw.substring('museum-pass:'.length);
 if(payload.isEmpty || payload.length>96 || !RegExp(r'^[A-Za-z0-9_-]+$').hasMatch(payload)) return null;
 return payload;
}
