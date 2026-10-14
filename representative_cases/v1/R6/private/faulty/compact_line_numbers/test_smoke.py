import unittest
from decimal import Decimal
from manifest_parser import parse_line
from manifest import summarize

class Smoke(unittest.TestCase):
    def test_parse(self):
        item=parse_line('ORD-1,SKU,2,3.25',1)
        self.assertEqual(item.unit_price,Decimal('3.25'))
    def test_summary(self):
        result=summarize(['ORD-1,SKU,2,3.25'])
        self.assertEqual(result['accepted_count'],1)
        self.assertEqual(result['orders'],[{'order_id':'ORD-1','total':'6.50'}])
