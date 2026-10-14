from dataclasses import dataclass
from decimal import Decimal

class ManifestError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

@dataclass(frozen=True)
class LineItem:
    line_number: int
    order_id: str
    sku: str
    quantity: int
    unit_price: Decimal

@dataclass(frozen=True)
class RowError:
    line_number: int
    code: str
    message: str
    text: str

@dataclass(frozen=True)
class BatchResult:
    accepted: tuple[LineItem, ...]
    errors: tuple[RowError, ...]
    totals: dict[str, Decimal]
