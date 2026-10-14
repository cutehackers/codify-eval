class Principal {
 final String tenant;
 final Set<String> writableProjects;
 Principal(this.tenant,Set<String> projects):writableProjects=Set.unmodifiable(projects);
}
class Document {
 final String project, text;
 final int version;
 const Document(this.project,this.text,this.version);
}
class FeedState {
 final String tenant;
 final int sequence;
 final Map<String,Document> documents;
 final Map<int,String> history;
 FeedState(this.tenant,this.sequence,Map<String,Document> documents,Map<int,String> history):documents=Map.unmodifiable(documents),history=Map.unmodifiable(history);
}
class FeedResult {
 final int applied, duplicates, sequence;
 const FeedResult(this.applied,this.duplicates,this.sequence);
}
class FeedException implements Exception {
 final String code;
 const FeedException(this.code);
 @override String toString()=>'FeedException($code)';
}
abstract class FeedStore {
 FeedState get state;
 // Atomic replacement or throw before making changes.
 void replace(FeedState next);
}
class MemoryFeedStore implements FeedStore {
 FeedState _state;
 bool failNextReplace=false;
 MemoryFeedStore(this._state);
 @override FeedState get state=>_state;
 @override void replace(FeedState next){
  if(failNextReplace){failNextReplace=false;throw StateError('storage-password');}
  _state=next;
 }
}
