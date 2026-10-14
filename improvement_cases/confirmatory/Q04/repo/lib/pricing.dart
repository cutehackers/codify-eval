import 'api.dart';
Quote quote(List<Line> lines,{required bool member,required String region}) {
 final total=lines.fold<int>(0,(sum,line)=>sum+line.unitCents*line.quantity);
 return Quote(total,member?total~/10:0,500);
}
