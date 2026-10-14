import 'package:flutter_test/flutter_test.dart';
import 'package:fixture_app/api.dart';
import 'package:fixture_app/implementation.dart';
class Auth implements Session { Principal? user=const Principal('alice'); bool fail=false; Future<Principal?> current()async {if(fail)throw StateError('token-secret');return user;} }
class Disk implements DraftDisk {
 Draft? value=const Draft('d','alice','old',3); int reads=0,writes=0; bool readFail=false,writeFail=false,conflict=false; Draft? attempted;
 Future<Draft?> read(String id)async {reads++;if(readFail)throw StateError('/private/token-secret');return value;}
 Future<bool> replace(Draft next,{required int expectedRevision})async {writes++;attempted=next;if(writeFail)throw StateError(next.title);if(conflict || value?.revision!=expectedRevision)return false;value=next;return true;}
}
void main(){
 test('authentication precedes access and denial discloses no object',()async{
  final a=Auth()..user=null;final d=Disk();final s=OwnedDraftStore(a,d);
  var r=await s.save('../secret','x',3);expect(r.code,SaveCode.denied);expect(r.message,'Access denied');expect(r.draft,isNull);expect(d.reads,0);expect(d.writes,0);
  a.user=const Principal('mallory');r=await s.save('d','x',3);expect(r.code,SaveCode.denied);expect(r.message,'Access denied');expect(r.draft,isNull);expect(d.writes,0);
  d.value=null;final missing=await s.save('d','x',3);expect(missing.message,r.message);expect(missing.code,r.code);
 });
 test('validation before disk includes traversal newline and Unicode bound',()async{
  for(final args in <List<Object>>[['../x','ok',3],['','ok',3],['d','   ',3],['d','a\nb',3],['d','a\rb',3],['d',List.filled(121,'😀').join(),3],['d','ok',-1]]) {
   final d=Disk();final r=await OwnedDraftStore(Auth(),d).save(args[0] as String,args[1] as String,args[2] as int);expect(r.code,SaveCode.invalid,reason:args.toString());expect(r.message,'Invalid draft');expect(r.draft,isNull);expect(d.reads,0);expect(d.writes,0);
  }
  final d=Disk();final r=await OwnedDraftStore(Auth(),d).save('d',List.filled(120,'😀').join(),3);expect(r.code,SaveCode.saved);
 });
 test('owner revision and atomic conflict determine persistence',()async{
  final d=Disk();final s=OwnedDraftStore(Auth(),d);final stale=await s.save('d','new',2);expect(stale.code,SaveCode.conflict);expect(stale.message,'Draft changed');expect(d.writes,0);
  d.conflict=true;final race=await s.save('d',' new ',3);expect(race.code,SaveCode.conflict);expect(race.draft,isNull);expect(d.value!.title,'old');expect(d.writes,1);
  d.conflict=false;final saved=await s.save('d',' new ',3);expect(saved.code,SaveCode.saved);expect(saved.message,'Saved');expect(saved.draft!.title,'new');expect(saved.draft!.ownerId,'alice');expect(saved.draft!.revision,4);expect(saved.draft!.id,'d');
 });
 test('all dependency errors have a fixed safe public result',()async{
  for(var stage=0;stage<3;stage++) {final a=Auth();a.fail=stage==0;final d=Disk();d.readFail=stage==1;d.writeFail=stage==2;
   final r=await OwnedDraftStore(a,d).save('d','private-title',3);expect(r.code,SaveCode.unavailable);expect(r.message,'Draft unavailable');expect(r.draft,isNull);expect(d.writes,stage==2?1:0);
  }
 });
 test('ASCII ID boundaries and original title validation are explicit',()async{
  for(final id in [List.filled(65,'a').join(),'ä','a.b','a/b','a b','a\nb']) {final d=Disk();final r=await OwnedDraftStore(Auth(),d).save(id,'ok',3);expect(r.code,SaveCode.invalid,reason:id);expect(r.message,'Invalid draft');expect(r.draft,isNull);expect(d.reads,0);expect(d.writes,0);}
  for(final id in ['a',List.filled(64,'a').join(),'A_9-z']) {final d=Disk();final r=await OwnedDraftStore(Auth(),d).save(id,'ok',3);expect(r.code,SaveCode.saved,reason:id);}
  final d=Disk();final r=await OwnedDraftStore(Auth(),d).save('d',' '+(List.filled(120,'a').join()),3);expect(r.code,SaveCode.invalid);expect(r.draft,isNull);expect(d.reads,0);
 });
 test('stored identity is preserved and conflict does not expose a draft',()async{
  final d=Disk()..value=const Draft('stored-id','alice','old',3);final s=OwnedDraftStore(Auth(),d);final r=await s.save('lookup-id',' trim ',3);expect(r.code,SaveCode.saved);expect(r.draft!.id,'stored-id');expect(d.attempted!.id,'stored-id');expect(d.attempted!.ownerId,'alice');expect(d.attempted!.title,'trim');
  final mismatch=await s.save('lookup-id','x',3);expect(mismatch.code,SaveCode.conflict);expect(mismatch.message,'Draft changed');expect(mismatch.draft,isNull);
  d.conflict=true;final race=await s.save('lookup-id','x',4);expect(race.code,SaveCode.conflict);expect(race.message,'Draft changed');expect(race.draft,isNull);
 });
 test('dependency failures preserve boundary and later requests recover',()async{
  for(var stage=0;stage<3;stage++) {
   final a=Auth();a.fail=stage==0;final d=Disk();d.readFail=stage==1;d.writeFail=stage==2;final s=OwnedDraftStore(a,d);
   final r=await s.save('d','secret',3);expect(r.code,SaveCode.unavailable);expect(r.message,'Draft unavailable');expect(r.draft,isNull);expect(d.reads,stage==0?0:1);expect(d.writes,stage==2?1:0);expect(d.value!.title,'old');
   a.fail=false;d.readFail=false;d.writeFail=false;final recovered=await s.save('d','next',3);expect(recovered.code,SaveCode.saved);expect(d.value!.title,'next');
  }
 });

}
