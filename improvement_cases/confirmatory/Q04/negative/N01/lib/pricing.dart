import 'api.dart';
Quote quote(List<Line> lines,{required bool member,required String region}) {
 if(region!='mainland' && region!='island')throw ArgumentError.value(region,'region');
 var subtotal=0;
 for(final line in lines){if(line.sku.trim().isEmpty || line.quantity<=0 || line.unitCents<0)throw ArgumentError('Invalid line');subtotal+=line.quantity*line.unitCents;}
 final discount=member?(subtotal*750)~/10000:0;
 final after=subtotal;
 final shipping=lines.isEmpty?0:(after>=5000?0:500)+(region=='island'?300:0);
 return Quote(subtotal,discount,shipping);
}
