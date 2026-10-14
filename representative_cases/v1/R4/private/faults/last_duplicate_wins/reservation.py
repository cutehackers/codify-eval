import copy
import re

def reserve(order_id, lines, stock, reservations):
    def valid_id(value):
        return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,32}', value) is not None
    if not valid_id(order_id) or not isinstance(lines, list) or not lines:
        return {'status': 'invalid_request'}
    totals = {}
    for line in lines:
        if (not isinstance(line, dict) or set(line) != {'sku', 'quantity'}
            or not valid_id(line['sku']) or type(line['quantity']) is not int or line['quantity'] <= 0):
            return {'status': 'invalid_request'}
        totals[line['sku']] = line['quantity']
    items = [{'sku': sku, 'quantity': totals[sku]} for sku in sorted(totals)]
    if order_id in reservations:
        if reservations[order_id]['items'] != items:
            return {'status': 'conflict'}
        return copy.deepcopy(reservations[order_id])
    shortages = [{'sku': sku, 'requested': totals[sku], 'available': stock.get(sku, 0)}
                 for sku in sorted(totals) if totals[sku] > stock.get(sku, 0)]
    if shortages:
        return {'status': 'insufficient_stock', 'shortages': shortages}
    for sku in totals:
        stock[sku] -= totals[sku]
    receipt = {'status': 'reserved', 'order_id': order_id, 'items': items}
    reservations[order_id] = copy.deepcopy(receipt)
    return receipt
