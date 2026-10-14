import unittest
from reservation import reserve
class Smoke(unittest.TestCase):
    def test_invalid_input_preserves_stock(self):
        stock={'A':3};saved={}
        self.assertEqual(reserve('order1',[{'sku':'A','quantity':True}],stock,saved),{'status':'invalid_request'})
        self.assertEqual(stock,{'A':3});self.assertEqual(saved,{})
if __name__=='__main__': unittest.main()
