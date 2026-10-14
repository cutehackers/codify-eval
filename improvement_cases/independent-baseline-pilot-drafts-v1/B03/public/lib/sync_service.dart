import 'models.dart';
class RecipeSyncService {
 final RecipeDisk disk;final RecipeCloud cloud;
 RecipeSyncService(this.disk,this.cloud);
 Future<RecipeSync> sync(String household,String id) async => const RecipeSync('decision_required');
}
