import json
import unittest
from decimal import Decimal
from models import LineItem, ManifestError
from manifest_parser import parse_line
from batch_processor import process_lines
from manifest import summarize

class ParserChecks(unittest.TestCase):
    def assertCode(self, text, code):
        with self.assertRaises(ManifestError) as caught: parse_line(text,7)
        self.assertEqual(caught.exception.code,code)
        self.assertTrue(str(caught.exception))
    def test_csv_quotes_trim_line_number_and_decimal(self):
        item=parse_line('" ORD-1 ","SKU", 2 , 0.10 ',9)
        self.assertEqual(item,LineItem(9,'ORD-1','SKU',2,Decimal('0.10')))
    def test_field_count_and_csv_syntax(self):
        self.assertCode('a,b,1','fields')
        self.assertCode('"a,b,1,1.00','csv')
        self.assertCode('a,b,1,1.00\nx','csv')
    def test_ids_ascii_and_length(self):
        for text,code in [('a!,b,1,1.00','order_id'),('a,b!,1,1.00','sku'),('a'*33+',b,1,1.00','order_id'),('é,b,1,1.00','order_id')]:
            self.assertCode(text,code)
        self.assertEqual(parse_line('a'*32+',B_-,1,0.00',1).sku,'B_-')
    def test_quantity_limits_and_ascii(self):
        for qty in ['0','10001','-1','1.0','+1','１','9'*5000]:
            self.assertCode('a,b,'+qty+',1.00','quantity')
        self.assertEqual(parse_line('a,b,10000,1.00',1).quantity,10000)
    def test_price_format_and_limits(self):
        for price in ['-0.10','1','1.0','1.000','1e2','NaN','1000000.01','１.00']:
            self.assertCode('a,b,1,'+price,'price')
        self.assertEqual(parse_line('a,b,1,1000000.00',1).unit_price,Decimal('1000000.00'))
    def test_validation_precedence(self):
        self.assertCode('!,!,0,NaN','order_id')
        self.assertCode('a,!,0,NaN','sku')
        self.assertCode('a,b,0,NaN','quantity')

class BatchChecks(unittest.TestCase):
    def test_injected_parser_single_call_physical_positions(self):
        calls=[]
        def parser(text,number):
            calls.append((text,number)); return LineItem(number,'X',str(number),2,Decimal('0.15'))
        rows=['\n','opaque one','  ','opaque two']
        result=process_lines(iter(rows),parser=parser)
        self.assertEqual(calls,[('opaque one',2),('opaque two',4)])
        self.assertEqual([x.line_number for x in result.accepted],[2,4])
        self.assertEqual(result.totals,{'X':Decimal('0.60')})
        self.assertEqual(rows,['\n','opaque one','  ','opaque two'])
    def test_errors_duplicates_and_rejected_rows_do_not_reserve(self):
        rows=['a,s,0,1.00\n','a,s,2,0.10','a,s,3,0.20','b,s,1,1.25','a,t,1,0.10']
        result=process_lines(rows)
        self.assertEqual([x.line_number for x in result.accepted],[2,4,5])
        self.assertEqual([(e.line_number,e.code,e.text) for e in result.errors],[(1,'quantity',rows[0]),(3,'duplicate',rows[2])])
        self.assertEqual(result.totals,{'a':Decimal('0.30'),'b':Decimal('1.25')})
    def test_unexpected_parser_exception_propagates(self):
        def broken(text,number): raise RuntimeError('bug')
        with self.assertRaisesRegex(RuntimeError,'bug'): process_lines(['anything'],parser=broken)
    def test_calls_are_independent(self):
        first=process_lines(['a,s,1,1.00']); second=process_lines(['a,s,1,1.00'])
        self.assertEqual(first,second); self.assertEqual(len(second.accepted),1)
    def test_empty_and_all_invalid(self):
        self.assertEqual(process_lines([]).totals,{})
        self.assertEqual(len(process_lines(['bad','a,s,0,1.00']).errors),2)
    def test_summary_integration_sorted_exact_and_json(self):
        result=summarize(['z,s,3,0.10','A,s,2,2.00','bad','z,s,9,9.00'])
        self.assertEqual(set(result),{'accepted_count','errors','orders'})
        self.assertEqual(result['accepted_count'],2)
        self.assertEqual(result['orders'],[{'order_id':'A','total':'4.00'},{'order_id':'z','total':'0.30'}])
        self.assertEqual([(e['line_number'],e['code']) for e in result['errors']],[(3,'fields'),(4,'duplicate')])
        self.assertTrue(all(set(e)=={'line_number','code','message'} and e['message'] for e in result['errors']))
        json.dumps(result)
        self.assertEqual(summarize([]),{'accepted_count':0,'errors':[],'orders':[]})
