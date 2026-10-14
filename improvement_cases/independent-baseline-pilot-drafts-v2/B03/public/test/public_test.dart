import 'package:test/test.dart';
import 'package:b03/models.dart';
import 'package:b03/labels.dart';
void main(){test('unresolved selection has a stable public label',(){
 expect(recipeLabel(const RecipeSync('decision_required')),'충돌 처리 방식을 먼저 정하세요.');
});}
