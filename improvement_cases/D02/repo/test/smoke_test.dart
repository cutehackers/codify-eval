import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/main.dart';

class Allow implements AccessPolicy {
  @override
  bool canRead(String owner) => true;
  @override
  bool canWrite(String owner) => true;
}

class Memory implements DocumentFiles {
  final data = <String, String>{};
  @override
  Future<String?> read(String key) async => data[key];
  @override
  Future<void> write(String key, String contents) async {
    data[key] = contents;
  }
}

void main() {
  test('basic save can be loaded', () async {
    final repository = DocumentRepository(Memory(), Allow());
    await repository.save('alice', 'draft', 'hello');
    expect(await repository.load('alice', 'draft'), 'hello');
  });
}
