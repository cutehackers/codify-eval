import 'contracts.dart';

class EventProcessor {
  EventProcessor({
    required String tenantId,
    required AccessContext context,
    required CheckpointStore store,
    required IntegrityService integrity,
  });
  TenantView? get current => null;
  Future<ProcessorResult> restore() async =>
      ProcessorResult(code: ProcessorCode.notInitialized);
  Future<ProcessorResult> ingest(String batchJson) async =>
      ProcessorResult(code: ProcessorCode.notInitialized);
}
