class Recipe {
 final String id,household,title; final int revision; final List<String> ingredients; final bool dirty;
 Recipe(this.id,this.household,this.revision,this.title,List<String> ingredients,{this.dirty=false}) : ingredients=List.unmodifiable(ingredients);
 Recipe clean() => Recipe(id,household,revision,title,ingredients);
}
abstract class RecipeDisk {
 Future<String?> read(String household,String id);
 // Atomic per-key replacement. Failure preserves old value.
 Future<void> write(String household,String id,String json);
}
abstract class RecipeCloud {
 Future<Recipe?> fetch(String household,String id);
 // Atomic compare-and-swap. null means concurrent conflict, no remote modification.
 Future<Recipe?> upload(Recipe draft,int expectedRevision);
}
class RecipeSync {
 final String code; final Recipe? recipe;
 const RecipeSync(this.code,[this.recipe]);
}
