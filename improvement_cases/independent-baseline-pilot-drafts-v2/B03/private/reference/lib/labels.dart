import 'models.dart';
String recipeLabel(RecipeSync s) {
 const labels={'updated':'최신 조리법을 받았습니다.','uploaded':'변경을 저장했습니다.',
 'offline':'연결되면 다시 저장하세요.','conflict_retained':'기기 변경을 보관했습니다. 내용을 비교하세요.',
 'conflict_replaced':'가족의 최신 조리법으로 바꿨습니다.','conflict_retry':'다른 변경이 있습니다. 다시 확인하세요.',
 'decision_required':'충돌 처리 방식을 먼저 정하세요.','storage_unavailable':'기기 저장 공간을 확인하세요.',
 'missing_local':'기기 조리법을 찾을 수 없습니다.','invalid_local':'기기 조리법을 읽을 수 없습니다.',
 'missing_remote':'공유 조리법을 찾을 수 없습니다.','invalid_remote':'공유 조리법을 확인할 수 없습니다.'};
 return labels[s.code]??'조리법을 확인할 수 없습니다.';
}
