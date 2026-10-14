import 'contracts.dart';

class CheckpointCodec {
  CheckpointCodec(IntegrityService integrity);
  String encode(CheckpointState state) => throw InvalidCheckpoint();
  CheckpointState decode(
    String checkpoint, {
    required String expectedTenant,
    required int expectedRevision,
  }) => throw InvalidCheckpoint();
}
