import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/contracts.dart';
import 'package:fixture_app/batch_service.dart';
import 'package:fixture_app/batch_validator.dart';
import 'support.dart';

void main() {
  test('public API can be constructed and returns a typed result', () async {
    final store = MemoryStore([const Account('a', 'team', 100), const Account('b', 'team', 0)]);
    final service = BatchService(store, TestAuthorizer());
    final result = await service.submit(const Actor('user', 'team'),
        BatchCommand('team', 'key', [const Transfer('one', 'a', 'b', 10)]));
    expect(result, isA<BatchResult>());
    expect(result.receipt != null || result.failure != null, isTrue);
  });
  test('empty command is a typed validation failure', () {
    expect(BatchValidator().validate(BatchCommand('team', 'key', [])).failure,
        FailureCode.invalid);
  });
}
