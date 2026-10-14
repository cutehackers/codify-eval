import 'api.dart';
class OwnedDraftStore {
 final Session session; final DraftDisk disk;
 OwnedDraftStore(this.session,this.disk);
 Future<SaveResult> save(String id,String title,int expectedRevision) async {
  try {
   final user=await session.current();
   if(user==null)return const SaveResult(SaveCode.denied,'Access denied');
   if(!RegExp(r'^[A-Za-z0-9_-]{1,64}$').hasMatch(id) || expectedRevision<0 || title.trim().isEmpty || title.runes.length>120 || title.contains(RegExp(r'[\r\n]')))return const SaveResult(SaveCode.invalid,'Invalid draft');
   final old=await disk.read(id);
   if(old==null)return const SaveResult(SaveCode.denied,'Access denied');
   if(old.revision!=expectedRevision)return const SaveResult(SaveCode.conflict,'Draft changed');
   final next=Draft(old.id,old.ownerId,title.trim(),old.revision+1);
   final saved=await disk.replace(next,expectedRevision:expectedRevision);
   if(!saved)return const SaveResult(SaveCode.conflict,'Draft changed');
   return SaveResult(SaveCode.saved,'Saved',next);
  } catch(_) { return const SaveResult(SaveCode.unavailable,'Draft unavailable'); }
 }
}
