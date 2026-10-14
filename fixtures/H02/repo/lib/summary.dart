import 'package:flutter/material.dart';
import 'basket.dart';

class BasketSummary extends StatelessWidget {
  final Basket basket;
  const BasketSummary({super.key, required this.basket});
  @override
  Widget build(BuildContext context) => AnimatedBuilder(
      animation: basket,
      builder: (_, _) => Column(children: [
            for (final product in basket.products)
              if ((basket.counts[product.sku] ?? 0) > 0)
                Text('${product.name} x${basket.counts[product.sku]}'),
            Text('총액 ${basket.totalCents} 센트')
          ]));
}
