import 'api.dart';
Reservation reserve(Map<String,int> stock,List<Line> lines) {
 for(final entry in stock.entries){if(entry.key.trim().isEmpty || entry.value<0)throw ArgumentError('Invalid stock');}
 final requested=<String,int>{};
 for(final line in lines){if(line.sku.trim().isEmpty || line.quantity<=0 || line.unitCents<0)throw ArgumentError('Invalid line');requested.update(line.sku,(old)=>old+line.quantity,ifAbsent:()=>line.quantity);}
 final accepted=requested.entries.every((entry)=>(stock[entry.key]??0)>=entry.value);
 final next=Map<String,int>.of(stock);
 for(final entry in requested.entries){if((next[entry.key]??0)>=entry.value)next[entry.key]=next[entry.key]!-entry.value;}
 return Reservation(next,requested,accepted);
}
