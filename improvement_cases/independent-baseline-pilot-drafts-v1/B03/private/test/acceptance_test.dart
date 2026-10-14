import 'dart:convert';
import 'package:test/test.dart';
import 'package:b03/models.dart';
import 'package:b03/codec.dart';
import 'package:b03/decision.dart';
import 'package:b03/sync_service.dart';
import 'package:b03/labels.dart';
const branch=String.fromEnvironment('OWNER_BRANCH');
Recipe recipe({int rev=3,bool dirty=true,String house='h',String title='콩국수'})=>Recipe('r',house,rev,title,['콩','물'],dirty:dirty);
String legacy()=>jsonEncode({'schema':1,'id':'r','household':'h','revision':3,'title':'콩국수','items':['콩','물'],'dirty':true});
class Disk implements RecipeDisk {
 String? value=legacy(); bool failRead=false,failWrite=false; int reads=0,writes=0;
 Future<String?> read(String h,String id)async{reads++;if(failRead)throw StateError('secret');return value;}
 Future<void> write(String h,String id,String raw)async{if(failWrite)throw StateError('secret');writes++;value=raw;}
}
class Cloud implements RecipeCloud {
 Recipe? remote=recipe(dirty:false),saved=recipe(rev:4,dirty:false); bool failFetch=false,failUpload=false; int fetches=0,uploads=0;int? expected;
 Future<Recipe?> fetch(String h,String id)async{fetches++;if(failFetch)throw StateError('secret');return remote;}
 Future<Recipe?> upload(Recipe r,int rev)async{uploads++;expected=rev;if(failUpload)throw StateError('secret');return saved;}
}
void main(){
 test('owner branch implemented rather than silently chosen',(){expect(['retain-draft','adopt-cloud'],contains(branch));expect(conflictMode,branch);});
 test('r1 legacy migration strict types and contents',(){
  final r=decodeRecipe(legacy(),'h','r')!;expect(r.ingredients,['콩','물']);expect(r.dirty,true);
  final out=jsonDecode(encodeRecipe(r));expect(out['schema'],2);expect(out.containsKey('items'),false);expect(out['ingredients'],['콩','물']);
  for(final patch in <Map<String,Object?>>[{'schema':4},{'revision':3.0},{'household':'foreign'},{'id':'other'},{'items':[1]},{'items':[]},{'dirty':'yes'},{'title':' '*3},{'title':'x'*121},{'items':['x'*81]}]){
   final raw=jsonDecode(legacy()) as Map<String,dynamic>;raw.addAll(patch);expect(decodeRecipe(jsonEncode(raw),'h','r'),null);
  }
  expect(decodeRecipe('{','h','r'),null);expect(decodeRecipe('[]','h','r'),null);
  expect(decodeRecipe(jsonEncode({'schema':2,'id':'r','household':'h','revision':0,'title':'  국수  ','ingredients':[' 물 ']}),'h','r')!.title,'  국수  ');
 });
 test('r2 early failure preserves disk and cloud boundaries',()async{
  for(final state in ['read','missing','invalid','fetch','remoteMissing']){
   final d=Disk();final c=Cloud(); if(state=='read')d.failRead=true;if(state=='missing')d.value=null;if(state=='invalid')d.value='private token';if(state=='fetch')c.failFetch=true;if(state=='remoteMissing')c.remote=null;
   final before=d.value;final r=await RecipeSyncService(d,c).sync('h','r');
   expect(r.code,{'read':'storage_unavailable','missing':'missing_local','invalid':'invalid_local','fetch':'offline','remoteMissing':'missing_remote'}[state]);expect(d.value,before);expect(d.writes,0);expect(c.uploads,0);expect(c.fetches, ['read','missing','invalid'].contains(state)?0:1);
  }
 });
 test('r3 reject foreign malformed or backwards snapshots',()async{
  for(final remote in [recipe(house:'foreign'),recipe(rev:2),recipe(title:'')]){
   final d=Disk();final before=d.value;final c=Cloud()..remote=remote;expect((await RecipeSyncService(d,c).sync('h','r')).code,'invalid_remote');expect(d.value,before);expect(c.uploads,0);
  }
  final d=Disk()..value=encodeRecipe(recipe(dirty:false));final c=Cloud()..remote=recipe(rev:7,dirty:true);
  expect((await RecipeSyncService(d,c).sync('h','r')).code,'updated');expect(decodeRecipe(d.value!,'h','r')!.revision,7);expect(decodeRecipe(d.value!,'h','r')!.dirty,false);expect(c.uploads,0);
 });
 test('r4 CAS success failure recovery and returned identity',()async{
  final d=Disk();final c=Cloud();final r=await RecipeSyncService(d,c).sync('h','r');expect(r.code,'uploaded');expect(c.expected,3);expect(c.uploads,1);expect(decodeRecipe(d.value!,'h','r')!.dirty,false);
  for(final kind in ['race','offline','foreign','wrongRevision']){
   final disk=Disk();final before=disk.value;final cloud=Cloud();if(kind=='race')cloud.saved=null;if(kind=='offline')cloud.failUpload=true;if(kind=='foreign')cloud.saved=recipe(rev:4,house:'other');if(kind=='wrongRevision')cloud.saved=recipe(rev:8);
   expect((await RecipeSyncService(disk,cloud).sync('h','r')).code,kind=='race'?'conflict_retry':kind=='offline'?'offline':'invalid_remote');expect(disk.value,before);expect(disk.writes,0);expect(cloud.uploads,1);expect(cloud.fetches,1);
  }
 });
 test('r5 resolved conflict policy and write failure',()async{
  final d=Disk();final before=d.value;final c=Cloud()..remote=recipe(rev:5,title:'가족 새 조리법',dirty:false);
  final r=await RecipeSyncService(d,c).sync('h','r');expect(c.uploads,0);
  if(branch=='retain-draft'){expect(r.code,'conflict_retained');expect(d.value,before);expect(d.writes,0);expect(r.recipe!.title,'콩국수');expect(r.recipe!.dirty,true);}
  else {expect(r.code,'conflict_replaced');expect(d.writes,1);expect(decodeRecipe(d.value!,'h','r')!.title,'가족 새 조리법');expect(r.recipe!.dirty,false);}
  final disk=Disk()..failWrite=true;final old=disk.value;final cloud=Cloud();expect((await RecipeSyncService(disk,cloud).sync('h','r')).code,'storage_unavailable');expect(disk.value,old);
  if(branch=='adopt-cloud'){final x=Disk()..failWrite=true;final y=Cloud()..remote=recipe(rev:9);expect((await RecipeSyncService(x,y).sync('h','r')).code,'storage_unavailable');}
 });
 test('r6 messages contain no remote diagnostics',(){
  const expected={'updated':'최신 조리법을 받았습니다.','uploaded':'변경을 저장했습니다.','offline':'연결되면 다시 저장하세요.','conflict_retained':'기기 변경을 보관했습니다. 내용을 비교하세요.','conflict_replaced':'가족의 최신 조리법으로 바꿨습니다.','conflict_retry':'다른 변경이 있습니다. 다시 확인하세요.','storage_unavailable':'기기 저장 공간을 확인하세요.','missing_local':'기기 조리법을 찾을 수 없습니다.','invalid_local':'기기 조리법을 읽을 수 없습니다.','missing_remote':'공유 조리법을 찾을 수 없습니다.','invalid_remote':'공유 조리법을 확인할 수 없습니다.'};
  for(final e in expected.entries)expect(recipeLabel(RecipeSync(e.key,recipe())),e.value);
  expect(recipeLabel(const RecipeSync('password=hidden')),'조리법을 확인할 수 없습니다.');
 });
}
