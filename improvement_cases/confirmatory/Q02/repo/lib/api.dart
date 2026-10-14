const contractVersion = 1;
class Principal { final String id; const Principal(this.id); }
abstract class Session { Future<Principal?> current(); }
class Draft { final String id; final String ownerId; final String title; final int revision; const Draft(this.id,this.ownerId,this.title,this.revision); }
abstract class DraftDisk {
 Future<Draft?> read(String id);
 // Atomic compare-and-replace. Returns false if revision changed.
 Future<bool> replace(Draft next, {required int expectedRevision});
}
enum SaveCode { saved, denied, invalid, conflict, unavailable }
class SaveResult { final SaveCode code; final String message; final Draft? draft; const SaveResult(this.code,this.message,[this.draft]); }
