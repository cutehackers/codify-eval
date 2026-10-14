import 'models.dart';
import 'codec.dart';
import 'decision.dart';
class RecipeSyncService {
 final RecipeDisk disk; final RecipeCloud cloud;
 RecipeSyncService(this.disk,this.cloud);
 Future<RecipeSync> sync(String household,String id) async {
  if(conflictMode==null) return const RecipeSync('decision_required');
  String? raw;
  try {raw=await disk.read(household,id);}catch(_){return const RecipeSync('storage_unavailable');}
  if(raw==null) return const RecipeSync('missing_local');
  final local=decodeRecipe(raw,household,id);
  if(local==null) return const RecipeSync('invalid_local');
  Recipe? remote;
  try {remote=await cloud.fetch(household,id);}catch(_){return RecipeSync('offline',local);}
  if(remote==null) return RecipeSync('missing_remote',local);
  if(!validRecipe(remote) || remote.id!=id || remote.household!=household) return RecipeSync('invalid_remote',local);
  if(remote.revision<local.revision) return RecipeSync('invalid_remote',local);
  if(!local.dirty) return _save(remote.clean(),'updated');
  if(remote.revision!=local.revision) return _conflict(local,remote);
  Recipe? saved;
  try {saved=await cloud.upload(local,local.revision);}catch(_){return RecipeSync('offline',local);}
  if(saved==null) return RecipeSync('conflict_retry',local);
  if(!validRecipe(saved) || saved.id!=id || saved.household!=household || saved.revision!=local.revision+1) return RecipeSync('invalid_remote',local);
  return _save(saved.clean(),'uploaded');
 }
 Future<RecipeSync> _conflict(Recipe local,Recipe remote) async {
  if(conflictMode=='retain-draft') return RecipeSync('conflict_retained',local);
  if(conflictMode=='adopt-cloud') return _save(remote.clean(),'conflict_replaced');
  return const RecipeSync('decision_required');
 }
 Future<RecipeSync> _save(Recipe r,String code) async {
  try {await disk.write(r.household,r.id,encodeRecipe(r));}
  catch(_){return const RecipeSync('storage_unavailable');}
  return RecipeSync(code,r);
 }
}
