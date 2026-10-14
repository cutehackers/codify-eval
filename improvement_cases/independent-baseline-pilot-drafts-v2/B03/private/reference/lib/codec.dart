import 'dart:convert';
import 'models.dart';
bool validRecipe(Recipe r) => r.id.isNotEmpty && r.household.isNotEmpty && r.revision>=0 && r.title.trim().isNotEmpty && r.title.trim().length<=120 && r.ingredients.isNotEmpty && r.ingredients.length<=40 && r.ingredients.every((s)=>s.trim().isNotEmpty && s.length<=80);
Recipe? decodeRecipe(String raw,String household,String id) {
 try {
  final o=jsonDecode(raw); if(o is! Map<String,dynamic>) return null;
  final schema=o['schema']; if(schema!=1 && schema!=2) return null;
  if(o['id']!=id || o['household']!=household || o['revision'] is! int || o['title'] is! String) return null;
  final rows=schema==1?o['items']:o['ingredients'];
  if(rows is! List || rows.any((x)=>x is! String)) return null;
  final dirty=o['dirty']; if(o.containsKey('dirty') && dirty is! bool) return null;
  final r=Recipe(id,household,o['revision'] as int,o['title'] as String,rows.cast<String>(),dirty:dirty==true);
  return validRecipe(r)?r:null;
 }catch(_){return null;}
}
String encodeRecipe(Recipe r) => jsonEncode({'schema':2,'id':r.id,'household':r.household,'revision':r.revision,'title':r.title,'ingredients':r.ingredients,'dirty':r.dirty});
