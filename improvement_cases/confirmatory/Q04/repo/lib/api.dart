const contractVersion = 1;
class Line {
 final String sku;final int quantity;final int unitCents;
 const Line(this.sku,this.quantity,this.unitCents);
}
class Quote {
 final int subtotalCents; final int discountCents;final int shippingCents;
 const Quote(this.subtotalCents,this.discountCents,this.shippingCents);
 int get totalCents=>subtotalCents-discountCents+shippingCents;
}
class Reservation {
 final Map<String,int> available;
 final Map<String,int> requested;
 final bool accepted;
 Reservation(Map<String,int> available,Map<String,int> requested,this.accepted):available=Map.unmodifiable(available),requested=Map.unmodifiable(requested);
}
