from decimal import Decimal
from manifest_parser import parse_line
from models import BatchResult, RowError, ManifestError

def process_lines(lines, parser=parse_line):
    accepted, errors, totals, seen = [], [], {}, set()
    for number, text in enumerate((x for x in lines if x.strip()), 1):
        if not text.strip():
            continue
        try:
            item = parser(text, number)
        except ManifestError as error:
            errors.append(RowError(number, error.code, str(error), text))
            continue
        key = (item.order_id, item.sku)
        if key in seen:
            errors.append(RowError(number, 'duplicate', 'Duplicate order/SKU pair', text))
            continue
        seen.add(key)
        accepted.append(item)
        totals[item.order_id] = totals.get(item.order_id, Decimal('0.00')) + item.quantity * item.unit_price
    return BatchResult(tuple(accepted), tuple(errors), totals)
