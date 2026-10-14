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
  void add(String sku) {}
  int get totalCents => 0;
}
