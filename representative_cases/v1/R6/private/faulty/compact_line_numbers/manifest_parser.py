import csv
import re
from decimal import Decimal
from models import LineItem, ManifestError

_ID = re.compile(r"[A-Za-z0-9_-]{1,32}", re.ASCII)
_QTY = re.compile(r"[0-9]+", re.ASCII)
_PRICE = re.compile(r"[0-9]+\.[0-9]{2}", re.ASCII)

def parse_line(text, line_number):
    record = text[:-2] if text.endswith('\r\n') else text[:-1] if text.endswith('\n') else text
    if '\n' in record or '\r' in record:
        raise ManifestError('csv', 'Only one optional trailing LF or CRLF is allowed')
    try:
        rows = list(csv.reader([record], strict=True))
    except csv.Error as error:
        raise ManifestError('csv', str(error)) from error
    fields = rows[0] if rows else []
    if len(fields) != 4:
        raise ManifestError('fields', 'Expected four fields')
    order, sku, quantity, price = (field.strip() for field in fields)
    if not _ID.fullmatch(order):
        raise ManifestError('order_id', 'Invalid order ID')
    if not _ID.fullmatch(sku):
        raise ManifestError('sku', 'Invalid SKU')
    if not _QTY.fullmatch(quantity) or len(quantity.lstrip("0")) > 5 or not 1 <= int(quantity.lstrip("0") or "0") <= 10000:
        raise ManifestError('quantity', 'Quantity must be 1 through 10000')
    if not _PRICE.fullmatch(price) or Decimal(price) > Decimal('1000000.00'):
        raise ManifestError('price', 'Invalid two-decimal price')
    return LineItem(line_number, order, sku, int(quantity.lstrip("0") or "0"), Decimal(price))
