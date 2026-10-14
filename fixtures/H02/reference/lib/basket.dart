import 'package:flutter/foundation.dart';

class Product {
  final String sku;
  final String name;
  final int cents;
  const Product(this.sku, this.name, this.cents);
}

class Basket extends ChangeNotifier {
  final Map<String, int> counts = {};
  final List<Product> products;
  Basket(this.products);
  void add(String sku) {
    if (!products.any((p) => p.sku == sku)) return;
    counts[sku] = (counts[sku] ?? 0) + 1;
    notifyListeners();
  }

  int get totalCents =>
      products.fold(0, (sum, p) => sum + p.cents * (counts[p.sku] ?? 0));
}
