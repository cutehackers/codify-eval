import 'api.dart';
Reservation reserve(Map<String,int> stock,List<Line> lines) {
 final result=Map<String,int>.of(stock);final requested=<String,int>{};
 for(final line in lines){requested[line.sku]=line.quantity;result[line.sku]=(result[line.sku]??0)-line.quantity;}
 return Reservation(result,requested,true);
}
