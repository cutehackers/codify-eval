import 'package:flutter/material.dart';
import 'basket.dart';

class ProductList extends StatelessWidget {
  final Basket basket;
  const ProductList({super.key, required this.basket});
  @override
  Widget build(BuildContext context) => Column(children: [
        for (final product in basket.products)
          TextButton(
              key: ValueKey('add-${product.sku}'),
              onPressed: () => basket.add(product.sku),
              child: Text(product.name))
      ]);
}
