import 'api.dart';
class OwnedDraftStore {
 final Session session; final DraftDisk disk;
 OwnedDraftStore(this.session,this.disk);
 Future<SaveResult> save(String id,String title,int expectedRevision) async {
  try {final old=await disk.read(id); if(old==null)return const SaveResult(SaveCode.denied,'Access denied');
   final next=Draft(id,old.ownerId,title,expectedRevision+1); await disk.replace(next,expectedRevision:expectedRevision);
   return SaveResult(SaveCode.saved,'Saved',next);
  } catch(e) {return SaveResult(SaveCode.unavailable,e.toString());}
 }
}
