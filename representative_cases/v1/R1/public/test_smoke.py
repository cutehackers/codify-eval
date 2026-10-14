import unittest
from document_export import export_document

class Smoke(unittest.TestCase):
    def test_bad_request_needs_no_dependencies(self):
        self.assertEqual(export_document({'doc_id': '../secret', 'filename': 'out.json'}, 'u', None, None, None, []), {'status': 'invalid_request'})

if __name__ == '__main__':
    unittest.main()
