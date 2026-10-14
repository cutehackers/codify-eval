import 'models.dart';
String recipeLabel(RecipeSync s) => s.code=='decision_required' ? '충돌 처리 방식을 먼저 정하세요.' : '조리법을 확인할 수 없습니다.';
