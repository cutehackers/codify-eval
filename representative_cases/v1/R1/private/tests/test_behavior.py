import json
import unittest
from document_export import export_document

class Repo:
    def __init__(self, events):
        self.events=events; self.permission=True; self.document={'id':'memo-7','title':'회의', 'text':'line1\nline2'}; self.fail=None
    def can_export(self, actor, doc_id):
        self.events.append(('auth', actor, doc_id))
        if self.fail=='auth': raise RuntimeError('credential=SECRET')
        return self.permission
    def get(self, doc_id):
        self.events.append(('read', doc_id))
        if self.fail=='read': raise RuntimeError('private database path')
        return self.document
class Store:
    def __init__(self, events): self.events=events; self.files={}; self.fail=False
    def write(self, filename, data):
        self.events.append(('write', filename))
        if self.fail: raise RuntimeError('token=SECRET')
        self.files[filename]=data
class Boundary(unittest.TestCase):
    def setUp(self):
        self.events=[]; self.repo=Repo(self.events); self.store=Store(self.events); self.audit=[]
        self.request={'doc_id':'memo-7','filename':'meeting_7.json'}
        self.output=json.dumps(self.repo.document, ensure_ascii=False, indent=2).encode()
        self.render=lambda doc: self.events.append(('render',)) or self.output
    def run_export(self, request=...):
        return export_document(self.request if request is ... else request,'user-9',self.repo,self.render,self.store,self.audit)
    def test_invalid_inputs_before_any_effect(self):
        for value in [None, [], {}, {'doc_id':'memo-7'}, {**self.request,'extra':1}, {**self.request,'doc_id':'../private'}, {**self.request,'doc_id':7}, {**self.request,'filename':'../x.json'}, {**self.request,'filename':'a.json\n'}, {**self.request,'filename':False}]:
            with self.subTest(value=value):
                self.assertEqual(self.run_export(value), {'status':'invalid_request'}); self.assertEqual(self.events,[])
        self.assertEqual(self.store.files,{}); self.assertEqual(self.audit,[])
    def test_permission_is_strict_and_before_read(self):
        for permission in [False, None, 1, 'yes']:
            with self.subTest(permission=permission):
                self.events.clear();self.repo.permission=permission
                self.assertEqual(self.run_export(),{'status':'forbidden'})
                self.assertEqual(self.events,[('auth','user-9','memo-7')])
        self.assertEqual(self.store.files,{});self.assertEqual(self.audit,[])
    def test_missing_document(self):
        self.repo.document=None
        self.assertEqual(self.run_export(),{'status':'not_found'})
        self.assertEqual(self.events,[('auth','user-9','memo-7'),('read','memo-7')]);self.assertEqual(self.audit,[])
    def test_invalid_repository_document(self):
        for document in [{'id':'other','title':'a','text':'b'}, {'id':'memo-7','title':1,'text':'b'}, {'id':'memo-7','title':'a','text':'b','secret':'x'}]:
            with self.subTest(document=document):
                self.events.clear();self.repo.document=document
                self.assertEqual(self.run_export(),{'status':'unavailable'});self.assertEqual(len(self.events),2)
        self.assertEqual(self.store.files,{})
    def test_success_preserves_valid_bytes_and_order(self):
        self.assertEqual(self.run_export(),{'status':'ok','filename':'meeting_7.json','size':len(self.output)})
        self.assertEqual(self.events,[('auth','user-9','memo-7'),('read','memo-7'),('render',),('write','meeting_7.json')])
        self.assertEqual(self.store.files,{'meeting_7.json':self.output})
        self.assertEqual(self.audit,[{'actor':'user-9','doc_id':'memo-7','filename':'meeting_7.json'}])
    def test_invalid_injected_output_never_persists(self):
        for output in [b'not json', b'\xff', '{}', b'[]', b'{"id":"memo-7","title":"changed","text":"x"}', json.dumps({**self.repo.document,'extra':'secret'}).encode()]:
            with self.subTest(output=output):
                self.output=output;self.events.clear()
                self.assertEqual(self.run_export(),{'status':'invalid_output'});self.assertEqual(len(self.events),3)
                self.assertEqual(self.store.files,{});self.assertEqual(self.audit,[])
    def test_renderer_cannot_mutate_authoritative_document(self):
        original=dict(self.repo.document)
        def mutating(doc):
            doc['text']='tampered';return json.dumps(doc).encode()
        self.render=mutating
        self.assertEqual(self.run_export(),{'status':'invalid_output'})
        self.assertEqual(self.repo.document,original);self.assertEqual(self.store.files,{});self.assertEqual(self.audit,[])
    def test_dependency_errors_are_safe_and_unaudited(self):
        for failure in ['auth','read','render','write']:
            with self.subTest(failure=failure):
                self.setUp()
                self.repo.fail=failure
                if failure=='render':
                    def broken(doc): raise RuntimeError('password=SECRET')
                    self.render=broken
                self.store.fail=failure=='write'
                self.assertEqual(self.run_export(),{'status':'unavailable'});self.assertEqual(self.audit,[]);self.assertEqual(self.store.files,{})
if __name__ == '__main__': unittest.main()
