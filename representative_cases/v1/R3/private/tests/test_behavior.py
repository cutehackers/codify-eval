import asyncio
import unittest
from record_service import RecordService

class Behavior(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.calls = []
        self.entered = {k: asyncio.Event() for k in ("a", "b")}
        self.release = {k: asyncio.Event() for k in ("a", "b")}
        self.cleaned = []
        async def loader(key):
            self.calls.append(key)
            self.entered[key].set()
            try:
                await self.release[key].wait()
                return key.upper()
            finally:
                self.cleaned.append(key)
        self.service = RecordService(loader)
    async def asyncTearDown(self):
        await asyncio.wait_for(self.service.close(), 2)
    async def checkpoint(self):
        # One event-loop turn, not a wall-clock delay.
        event = asyncio.Event()
        asyncio.get_running_loop().call_soon(event.set)
        await event.wait()
    async def test_same_key_coalesces(self):
        a = asyncio.create_task(self.service.get("a"))
        await self.entered["a"].wait()
        b = asyncio.create_task(self.service.get("a"))
        await self.checkpoint()
        self.assertEqual(self.calls, ["a"])
        self.release["a"].set()
        self.assertEqual(await asyncio.gather(a,b), ["A","A"])
    async def test_different_keys_concurrent_and_ordered(self):
        batch = asyncio.create_task(self.service.get_many(["b","a","b"]))
        await self.entered["a"].wait(); await self.entered["b"].wait()
        self.release["a"].set(); self.release["b"].set()
        self.assertEqual(await batch, ["B","A","B"])
        self.assertEqual(sorted(self.calls), ["a","b"])
    async def test_cancel_one_preserves_other(self):
        first = asyncio.create_task(self.service.get("a"))
        await self.entered["a"].wait()
        second = asyncio.create_task(self.service.get("a"))
        await self.checkpoint(); first.cancel()
        with self.assertRaises(asyncio.CancelledError): await first
        self.assertEqual(self.service.pending_count, 1)
        self.release["a"].set()
        self.assertEqual(await second,"A")
    async def test_cancel_only_waiter_retains_ownership(self):
        first = asyncio.create_task(self.service.get("a"))
        await self.entered["a"].wait(); first.cancel()
        with self.assertRaises(asyncio.CancelledError): await first
        self.assertEqual(self.service.pending_count,1)
        self.release["a"].set()
        await self.service.close()
        self.assertEqual(self.service.pending_count,0)
    async def test_failure_fanout_and_immediate_retry(self):
        entered=asyncio.Event(); release=asyncio.Event(); calls=[]
        async def loader(key):
            calls.append(key)
            if len(calls)==1:
                entered.set(); await release.wait(); raise ValueError("unavailable")
            return "recovered"
        service=RecordService(loader)
        a=asyncio.create_task(service.get("a")); await entered.wait()
        b=asyncio.create_task(service.get("a")); await self.checkpoint(); release.set()
        results=await asyncio.gather(a,b,return_exceptions=True)
        self.assertTrue(all(isinstance(x,ValueError) for x in results))
        self.assertEqual(await service.get("a"),"recovered")
        self.assertEqual(calls,["a","a"]); await service.close()
    async def test_success_not_cached_and_no_finished_tasks(self):
        self.release["a"].set()
        self.assertEqual(await self.service.get("a"),"A")
        self.assertEqual(self.service.pending_count,0)
        await self.service.get("a")
        self.assertEqual(self.calls,["a","a"])
    async def test_close_cancels_waiters_and_cleanup(self):
        task=asyncio.create_task(self.service.get("a")); await self.entered["a"].wait()
        await self.service.close()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(self.cleaned,["a"]); self.assertEqual(self.service.pending_count,0)
        await self.service.close()
    async def test_concurrent_close_waits_for_cleanup(self):
        entered=asyncio.Event(); cancelled=asyncio.Event(); release=asyncio.Event()
        async def loader(key):
            entered.set()
            try: await asyncio.Event().wait()
            finally: cancelled.set(); await release.wait()
        service=RecordService(loader); waiter=asyncio.create_task(service.get("a")); await entered.wait()
        a=asyncio.create_task(service.close()); await cancelled.wait()
        b=asyncio.create_task(service.close()); await self.checkpoint()
        self.assertFalse(a.done()); self.assertFalse(b.done())
        release.set(); await asyncio.gather(a,b)
        with self.assertRaises(asyncio.CancelledError): await waiter
    async def test_closed_rejects_all_new_calls(self):
        await self.service.close()
        for fn in (lambda:self.service.get("a"), lambda:self.service.get_many([]), lambda:self.service.get_many(["a"])):
            with self.assertRaises(RuntimeError): await fn()
        self.assertEqual(self.calls,[])
    async def test_empty_batch(self):
        self.assertEqual(await self.service.get_many([]),[])
    async def test_batch_cancel_releases_callers_preserves_loads(self):
        batch=asyncio.create_task(self.service.get_many(["a","b"]))
        await self.entered["a"].wait(); await self.entered["b"].wait()
        batch.cancel()
        with self.assertRaises(asyncio.CancelledError): await batch
        self.assertEqual(self.service.pending_count,2)
        remaining=[t for t in asyncio.all_tasks() if t is not asyncio.current_task() and 'RecordService.get' in t.get_coro().__qualname__]
        self.assertEqual(remaining,[])
    async def test_batch_failure_releases_siblings(self):
        entered=asyncio.Event(); fail=asyncio.Event(); blocked=asyncio.Event()
        async def loader(key):
            if key=='a': entered.set(); await fail.wait(); raise ValueError('broken')
            blocked.set(); await asyncio.Event().wait()
        service=RecordService(loader)
        batch=asyncio.create_task(service.get_many(['a','b']))
        await entered.wait(); await blocked.wait(); fail.set()
        with self.assertRaisesRegex(ValueError,'broken'): await batch
        callers=[t for t in asyncio.all_tasks() if t is not asyncio.current_task() and 'RecordService.get' in t.get_coro().__qualname__]
        self.assertEqual(callers,[]); self.assertEqual(service.pending_count,1)
        await service.close()

# A wrong implementation must fail within a bounded deadline rather than hang
# on a never-reached barrier. Correctness assertions use Events, not elapsed time.
def _bounded(method):
    async def run(self):
        await asyncio.wait_for(method(self), timeout=2)
    return run
for _name, _method in list(vars(Behavior).items()):
    if _name.startswith('test_'):
        setattr(Behavior, _name, _bounded(_method))
