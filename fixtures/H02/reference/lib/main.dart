import 'package:flutter/material.dart';
import 'basket.dart';
import 'catalog.dart';
import 'summary.dart';
export 'basket.dart';

void main() =>
    runApp(ShopApp(basket: Basket(const [Product('one', '노트', 300)])));

class ShopApp extends StatelessWidget {
  final Basket basket;
  const ShopApp({super.key, required this.basket});
  @override
  Widget build(BuildContext context) => MaterialApp(
          home: Scaffold(
              body: Column(children: [
        ProductList(basket: basket),
        BasketSummary(basket: basket)
      ])));
}
