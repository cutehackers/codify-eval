abstract class LocalStore {
  Future<String?> read();
  Future<void> write(String value);
}

class MemoryStore implements LocalStore {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String value) async {
    this.value = value;
  }
}
