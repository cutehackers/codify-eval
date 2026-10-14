import 'api.dart';
class RetentionService {
 final JournalDisk disk; final Clock clock;
 RetentionService(this.disk,this.clock);
 Future<RetentionPreview> preview()async {
  final now=clock.now().toUtc();
  final cutoff=now.subtract(const Duration(days:30));
  final records=await disk.readAll();
  final ids=records.where((r)=>r.completed && !r.completedAt.toUtc().isAfter(cutoff)).map((r)=>r.id).toSet();
  return RetentionPreview(ids,now);
 }
 Future<int> apply(RetentionPreview preview)async {
  if(preview.ids.isEmpty)return 0;
  await disk.deleteIds(preview.ids);
  return preview.ids.length;
 }
}
