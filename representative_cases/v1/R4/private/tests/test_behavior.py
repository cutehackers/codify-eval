import copy
import unittest
from reservation import reserve
class Reservations(unittest.TestCase):
    def setUp(self):
        self.stock={'A':8,'B':4,'OTHER':99};self.saved={}
    def assert_unchanged(self, before): self.assertEqual((self.stock,self.saved),before)
    def test_validate_all_before_effects(self):
        for order,lines in [('bad id',[{'sku':'A','quantity':1}]), ('o',[]), ('o',None), ('o',[{'sku':'A','quantity':1},{'sku':'B','quantity':True}]), ('o',[{'sku':'A','quantity':0}]), ('o',[{'sku':'A','quantity':1,'extra':1}]), ('o',[{'sku':'../A','quantity':2}]), ('o',[{'sku':'A','quantity':1.0}])]:
            with self.subTest(order=order,lines=lines):
                before=copy.deepcopy((self.stock,self.saved))
                self.assertEqual(reserve(order,lines,self.stock,self.saved),{'status':'invalid_request'});self.assert_unchanged(before)
    def test_aggregate_and_sort_success(self):
        lines=[{'sku':'B','quantity':1},{'sku':'A','quantity':2},{'sku':'B','quantity':2}];original=copy.deepcopy(lines)
        receipt=reserve('o',lines,self.stock,self.saved)
        self.assertEqual(receipt,{'status':'reserved','order_id':'o','items':[{'sku':'A','quantity':2},{'sku':'B','quantity':3}]})
        self.assertEqual(self.stock,{'A':6,'B':1,'OTHER':99});self.assertEqual(self.saved,{'o':receipt});self.assertEqual(lines,original)
    def test_shortage_is_atomic_and_sorted(self):
        before=copy.deepcopy((self.stock,self.saved))
        result=reserve('o',[{'sku':'B','quantity':6},{'sku':'A','quantity':2},{'sku':'Z','quantity':1}],self.stock,self.saved)
        self.assertEqual(result,{'status':'insufficient_stock','shortages':[{'sku':'B','requested':6,'available':4},{'sku':'Z','requested':1,'available':0}]});self.assert_unchanged(before)
    def test_repeated_sku_shortage_uses_total(self):
        before=copy.deepcopy((self.stock,self.saved))
        self.assertEqual(reserve('o',[{'sku':'A','quantity':5},{'sku':'A','quantity':4}],self.stock,self.saved),{'status':'insufficient_stock','shortages':[{'sku':'A','requested':9,'available':8}]});self.assert_unchanged(before)
    def test_normalized_retry_no_double_debit(self):
        first=reserve('o',[{'sku':'A','quantity':2},{'sku':'A','quantity':3}],self.stock,self.saved)
        before=copy.deepcopy((self.stock,self.saved))
        retry=reserve('o',[{'sku':'A','quantity':5}],self.stock,self.saved)
        self.assertEqual(retry,first);self.assert_unchanged(before)
        retry['items'][0]['quantity']=100
        self.assertEqual(self.saved['o']['items'][0]['quantity'],5)
    def test_conflicting_retry_preserves_state(self):
        reserve('o',[{'sku':'B','quantity':1}],self.stock,self.saved);before=copy.deepcopy((self.stock,self.saved))
        self.assertEqual(reserve('o',[{'sku':'A','quantity':1}],self.stock,self.saved),{'status':'conflict'});self.assert_unchanged(before)
    def test_return_value_does_not_alias_saved_receipt(self):
        result=reserve('o',[{'sku':'A','quantity':1}],self.stock,self.saved)
        result['items'][0]['quantity']=8;result['status']='changed'
        self.assertEqual(self.saved['o'],{'status':'reserved','order_id':'o','items':[{'sku':'A','quantity':1}]})
    def test_shortage_not_saved_retry_after_replenishment(self):
        self.assertEqual(reserve('o',[{'sku':'NEW','quantity':2}],self.stock,self.saved)['status'],'insufficient_stock')
        self.assertNotIn('NEW',self.stock);self.assertNotIn('o',self.saved)
        self.stock['NEW']=2
        self.assertEqual(reserve('o',[{'sku':'NEW','quantity':2}],self.stock,self.saved)['status'],'reserved');self.assertEqual(self.stock['NEW'],0)
if __name__=='__main__': unittest.main()
