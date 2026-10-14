import 'dart:convert';
import 'models.dart';
class FeedImporter {
 final FeedStore store;
 FeedImporter(this.store);
 FeedResult ingest(Principal principal,String jsonLines){
  Never invalid()=>throw const FeedException('invalid');
  if(utf8.encode(jsonLines).length>65536) invalid();
  final lines=jsonLines.split('\n').where((s)=>s.trim().isNotEmpty).toList();
  if(lines.isEmpty||lines.length>100) invalid();
  final events=<Map<String,dynamic>>[];
  final pattern=RegExp(r'^[A-Za-z0-9_-]{1,40}$');
  bool valid(String value) => pattern.firstMatch(value)?.end == value.length;
  const keys={'seq','tenant','project','id','version','op','text'};
  for(final line in lines){
   dynamic decoded;try{decoded=jsonDecode(line);}catch(_){invalid();}
   if(decoded is! Map<String,dynamic>||decoded.length!=7||!decoded.keys.every(keys.contains)) invalid();
   final m=decoded;
   for(final k in ['seq','version']){if(m[k] is! int||(m[k] as int)<=0) invalid();}
   for(final k in ['tenant','project','id']){if(m[k] is! String||!valid(m[k] as String)) invalid();}
   if(m['op']=='put'){
    if(m['text'] is! String||utf8.encode(m['text'] as String).length>4096||(m['text'] as String).contains('\x00')) invalid();
   }else if(m['op']=='delete'){if(m['text']!=null) invalid();}else{invalid();}
   events.add(m);
  }
  final original=store.state;
  for(final m in events){
   if(principal.tenant!=original.tenant||m['tenant']!=original.tenant||!principal.writableProjects.contains(m['project'])) throw const FeedException('forbidden');
  }
  final docs=Map<String,Document>.of(original.documents), history=Map<int,String>.of(original.history);
  var seq=original.sequence, applied=0,duplicates=0;
  for(final m in events){
   final n=m['seq'] as int,version=m['version'] as int;
   final id=m['id'] as String,project=m['project'] as String;
   final fingerprint=jsonEncode([n,m['tenant'],project,id,version,m['op'],m['text']]);
   if(n<=seq){
    if(history[n]!=fingerprint) throw const FeedException('replay_conflict');
    duplicates++;continue;
   }
   if(n!=seq+1) throw const FeedException('gap');
   final existing=docs[id];
   if(existing!=null&&existing.project!=project) throw const FeedException('conflict');
   if(m['op']=='delete'){
    if(existing==null||version!=existing.version+1) throw const FeedException('version');
    docs.remove(id);
   }else{
    if(version!=(existing==null?1:existing.version+1)) throw const FeedException('version');
    docs[id]=Document(project,m['text'] as String,version);
   }
   seq=n;history[n]=fingerprint;applied++;
  }
  if(applied>0){
   try{store.replace(FeedState(original.tenant,seq,docs,history));}catch(_){throw const FeedException('storage');}
  }
  return FeedResult(applied,duplicates,seq);
 }
}
