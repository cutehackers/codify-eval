import 'models.dart';
class Outbox {
 final OutboxStore store; final RepairApi api;
 Outbox(this.store,this.api);
 Future<SyncSummary> flush(String tenant) async => const SyncSummary(0,0,0);
}
