import 'models.dart';
import 'job_rules.dart';
class Outbox {
  final OutboxStore store;
  final RepairApi api;
  Future<void> _tail = Future.value();
  Outbox(this.store, this.api);
  Future<SyncSummary> flush(String tenant) {
    final result = _tail.then((_) => _flush(tenant));
    _tail = result.then<void>((_) {}, onError: (Object e, StackTrace s) {});
    return result;
  }
  Future<SyncSummary> _flush(String tenant) async {
    List<Job> jobs;
    try { jobs = List.of(await store.read()); }
    catch (_) { return const SyncSummary(0, 0, 0, storageUnavailable:true); }
    var sent=0, retried=0, rejected=0;
    for (var i=0;i<jobs.length;i++) {
      final j=jobs[i];
      if (j.tenant!=tenant || j.state!='pending') continue;
      Job next;
      if (!validJob(j)) {
        next=j.copy(state:'rejected');
      } else {
        SendResult answer;
        try { answer=await api.send(j, deliveryKey(j)); }
        catch (_) { answer=const SendResult('network', retryable:true); }
        next=answer.code=='accepted' ? j.copy(state:'sent') :
            answer.retryable ? j.copy(attempts:j.attempts+1) : j.copy(state:'rejected');
      }
      final updated=List<Job>.of(jobs)..[i]=next;
      try { await store.replace(updated); }
      catch (_) { return SyncSummary(sent,retried,rejected,storageUnavailable:true); }
      jobs=updated;
      if(next.state=='sent') {sent++;}
      else if(next.state=='rejected') {rejected++;}
      else {retried++;}
    }
    return SyncSummary(sent,retried,rejected);
  }
}
