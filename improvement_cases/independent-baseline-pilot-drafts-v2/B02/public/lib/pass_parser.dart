String? parsePass(String raw) => raw.startsWith('museum-pass:') ? raw.substring(12) : null;
