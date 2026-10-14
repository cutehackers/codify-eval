import math
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from outbox import Outbox, ConflictError

class Behavior(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'queue.sqlite';self.box=Outbox(self.path)
    def tearDown(self):
        self.box.close();self.tmp.cleanup()
    def test_canonical_duplicate(self):
        a=self.box.enqueue('a','x',{'z':2,'a':[1]})
        self.assertEqual(a,self.box.enqueue('a','x',{'a':[1],'z':2}))
        self.assertEqual(len(self.box.claim('a',0,5,5)),1)
    def test_conflict_preserves_original(self):
        a=self.box.enqueue('a','x',{'v':1})
        with self.assertRaises(ConflictError):self.box.enqueue('a','x',{'v':2})
        self.assertEqual(self.box.claim('a',0,5,1),[{'id':a,'key':'x','payload':{'v':1},'attempts':1}])
    def test_tenant_separation(self):
        a=self.box.enqueue('a','x',1);b=self.box.enqueue('b','x',2)
        self.assertNotEqual(a,b)
        self.assertEqual([r['id'] for r in self.box.claim('a',0,5,4)],[a])
        self.assertFalse(self.box.complete('b',a));self.assertFalse(self.box.retry('b',a,1))
        self.assertEqual([r['id'] for r in self.box.claim('b',0,5,4)],[b])
    def test_restart_and_done_idempotency(self):
        a=self.box.enqueue('a','x',1);self.box.claim('a',0,5,1);self.assertTrue(self.box.complete('a',a))
        self.box.close();self.box=Outbox(self.path)
        self.assertEqual(self.box.enqueue('a','x',1),a);self.assertEqual(self.box.claim('a',99,5,1),[])
        self.assertGreater(self.box.enqueue('a','y',2),a)
    def test_pending_survives_restart(self):
        a=self.box.enqueue('a','x',{'nested':[True,None]});self.box.close();self.box=Outbox(self.path)
        self.assertEqual(self.box.claim('a',0,5,1)[0]['id'],a)
    def test_lease_boundary_and_attempts(self):
        a=self.box.enqueue('a','x',1)
        self.assertEqual(self.box.claim('a',2,5,1)[0]['attempts'],1)
        self.assertEqual(self.box.claim('a',6.999,5,1),[])
        self.assertEqual(self.box.claim('a',7,5,1)[0]['attempts'],2)
    def test_retry_schedule(self):
        a=self.box.enqueue('a','x',1);self.box.claim('a',0,5,1)
        self.assertTrue(self.box.retry('a',a,20));self.assertEqual(self.box.claim('a',19,5,1),[])
        self.assertEqual(self.box.claim('a',20,5,1)[0]['attempts'],2)
    def test_state_transitions(self):
        a=self.box.enqueue('a','x',1)
        self.assertFalse(self.box.complete('a',a));self.assertFalse(self.box.retry('a',a,0))
        self.box.claim('a',0,5,1);self.assertTrue(self.box.complete('a',a))
        self.assertFalse(self.box.complete('a',a));self.assertFalse(self.box.retry('a',a,0));self.assertFalse(self.box.complete('a',999))
    def test_fifo_limit(self):
        ids=[self.box.enqueue('a',str(i),i) for i in range(4)]
        self.assertEqual([r['id'] for r in self.box.claim('a',0,5,2)],ids[:2])
        self.assertEqual([r['id'] for r in self.box.claim('a',0,5,5)],ids[2:])
    def test_invalid_claim_preserves(self):
        a=self.box.enqueue('a','x',1)
        for args in [('a',-1,5,1),('a',0,0,1),('a',float('nan'),5,1),('a',0,5,True),('a',0,5,0),('a',0,5,1.5)]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):self.box.claim(*args)
        self.assertEqual(self.box.claim('a',0,5,1)[0]['attempts'],1)
    def test_invalid_payload_and_identity(self):
        for args in [('', 'x',1),('a','',1),('a','x',float('nan')),('a','x',object())]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):self.box.enqueue(*args)
        self.assertEqual(self.box.claim('a',0,5,9),[])
    def test_invalid_retry_preserves_lease(self):
        a=self.box.enqueue('a','x',1);self.box.claim('a',0,5,1)
        with self.assertRaises(ValueError):self.box.retry('a',a,float('inf'))
        self.assertEqual(self.box.claim('a',4,5,1),[]);self.assertTrue(self.box.complete('a',a))
    def test_other_connection_cannot_steal_lease(self):
        self.box.enqueue('a','x',1);other=Outbox(self.path)
        try:
            self.assertEqual(len(self.box.claim('a',0,10,1)),1)
            self.assertEqual(other.claim('a',1,10,1),[])
        finally:other.close()
    def test_batch_failure_rolls_back(self):
        first=self.box.enqueue('a','one',1);second=self.box.enqueue('a','two',2)
        with sqlite3.connect(self.path) as db:
            # Find the implementation's message table by its documented persistent fields.
            tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            table=next(t for t in tables if {'id','attempts'}.issubset({r[1] for r in db.execute('PRAGMA table_info("'+t+'")')}))
            db.execute('CREATE TRIGGER fail_second BEFORE UPDATE ON "'+table+'" WHEN OLD.id='+str(second)+" BEGIN SELECT RAISE(ABORT,'injected write failure'); END")
        with self.assertRaises(sqlite3.DatabaseError):self.box.claim('a',0,10,2)
        with sqlite3.connect(self.path) as db:db.execute('DROP TRIGGER fail_second')
        rows=self.box.claim('a',0,10,2)
        self.assertEqual([r['id'] for r in rows],[first,second]);self.assertEqual([r['attempts'] for r in rows],[1,1])
    def test_simultaneous_claims_are_disjoint(self):
        ids={self.box.enqueue('a',str(i),i) for i in range(12)}
        barrier=threading.Barrier(2);results=[];errors=[]
        def worker():
            other=Outbox(self.path)
            try:
                barrier.wait(timeout=3)
                results.append(other.claim('a',0,10,6))
            except BaseException as exc:errors.append(exc)
            finally:other.close()
        threads=[threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(timeout=10)
        self.assertFalse(any(thread.is_alive() for thread in threads));self.assertEqual(errors,[])
        claimed=[row['id'] for result in results for row in result]
        self.assertEqual(len(claimed),12);self.assertEqual(set(claimed),ids)
